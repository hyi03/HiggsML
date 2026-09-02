"""Application service for one immutable MC preprocessing run."""

from __future__ import annotations

from datetime import datetime, timezone
import gzip
import hashlib
from importlib import metadata
from pathlib import Path
import platform
import stat
import subprocess
from typing import Any, Mapping

import pandas as pd

from ..artifacts.manifest import canonical_json_bytes
from ..artifacts.transaction import RunTransaction
from ..config import load_preprocessing_protocol, load_preprocessing_run_config
from .pipeline import LUMINOSITY_PB, OUTPUT_COLUMNS, build_preprocessed_dataset
from .reader import InputReceipt, inspect_mc_input, verify_mc_input


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read_regular_input(path: str | Path, label: str) -> bytes:
    source = Path(path).absolute()
    if source.is_symlink():
        raise ValueError(f"symlink {label} inputs are not allowed")
    try:
        source_stat = source.lstat()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"{label} does not exist: {source}") from exc
    if not stat.S_ISREG(source_stat.st_mode):
        raise ValueError(f"{label} must be a regular file")
    return source.read_bytes()


def _canonical_csv(frame: pd.DataFrame) -> bytes:
    if tuple(frame.columns) != OUTPUT_COLUMNS:
        raise ValueError("preprocessing output schema does not match the frozen column order")
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _csv_artifact(frame: pd.DataFrame) -> tuple[bytes, dict[str, Any]]:
    canonical = _canonical_csv(frame)
    compressed = gzip.compress(canonical, compresslevel=9, mtime=0)
    return compressed, {
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "sha256_compressed": _sha256(compressed),
        "sha256_canonical_csv": _sha256(canonical),
        "size_bytes": len(compressed),
    }


def _git_identity(project_root: Path) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("unable to bind preprocessing run to Git code identity") from exc
    return {"commit": commit, "worktree_dirty": dirty}


def _code_sha256(project_root: Path) -> str:
    digest = hashlib.sha256()
    sources = [
        project_root / "src" / "__init__.py",
        project_root / "src" / "config.py",
        *(project_root / "src" / "artifacts").glob("*.py"),
        project_root / "src" / "cli" / "__init__.py",
        project_root / "src" / "cli" / "preprocess.py",
        *(project_root / "src" / "domain").glob("*.py"),
        *(project_root / "src" / "preprocessing").glob("*.py"),
    ]
    for path in sorted(sources, key=lambda item: item.as_posix()):
        relative = path.relative_to(project_root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _software_versions() -> dict[str, str]:
    distributions = {
        "numpy": "numpy",
        "pandas": "pandas",
        "pyyaml": "PyYAML",
        "uproot": "uproot",
        "awkward": "awkward",
        "vector": "vector",
    }
    versions = {"python": platform.python_version()}
    for name, distribution in distributions.items():
        try:
            versions[name] = metadata.version(distribution)
        except metadata.PackageNotFoundError as exc:
            raise RuntimeError(f"required distribution is not installed: {distribution}") from exc
    return versions


def _input_payload(receipts: Mapping[str, InputReceipt]) -> dict[str, Any]:
    return {name: receipt.as_dict() for name, receipt in receipts.items()}


def run_preprocessing(
    *,
    protocol_path: str | Path,
    run_config_path: str | Path,
    run_dir: str | Path,
) -> Mapping[str, Any]:
    protocol_source = Path(protocol_path).absolute()
    run_config_source = Path(run_config_path).absolute()
    protocol_bytes = _read_regular_input(protocol_source, "preprocessing protocol")
    run_config_bytes = _read_regular_input(run_config_source, "preprocessing run config")
    protocol = load_preprocessing_protocol(protocol_source)
    run_config = load_preprocessing_run_config(run_config_source)
    destination = Path(run_dir).absolute()
    if destination.parent.name != "runs":
        raise ValueError("run directory must be a direct child of a named runs root")
    project_root = Path(__file__).resolve().parents[2]

    with RunTransaction(destination, runs_root=destination.parent) as transaction:
        receipts = {
            "higgs": inspect_mc_input(run_config.higgs_root),
            "zz": inspect_mc_input(run_config.zz_root),
        }
        dataset = build_preprocessed_dataset(
            protocol=protocol.raw,
            higgs_root=receipts["higgs"].path,
            zz_root=receipts["zz"].path,
            chunk_size_events=run_config.chunk_size_events,
        )
        for receipt in receipts.values():
            verify_mc_input(receipt)
        if _read_regular_input(protocol_source, "preprocessing protocol") != protocol_bytes:
            raise RuntimeError("preprocessing protocol changed during the run")
        if _read_regular_input(run_config_source, "preprocessing run config") != run_config_bytes:
            raise RuntimeError("preprocessing run config changed during the run")

        development_bytes, development_receipt = _csv_artifact(dataset.development)
        test_bytes, test_receipt = _csv_artifact(dataset.test)
        transaction.write_bytes("config.yaml", run_config_bytes)
        transaction.write_bytes("processed/development.csv.gz", development_bytes)
        transaction.write_bytes("processed/test.csv.gz", test_bytes)
        transaction.write_bytes(
            "artifacts/cutflow.json", canonical_json_bytes(dataset.cutflow)
        )
        transaction.write_bytes(
            "artifacts/mc_summary.json", canonical_json_bytes(dataset.summary)
        )

        manifest: dict[str, Any] = {
            "schema_version": "1.0",
            "run_type": "mc_preprocessing",
            "status": "succeeded",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "protocol": {
                "path": str(protocol_source.resolve(strict=True)),
                "schema_version": protocol.raw["schema_version"],
                "sha256": _sha256(protocol_bytes),
            },
            "run_config": {
                "path": str(run_config_source.resolve(strict=True)),
                "sha256": _sha256(run_config_bytes),
            },
            "code": {
                **_git_identity(project_root),
                "sha256": _code_sha256(project_root),
            },
            "software": _software_versions(),
            "luminosity_pb": LUMINOSITY_PB,
            "inputs": _input_payload(receipts),
            "outputs": {
                "development": {
                    "path": "processed/development.csv.gz",
                    **development_receipt,
                },
                "test": {"path": "processed/test.csv.gz", **test_receipt},
                "cutflow": "artifacts/cutflow.json",
                "mc_summary": "artifacts/mc_summary.json",
            },
            "counts": {
                "development": len(dataset.development),
                "test": len(dataset.test),
                "total": len(dataset.development) + len(dataset.test),
            },
            "schema": {
                "model_features": list(protocol.model_features),
                "columns": list(OUTPUT_COLUMNS),
                "forbidden_model_features": list(protocol.raw["forbidden_features"]),
            },
        }
        transaction.publish_manifest(manifest, "artifacts/manifest.json")
        return manifest
