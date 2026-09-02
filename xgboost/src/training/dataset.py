"""Fail-closed reader for the committed M1-02 development artifact."""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import stat
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..preprocessing.pipeline import MODEL_FEATURES, OUTPUT_COLUMNS


@dataclass(frozen=True)
class DevelopmentInput:
    frame: pd.DataFrame
    input_run: Path
    manifest_path: Path
    manifest_bytes: bytes
    manifest_sha256: str
    manifest: Mapping[str, Any]
    upstream_protocol: Mapping[str, Any]
    upstream_run_config: Mapping[str, Any]
    development_path: Path
    development_bytes: bytes
    canonical_csv: bytes


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read_regular_bytes(path: str | Path, label: str) -> bytes:
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


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown or missing:
        raise ValueError(f"{label} keys mismatch; unknown={unknown}, missing={missing}")


def _sha256_identity(value: object, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-fA-F]{64}", value) is None:
        raise ValueError(f"{label} must be a 64-character hexadecimal SHA-256")
    return value.lower()


def _resolve_artifact(input_run: Path, relative_path: object) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("development artifact path must be a non-empty string")
    relative = Path(relative_path)
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise ValueError("development artifact path must be safe and relative")
    if relative.as_posix() != "processed/development.csv.gz":
        raise ValueError("unknown preprocessing development artifact layout")
    destination = input_run.joinpath(*relative.parts)
    resolved_run = input_run.resolve(strict=True)
    resolved = destination.resolve(strict=True)
    if resolved_run not in resolved.parents:
        raise ValueError("development artifact escapes the preprocessing run")
    return destination


def validate_development_frame(frame: pd.DataFrame) -> None:
    if tuple(frame.columns) != OUTPUT_COLUMNS:
        raise ValueError("development CSV must match the frozen 32-column schema")
    if not frame.index.is_unique:
        raise ValueError("development frame index must be unique")
    if frame.empty:
        raise ValueError("development CSV must be non-empty")
    if set(frame["split"]) != {"train", "validation"}:
        raise ValueError("development CSV must contain only train and validation splits")
    labels = frame["label"].to_numpy()
    if set(labels) != {0, 1}:
        raise ValueError("development CSV must contain only Higgs/ZZ labels 1/0")
    numeric_columns = [name for name in OUTPUT_COLUMNS if name != "split"]
    try:
        numeric = frame.loc[:, numeric_columns].to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("development numeric columns have invalid types") from exc
    if not np.isfinite(numeric).all():
        raise ValueError("development numeric columns contain NaN or infinity")
    if frame.duplicated(["channelNumber", "eventNumber"]).any():
        raise ValueError("development event identity must be unique")
    for split in ("train", "validation"):
        if set(frame.loc[frame["split"] == split, "label"]) != {0, 1}:
            raise ValueError(f"development split {split} must contain labels 0 and 1")
    if tuple(frame.columns[: len(MODEL_FEATURES)]) != MODEL_FEATURES:
        raise ValueError("development model features have the wrong order")


