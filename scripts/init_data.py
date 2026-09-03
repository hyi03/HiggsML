"""Initialize the shared HiggsML Monte Carlo inputs under data/raw/."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


CHUNK_SIZE = 1024 * 1024
PROGRESS_WIDTH = 40
USER_AGENT = "HiggsML-data-initializer/1.0"
HIGGS_RECORD = "https://opendata.cern.ch/record/atlas-93928"
HIGGS_RECORD_API = "https://opendata.cern.ch/api/records/atlas-93928"


@dataclass(frozen=True)
class Dataset:
    name: str
    dsid: int
    filename: str
    size_bytes: int
    sha256: str
    download_url: str | None
    record_url: str


DATASETS = (
    Dataset(
        name="Higgs MC",
        dsid=345060,
        filename="higgs.root",
        size_bytes=182_051_943,
        sha256="5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0",
        download_url=None,
        record_url=HIGGS_RECORD,
    ),
    Dataset(
        name="continuum ZZ MC",
        dsid=363490,
        filename="zz_363490.root",
        size_bytes=179_082_866,
        sha256="76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07",
        download_url=(
            "https://opendata.cern.ch/record/15005/files/"
            "mc_363490.llll.4lep.root"
        ),
        record_url="https://opendata.cern.ch/record/15005",
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, dataset: Dataset) -> tuple[bool, str]:
    actual_size = path.stat().st_size
    if actual_size != dataset.size_bytes:
        return False, f"size {actual_size}, expected {dataset.size_bytes}"
    actual_hash = sha256_file(path)
    if actual_hash != dataset.sha256:
        return False, f"SHA-256 {actual_hash}, expected {dataset.sha256}"
    return True, "size and SHA-256 match"


def print_progress(downloaded: int, total: int) -> None:
    ratio = min(downloaded / total, 1.0)
    completed = int(PROGRESS_WIDTH * ratio)
    bar = "#" * completed + "-" * (PROGRESS_WIDTH - completed)
    downloaded_mib = downloaded / (1024 * 1024)
    total_mib = total / (1024 * 1024)
    print(
        f"\r  [{bar}] {ratio:6.2%}  {downloaded_mib:7.1f}/{total_mib:.1f} MiB",
        end="",
        flush=True,
    )


def resolve_higgs_download_url() -> str:
    request = Request(HIGGS_RECORD_API, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        record = json.load(response)

    files = record.get("metadata", {}).get("files", [])
    candidates = [
        item
        for item in files
        if str(345060) in str(item.get("key", ""))
        and item.get("size") == 182_051_943
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            "CERN record did not contain exactly one DSID 345060 file with the "
            f"expected size; inspect {HIGGS_RECORD}"
        )

    key = candidates[0].get("key")
    if not isinstance(key, str) or not key:
        raise RuntimeError(f"CERN record returned an invalid filename; inspect {HIGGS_RECORD}")
    return f"{HIGGS_RECORD}/files/{quote(key, safe='._-')}"


def download(dataset: Dataset, destination: Path) -> None:
    url = dataset.download_url or resolve_higgs_download_url()
    temporary = destination.with_name(f"{destination.name}.part")
    temporary.unlink(missing_ok=True)

    print(f"Downloading {dataset.name} (DSID {dataset.dsid})")
    print(f"  source: {url}")
    print(f"  target: {destination}")

    request = Request(url, headers={"User-Agent": USER_AGENT})
    downloaded = 0
    try:
        with urlopen(request, timeout=60) as response, temporary.open("xb") as output:
            while chunk := response.read(CHUNK_SIZE):
                output.write(chunk)
                downloaded += len(chunk)
                print_progress(downloaded, dataset.size_bytes)
        print()

        valid, detail = verify_file(temporary, dataset)
        if not valid:
            raise RuntimeError(f"downloaded {dataset.filename} failed verification: {detail}")
        os.replace(temporary, destination)
        print(f"  ready: {detail}")
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def initialize(data_dir: Path, *, force: bool) -> None:
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for dataset in DATASETS:
        destination = raw_dir / dataset.filename
        if destination.exists() and not destination.is_file():
            raise RuntimeError(f"destination is not a regular file: {destination}")
        if destination.exists():
            valid, detail = verify_file(destination, dataset)
            if valid and not force:
                print(f"Skipping {destination}: {detail}")
                continue
            if not valid and not force:
                raise RuntimeError(
                    f"existing {destination} failed verification ({detail}); "
                    "rerun with --force to replace it"
                )
        download(dataset, destination)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and verify the shared HiggsML MC ROOT files."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="redownload and replace existing files after verifying the new download",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    try:
        initialize(repository_root / "data", force=args.force)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"data initialization failed: {error}", file=sys.stderr)
        return 1
    print("Shared data initialization completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
