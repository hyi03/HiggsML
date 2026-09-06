from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.artifacts.manifest import sha256_file
from src.config import InputBindingError
from src.dataset_binding import validate_dataset_snapshot
from src.resource_seals import RESOURCE_HASHES
from src.training.config import INPUT_COLUMNS
from src.training.dataset import ValidatedDevelopment, validate_development_frame


_INTEGER_COLUMNS = {"label", "source_entry", "runNumber", "eventNumber", "channelNumber"}
_TEXT_COLUMNS = {"split", "source_sample", "source_file_id", "event_group_id"}
_REPARSE_POINT = 0x400


@dataclass(frozen=True)
class DevelopmentInput:
    development: ValidatedDevelopment
    input_manifest_sha256: str
    input_table_sha256: str
    input_canonical_content_sha256: str
    preprocess_protocol_sha256: str
    preprocess_run_config_sha256: str
    total_rows: int
    development_rows: int
    held_out_test_rows: int


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(path)):
        return True
    try:
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & _REPARSE_POINT)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise InputBindingError("input run path cannot be inspected") from error


def _bound_input_run(input_run: str | Path, allowed_root: str | Path) -> Path:
    try:
        root = Path(allowed_root).resolve(strict=True)
    except OSError as error:
        raise InputBindingError("input allowed root does not exist") from error
    requested = Path(input_run)
    if ".." in requested.parts:
        raise InputBindingError("input run is outside allowed root")
    absolute = requested if requested.is_absolute() else Path.cwd() / requested
    try:
        relative = absolute.absolute().relative_to(root)
    except ValueError as error:
        raise InputBindingError("input run is outside allowed root") from error
    current = root
    for part in relative.parts:
        current = current / part
        if _is_link_or_reparse(current):
            raise InputBindingError("input run contains a symlink or reparse point")
    try:
        resolved = absolute.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise InputBindingError("input run does not exist") from error
    if not resolved.is_dir() or resolved == root:
        raise InputBindingError("input run must be a directory below allowed root")
    return resolved