def load_development_input(input_run: str | Path) -> DevelopmentInput:
    run = Path(input_run).absolute()
    if run.is_symlink() or not run.is_dir():
        raise ValueError("input_run must be an existing non-symlink directory")
    manifest_path = run / "artifacts" / "manifest.json"
    manifest_bytes = read_regular_bytes(manifest_path, "preprocessing manifest")
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("preprocessing manifest must be valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("preprocessing manifest must be a mapping")
    _require_exact_keys(
        manifest,
        {
            "schema_version", "run_type", "status", "created_at_utc", "protocol",
            "run_config", "code", "software", "luminosity_pb", "inputs", "outputs",
            "counts", "schema",
        },
        "preprocessing manifest",
    )
    if (
        manifest.get("schema_version") != "1.0"
        or manifest.get("run_type") != "mc_preprocessing"
        or manifest.get("status") != "succeeded"
    ):
        raise ValueError("input_run is not a succeeded preprocessing V1 run")
    upstream_protocol = _mapping(manifest.get("protocol"), "preprocessing protocol identity")
    _require_exact_keys(
        upstream_protocol,
        {"path", "schema_version", "sha256"},
        "preprocessing protocol identity",
    )
    if (
        not isinstance(upstream_protocol.get("path"), str)
        or not upstream_protocol["path"]
        or upstream_protocol.get("schema_version") != "1.0"
    ):
        raise ValueError("preprocessing protocol identity is invalid")
    protocol_identity = {
        **dict(upstream_protocol),
        "sha256": _sha256_identity(
            upstream_protocol.get("sha256"), "preprocessing protocol SHA-256"
        ),
    }
    upstream_run_config = _mapping(
        manifest.get("run_config"), "preprocessing run-config identity"
    )
    _require_exact_keys(
        upstream_run_config,
        {"path", "sha256"},
        "preprocessing run-config identity",
    )
    if not isinstance(upstream_run_config.get("path"), str) or not upstream_run_config["path"]:
        raise ValueError("preprocessing run-config identity is invalid")
    run_config_identity = {
        **dict(upstream_run_config),
        "sha256": _sha256_identity(
            upstream_run_config.get("sha256"), "preprocessing run-config SHA-256"
        ),
    }
    outputs = _mapping(manifest.get("outputs"), "preprocessing outputs")
    _require_exact_keys(
        outputs, {"development", "test", "cutflow", "mc_summary"},
        "preprocessing outputs",
    )
    development = _mapping(outputs.get("development"), "development output")
    _require_exact_keys(
        development,
        {
            "path", "rows", "columns", "sha256_compressed",
            "sha256_canonical_csv", "size_bytes",
        },
        "development output",
    )
    held_out = _mapping(outputs.get("test"), "test output")
    _require_exact_keys(
        held_out,
        {
            "path", "rows", "columns", "sha256_compressed",
            "sha256_canonical_csv", "size_bytes",
        },
        "test output",
    )
    if held_out.get("path") != "processed/test.csv.gz":
        raise ValueError("unknown preprocessing test artifact layout")
    development_path = _resolve_artifact(run, development.get("path"))
    compressed = read_regular_bytes(development_path, "development CSV")
    expected_compressed = development.get("sha256_compressed")
    if not isinstance(expected_compressed, str) or _sha256(compressed) != expected_compressed:
        raise ValueError("development compressed SHA-256 does not match manifest")
    try:
        canonical = gzip.decompress(compressed)
    except (gzip.BadGzipFile, EOFError, OSError) as exc:
        raise ValueError("development artifact is not valid gzip") from exc
    expected_canonical = development.get("sha256_canonical_csv")
    if not isinstance(expected_canonical, str) or _sha256(canonical) != expected_canonical:
        raise ValueError("development canonical CSV SHA-256 does not match manifest")
    try:
        frame = pd.read_csv(io.BytesIO(canonical))
    except (UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise ValueError("development artifact is not valid CSV") from exc
    validate_development_frame(frame)
    if development.get("rows") != len(frame):
        raise ValueError("development row count does not match manifest")
    if development.get("columns") != list(OUTPUT_COLUMNS):
        raise ValueError("development columns do not match manifest")
    schema = _mapping(manifest.get("schema"), "preprocessing schema")
    _require_exact_keys(
        schema, {"model_features", "columns", "forbidden_model_features"},
        "preprocessing schema",
    )
    if schema.get("columns") != list(OUTPUT_COLUMNS):
        raise ValueError("preprocessing manifest schema does not match frozen columns")
    if schema.get("model_features") != list(MODEL_FEATURES):
        raise ValueError("preprocessing manifest model features do not match Angular19")
    counts = _mapping(manifest.get("counts"), "preprocessing counts")
    _require_exact_keys(counts, {"development", "test", "total"}, "preprocessing counts")
    count_values = (counts.get("development"), counts.get("test"), counts.get("total"))
    if any(isinstance(value, bool) or not isinstance(value, int) for value in count_values):
        raise ValueError("preprocessing counts must be integers")
    if (
        count_values[0] != len(frame)
        or count_values[1] != held_out.get("rows")
        or count_values[2] != count_values[0] + count_values[1]
    ):
        raise ValueError("preprocessing counts are inconsistent")
    return DevelopmentInput(
        frame=frame,
        input_run=run.resolve(strict=True),
        manifest_path=manifest_path,
        manifest_bytes=manifest_bytes,
        manifest_sha256=_sha256(manifest_bytes),
        manifest=manifest,
        upstream_protocol=protocol_identity,
        upstream_run_config=run_config_identity,
        development_path=development_path,
        development_bytes=compressed,
        canonical_csv=canonical,
    )


def verify_development_input(binding: DevelopmentInput) -> None:
    if read_regular_bytes(binding.manifest_path, "preprocessing manifest") != binding.manifest_bytes:
        raise RuntimeError("preprocessing manifest changed during development")
    if read_regular_bytes(binding.development_path, "development CSV") != binding.development_bytes:
        raise RuntimeError("development CSV changed during development")
