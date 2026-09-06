"""Initialize pinned, same-release MC pairs. Standard library only."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
import time
from urllib.request import Request, urlopen
from http.client import HTTPException

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "higgsml_download_contract", REPOSITORY_ROOT / "neural" / "src" / "data_contract.py"
)
_contract = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _contract
_spec.loader.exec_module(_contract)
DatasetBinding = _contract.DatasetBinding
Member = _contract.Member
DATASET_NAMES = _contract.DATASET_NAMES
load_dataset = _contract.load_dataset

CHUNK_SIZE = 1024 * 1024
VERSION = "2.0"
USER_AGENT = f"HiggsML-data-initializer/{VERSION}"
TIMEOUT = 60
MAX_ATTEMPTS = 3
RECEIPT_SCHEMA = "higgsml.download-receipt.v1"


def safe_path(path: Path, *, directory: bool = False) -> None:
    """Check every existing component without resolving away links/reparse points."""
    if ".." in path.parts:
        raise RuntimeError(f"parent traversal is forbidden: {path}")
    path = Path(os.path.abspath(path))
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise RuntimeError(f"link/reparse point is forbidden: {component}")
        expected_dir = component != path or directory
        if not (stat.S_ISDIR(info.st_mode) if expected_dir else stat.S_ISREG(info.st_mode)):
            raise RuntimeError(f"not a regular {'directory' if expected_dir else 'file'}: {component}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, member: Member) -> tuple[bool, str]:
    safe_path(path)
    if not path.exists():
        return False, "missing file"
    size = path.stat().st_size
    if size != member.size_bytes:
        return False, f"size {size}, expected {member.size_bytes}"
    digest = sha256_file(path)
    if digest != member.sha256:
        return False, f"SHA-256 {digest}, expected {member.sha256}"
    return True, "size and SHA-256 match"


def print_progress(downloaded: int, total: int) -> None:
    ratio = min(downloaded / total, 1.0)
    completed = int(40 * ratio)
    print(f"\r  [{'#' * completed}{'-' * (40-completed)}] {ratio:6.2%} "
          f"{downloaded / 1048576:.1f}/{total / 1048576:.1f} MiB", end="", flush=True)


@contextmanager
def dataset_lock(directory: Path):
    lock = directory / ".init-data.lock"
    safe_path(lock)
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise RuntimeError(f"dataset is locked: {lock}; see README for crash recovery") from error
    identity = os.fstat(descriptor)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "host": socket.gethostname(),
                       "created_at": datetime.now(timezone.utc).isoformat()}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        # Never remove a lock that has been replaced by another owner.
        safe_path(lock)
        if lock.exists() and os.path.samestat(identity, lock.stat()):
            lock.unlink()


def download(member: Member, destination: Path) -> None:
    """Retry from zero in owned temporary files; publish only verified bytes."""
    safe_path(destination)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".part", dir=destination.parent
        )
        temporary = Path(temporary_name)
        try:
            print(f"Downloading {member.file_id} (attempt {attempt}/{MAX_ATTEMPTS})")
            with os.fdopen(descriptor, "wb") as output:
                request = Request(member.download_url, headers={"User-Agent": USER_AGENT})
                with urlopen(request, timeout=TIMEOUT) as response:
                    if response.status != 200:
                        raise RuntimeError(f"HTTP status {response.status}")
                    downloaded = 0
                    while chunk := response.read(CHUNK_SIZE):
                        downloaded += len(chunk)
                        if downloaded > member.size_bytes:
                            raise RuntimeError("response exceeds pinned size")
                        output.write(chunk)
                        print_progress(downloaded, member.size_bytes)
                output.flush()
                os.fsync(output.fileno())
            print()
            valid, detail = verify_file(temporary, member)
            if not valid:
                raise RuntimeError(f"download verification failed: {detail}")
            safe_path(destination)
            os.replace(temporary, destination)
            return
        except (OSError, RuntimeError, HTTPException) as error:
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(f"{member.file_id}: download failed: {error}") from error
            print(f"  retry: {error}", file=sys.stderr)
            time.sleep(attempt)
        finally:
            temporary.unlink(missing_ok=True)


def receipt_content(binding: DatasetBinding) -> dict:
    return {
        "schema_version": RECEIPT_SCHEMA, "status": "complete",
        "dataset_name": binding.dataset_name,
        "definition_revision": binding.definition_revision,
        "definition_sha256": binding.definition_sha256,
        "release": binding.release, "collection": binding.collection,
        "mc_only": True, "validation_scope": "file_bytes_only",
        "downloader_version": VERSION,
        "members": [dict(asdict(m), actual_size_bytes=m.size_bytes, actual_sha256=m.sha256)
                    for m in binding.members],
    }


def receipt_matches(path: Path, expected: dict) -> bool:
    if not path.exists():
        return False
    try:
        actual = json.loads(path.read_bytes(), object_pairs_hook=_contract.unique_object)
        if not isinstance(actual, dict):
            return False
        timestamp = actual.pop("verified_at")
        if not isinstance(timestamp, str) or datetime.fromisoformat(timestamp).tzinfo is None:
            return False
        return actual == expected
    except (ValueError, KeyError, TypeError):
        return False


def publish_receipt(path: Path, expected: dict) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".receipt.", suffix=".part", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(dict(expected, verified_at=datetime.now(timezone.utc).isoformat()),
                      stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        safe_path(path)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def initialize_pair(data_dir: Path, binding: DatasetBinding, *, force: bool) -> None:
    directory = data_dir / "raw" / binding.dataset_name
    safe_path(directory, directory=True)
    directory.mkdir(parents=True, exist_ok=True)
    receipt = directory / "dataset_receipt.json"
    with dataset_lock(directory):
        safe_path(directory, directory=True)
        safe_path(receipt)
        for member in binding.members:
            safe_path(directory / member.filename)
        valid = [verify_file(directory / m.filename, m) for m in binding.members]
        expected = receipt_content(binding)
        receipt_valid = all(ok for ok, _ in valid) and receipt_matches(receipt, expected)
        if receipt.exists() and not receipt_valid:
            receipt.unlink()
        for member, (ok, detail) in zip(binding.members, valid, strict=True):
            destination = directory / member.filename
            if ok and not force:
                print(f"Skipping {destination}: {detail}")
                continue
            if destination.exists() and not ok and not force:
                raise RuntimeError(f"{destination}: {detail}; rerun with --force")
            download(member, destination)
        for member in binding.members:
            ok, detail = verify_file(directory / member.filename, member)
            if not ok:
                receipt.unlink(missing_ok=True)
                raise RuntimeError(f"final verification failed: {member.file_id}: {detail}")
        if not receipt_valid:
            publish_receipt(receipt, expected)
    print(f"{binding.dataset_name}: complete (file bytes verified)")


def initialize(data_dir: Path, *, force: bool = False, dataset: str | None = None) -> None:
    # Validate every requested definition before making any network request.
    bindings = [load_dataset(name) for name in (DATASET_NAMES if dataset is None else (dataset,))]
    failures = []
    for binding in bindings:
        try:
            initialize_pair(data_dir, binding, force=force)
        except (OSError, RuntimeError, ValueError, HTTPException) as error:
            failures.append(f"{binding.dataset_name}: {error}")
            print(failures[-1], file=sys.stderr)
    if failures:
        raise RuntimeError("; ".join(failures))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and verify pinned same-release MC pairs.")
    parser.add_argument("--dataset", choices=DATASET_NAMES, help="initialize only this complete MC pair")
    parser.add_argument("--force", action="store_true", help="redownload; pinned verification still required")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        initialize(REPOSITORY_ROOT / "data", force=args.force, dataset=args.dataset)
    except (OSError, RuntimeError, ValueError, HTTPException) as error:
        print(f"data initialization failed: {error}", file=sys.stderr)
        return 1
    print("All requested MC dataset pairs completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