def _plain_descendant(run: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise InputBindingError("preprocess output path changed")
    current = run
    for part in relative.parts:
        current = current / part
        if _is_link_or_reparse(current):
            raise InputBindingError("preprocess output contains a symlink or reparse point")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(run)
    except (OSError, ValueError) as error:
        raise InputBindingError("preprocess output is missing or outside input run") from error
    return resolved


def _read_manifest(run: Path, *, debug: bool = False) -> tuple[dict[str, Any], str]:
    path = _plain_descendant(run, Path("artifacts/manifest.json"))
    try:
        payload = path.read_bytes()
        manifest = json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InputBindingError("preprocess manifest cannot be loaded") from error
    required_keys = {
        "dataset_binding", "schema_version", "status", "run_type", "protocol_id", "started_at_utc",
        "completed_at_utc", "inputs", "configuration", "outputs", "schema", "counts",
        "software", "platform", "determinism", "performance",
    }
    schema = manifest.get("schema") if isinstance(manifest, dict) else None
    configuration = manifest.get("configuration") if isinstance(manifest, dict) else None
    configuration_keys = {
        "protocol_path", "protocol_sha256", "run_config_path", "run_config_sha256",
        "chunk_size_events", "full_read",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != required_keys
        or manifest.get("schema_version") != "2.0"
        or manifest.get("status") != "success"
        or manifest.get("run_type") != "preprocess"
        or (not debug and manifest.get("protocol_id") != "higgsml-preprocess-v2")
        or (debug and type(manifest.get("protocol_id")) is not str)
        or not isinstance(manifest.get("inputs"), list)
        or not isinstance(manifest.get("outputs"), list)
        or not isinstance(configuration, dict)
        or set(configuration) != configuration_keys
        or type(configuration.get("protocol_path")) is not str
        or type(configuration.get("run_config_path")) is not str
        or (not debug
            and configuration.get("protocol_sha256") != RESOURCE_HASHES["preprocess_protocol_v2.yaml"])
        or (not debug and not _is_sha256(configuration.get("run_config_sha256")))
        or (debug and type(configuration.get("run_config_sha256")) is not str)
        or type(configuration.get("chunk_size_events")) is not int
        or configuration.get("chunk_size_events", 0) <= 0
        or configuration.get("full_read") is not True
        or not isinstance(schema, dict)
        or set(schema) != {"ordered_columns", "dtypes"}
        or schema.get("ordered_columns") != list(INPUT_COLUMNS)
        or not isinstance(schema.get("dtypes"), dict)
        or tuple(schema["dtypes"]) != INPUT_COLUMNS
    ):
        raise InputBindingError("preprocess manifest binding changed")
    validate_dataset_snapshot(manifest["dataset_binding"])
    return manifest, hashlib.sha256(payload).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _output_records(run: Path, manifest: dict[str, Any], *, debug: bool = False) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for record in manifest["outputs"]:
        if (
            not isinstance(record, dict)
            or set(record) != {"path", "sha256", "size_bytes", "row_count", "canonical_content_sha256"}
            or type(record.get("path")) is not str
        ):
            raise InputBindingError("preprocess output record changed")
        logical = record["path"]
        relative = Path(logical)
        if relative.is_absolute() or ".." in relative.parts or logical in records:
            raise InputBindingError("preprocess output path changed")
        expected_sha = record.get("sha256")
        size_bytes = record.get("size_bytes")
        row_count = record.get("row_count")
        canonical_sha = record.get("canonical_content_sha256")
        if (
            (not debug and not _is_sha256(expected_sha))
            or (debug and type(expected_sha) is not str)
            or type(size_bytes) is not int
            or size_bytes < 0
            or (row_count is not None and (type(row_count) is not int or row_count < 0))
            or (not debug and canonical_sha is not None and not _is_sha256(canonical_sha))
            or (debug and canonical_sha is not None and type(canonical_sha) is not str)
        ):
            raise InputBindingError("preprocess output SHA-256 changed")
        if logical != "processed/test_events.csv.gz":
            target = _plain_descendant(run, relative)
            if not target.is_file():
                raise InputBindingError("preprocess output is missing or linked")
            if not debug and (target.stat().st_size != size_bytes or sha256_file(target) != expected_sha):
                raise InputBindingError("preprocess output SHA-256 changed")
        records[logical] = record
    required = {
        "config.yaml",
        "processed/development_events.csv.gz",
        "processed/test_events.csv.gz",
        "artifacts/cutflow.json",
        "artifacts/mc_summary.json",
    }
    if set(records) != required:
        raise InputBindingError("preprocess output set changed")
    return records


def _canonical_content_sha256(table: Path) -> str:
    digest = hashlib.sha256()
    try:
        with gzip.open(table, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except (OSError, EOFError) as error:
        raise InputBindingError("preprocess table gzip is invalid") from error
    return digest.hexdigest()


def _field_token(line: bytes, index: int) -> bytes:
    start = 0
    for _ in range(index):
        delimiter = line.find(b",", start)
        if delimiter < 0:
            raise InputBindingError("preprocess row is missing split routing field")
        start = delimiter + 1
    end = line.find(b",", start)
    if end < 0:
        end = len(line.rstrip(b"\r\n"))
    return line[start:end]


def _development_frame(table: Path, *, expected_rows: int) -> tuple[pd.DataFrame, int]:
    header = b",".join(name.encode("utf-8") for name in INPUT_COLUMNS) + b"\n"
    split_index = INPUT_COLUMNS.index("split")
    approved = bytearray(header)
    total_rows = 0
    test_rows = 0
    try:
        with gzip.open(table, "rb") as stream:
            if stream.readline() != header:
                raise InputBindingError("preprocess table header changed")
            for line in stream:
                total_rows += 1
                try:
                    split = _field_token(line, split_index).decode("ascii")
                except UnicodeError as error:
                    raise InputBindingError("preprocess split token is invalid") from error
                if split == "test":
                    raise InputBindingError("test row in development partition")
                if split not in {"train", "validation"}:
                    raise InputBindingError("preprocess split token is invalid")
                approved.extend(line)
    except InputBindingError:
        raise
    except (OSError, EOFError) as error:
        raise InputBindingError("preprocess table cannot be routed") from error
    if total_rows != expected_rows or total_rows == 0 or len(approved) == len(header):
        raise InputBindingError("preprocess table row count changed")
    return _decode_development_rows(bytes(approved)), test_rows


def _decode_development_rows(payload: bytes) -> pd.DataFrame:
    dtypes = {
        name: ("int64" if name in _INTEGER_COLUMNS else "object" if name in _TEXT_COLUMNS else "float64")
        for name in INPUT_COLUMNS
    }
    try:
        frame = pd.read_csv(io.BytesIO(payload), dtype=dtypes)
    except (ValueError, TypeError, UnicodeError) as error:
        raise InputBindingError("development rows cannot be decoded") from error
    return frame


def read_development_input(
    input_run: str | Path,
    *,
    allowed_root: str | Path,
    dataset: str,
    protocol_sha256: str,
    debug: bool = False,
) -> DevelopmentInput:
    run = _bound_input_run(input_run, allowed_root)
    manifest, manifest_sha = _read_manifest(run, debug=debug)
    validate_dataset_snapshot(manifest["dataset_binding"], dataset)
    records = _output_records(run, manifest, debug=debug)
    try:
        snapshot = yaml.safe_load((run / "config.yaml").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise InputBindingError("preprocess configuration snapshot cannot be loaded") from error
    if (not isinstance(snapshot, dict)
            or snapshot.get("dataset_binding") != manifest["dataset_binding"]
            or (not debug and snapshot.get("protocol_sha256") != manifest["configuration"]["protocol_sha256"])
            or (not debug and snapshot.get("run_config_sha256") != manifest["configuration"]["run_config_sha256"])):
        raise InputBindingError("preprocess configuration snapshot binding changed")
    table_record = records["processed/development_events.csv.gz"]
    expected_rows = table_record.get("row_count")
    canonical_sha = table_record.get("canonical_content_sha256")
    if type(expected_rows) is not int or expected_rows <= 0 or type(canonical_sha) is not str:
        raise InputBindingError("preprocess table receipt changed")
    table = run / "processed" / "development_events.csv.gz"
    if not debug and _canonical_content_sha256(table) != canonical_sha:
        raise InputBindingError("preprocess canonical content SHA-256 changed")
    frame, _ = _development_frame(table, expected_rows=expected_rows)
    test_rows = records["processed/test_events.csv.gz"]["row_count"]
    if type(test_rows) is not int or test_rows < 0:
        raise InputBindingError("test partition count changed")
    try:
        totals = manifest["counts"]["totals"]
        split_counts = totals["split_counts"]
    except (KeyError, TypeError) as error:
        raise InputBindingError("preprocess manifest counts changed") from error
    if (
        totals.get("selected_count") != expected_rows + test_rows
        or split_counts.get("test") != test_rows
        or split_counts.get("train", 0) + split_counts.get("validation", 0) != len(frame)
    ):
        raise InputBindingError("preprocess manifest split counts changed")
    development = validate_development_frame(
        frame, protocol_sha256=protocol_sha256,
        dataset_binding=manifest["dataset_binding"], debug=debug,
    )
    configuration = manifest["configuration"]
    return DevelopmentInput(
        development=development,
        input_manifest_sha256=manifest_sha,
        input_table_sha256=str(table_record["sha256"]),
        input_canonical_content_sha256=canonical_sha,
        preprocess_protocol_sha256=configuration["protocol_sha256"],
        preprocess_run_config_sha256=configuration["run_config_sha256"],
        total_rows=expected_rows + test_rows,
        development_rows=len(frame),
        held_out_test_rows=test_rows,
    )
