from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable

import pytest

from src.artifacts.manifest import sha256_file, write_json
from src.config import InputBindingError
from src.training.config import INPUT_COLUMNS, load_training_protocol
from src.training.development_reader import _bound_input_run, read_development_input
from tests.development_fixtures import write_synthetic_preprocess_run


PROJECT = Path(__file__).resolve().parents[2]
PROTOCOL = PROJECT / "config/adversarial_mlp_protocol_v1.yaml"


def _manifest_path(run: Path) -> Path:
    return run / "artifacts" / "manifest.json"


def _manifest(run: Path) -> dict[str, Any]:
    return json.loads(_manifest_path(run).read_text(encoding="utf-8"))


def _write_manifest(run: Path, manifest: dict[str, Any]) -> None:
    write_json(_manifest_path(run), manifest)


def _read(run: Path, root: Path):
    protocol = load_training_protocol(PROTOCOL)
    return read_development_input(run, allowed_root=root, protocol_sha256=protocol.sha256)


def _table_record(manifest: dict[str, Any]) -> dict[str, Any]:
    return next(
        item for item in manifest["outputs"] if item["path"] == "processed/mc_events.csv.gz"
    )


def _replace_table_payload(run: Path, payload: bytes, manifest: dict[str, Any]) -> None:
    table = run / "processed" / "mc_events.csv.gz"
    compressed = gzip.compress(payload, compresslevel=9, mtime=0)
    table.write_bytes(compressed)
    record = _table_record(manifest)
    record["sha256"] = hashlib.sha256(compressed).hexdigest()
    record["size_bytes"] = len(compressed)
    record["canonical_content_sha256"] = hashlib.sha256(payload).hexdigest()
    _write_manifest(run, manifest)


def test_reader_surfaces_preprocess_lineage_hashes(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    run, _ = write_synthetic_preprocess_run(root)
    loaded = _read(run, root)
    assert loaded.preprocess_protocol_sha256 == "1" * 64
    assert loaded.preprocess_run_config_sha256 == "2" * 64


def test_input_run_rejects_absolute_and_relative_parent_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "runs"
    (root / "inside").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(InputBindingError, match="outside allowed root"):
        _bound_input_run(root / "inside" / ".." / ".." / "outside", root)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(InputBindingError, match="outside allowed root"):
        _bound_input_run(Path("runs") / "inside" / ".." / ".." / "outside", root)
    with pytest.raises(InputBindingError, match="below allowed root"):
        _bound_input_run(root, root)


def test_input_run_missing_allowed_root_maps_to_binding_error(tmp_path: Path) -> None:
    with pytest.raises(InputBindingError, match="allowed root"):
        _bound_input_run(tmp_path / "missing" / "run", tmp_path / "missing")


def test_input_run_missing_below_existing_root_maps_to_binding_error(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    root.mkdir()
    with pytest.raises(InputBindingError, match="input run does not exist"):
        _bound_input_run(root / "missing", root)


def test_reader_reports_missing_manifest_for_failed_preprocess_run(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    run = root / "failed"
    run.mkdir(parents=True)
    (run / "failure.json").write_text("{}", encoding="utf-8")
    with pytest.raises(InputBindingError, match="preprocess output is missing"):
        _read(run, root)


def test_input_run_rejects_symlink_component_when_supported(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    target = root / "target"
    target.mkdir(parents=True)
    link = root / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
    with pytest.raises(InputBindingError, match="symlink or reparse point"):
        _bound_input_run(link, root)


ManifestMutation = Callable[[dict[str, Any]], None]


def _set(key: str, value: Any) -> ManifestMutation:
    return lambda manifest: manifest.__setitem__(key, value)


def _drop_configuration_hash(manifest: dict[str, Any]) -> None:
    manifest["configuration"].pop("protocol_sha256")


def _bad_configuration_hash(manifest: dict[str, Any]) -> None:
    manifest["configuration"]["run_config_sha256"] = "not-a-sha"


def _drop_schema_dtype(manifest: dict[str, Any]) -> None:
    manifest["schema"]["dtypes"].pop(INPUT_COLUMNS[0])


@pytest.mark.parametrize(
    "mutation",
    [
        _set("schema_version", "2.0"),
        _set("status", "failed"),
        _set("run_type", "development"),
        _set("protocol_id", "changed"),
        _set("inputs", {}),
        _drop_configuration_hash,
        _bad_configuration_hash,
        _drop_schema_dtype,
    ],
)
def test_reader_rejects_manifest_schema_and_lineage_mutations(
    tmp_path: Path, mutation: ManifestMutation
) -> None:
    root = tmp_path / "runs"
    run, _ = write_synthetic_preprocess_run(root)
    manifest = _manifest(run)
    mutation(manifest)
    _write_manifest(run, manifest)
    with pytest.raises(InputBindingError, match="manifest binding changed"):
        _read(run, root)


@pytest.mark.parametrize("field", ["sha256", "size_bytes", "row_count", "canonical_content_sha256"])
def test_reader_rejects_output_receipt_mutations(tmp_path: Path, field: str) -> None:
    root = tmp_path / "runs"
    run, _ = write_synthetic_preprocess_run(root)
    manifest = _manifest(run)
    record = _table_record(manifest)
    record[field] = {
        "sha256": "0" * 64,
        "size_bytes": record["size_bytes"] + 1,
        "row_count": True,
        "canonical_content_sha256": "f" * 64,
    }[field]
    _write_manifest(run, manifest)
    with pytest.raises(InputBindingError):
        _read(run, root)


def test_reader_rejects_output_path_traversal_and_output_set_drift(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    run, _ = write_synthetic_preprocess_run(root)
    manifest = _manifest(run)
    manifest["outputs"][0]["path"] = "../config.yaml"
    _write_manifest(run, manifest)
    with pytest.raises(InputBindingError, match="output path changed"):
        _read(run, root)

    root2 = tmp_path / "runs-2"
    run2, _ = write_synthetic_preprocess_run(root2)
    manifest2 = _manifest(run2)
    manifest2["outputs"].pop()
    _write_manifest(run2, manifest2)
    with pytest.raises(InputBindingError, match="output set changed"):
        _read(run2, root2)


@pytest.mark.parametrize("split", [b"", b"unknown"])
def test_reader_rejects_empty_or_unknown_split_before_other_decode(
    tmp_path: Path, split: bytes
) -> None:
    root = tmp_path / "runs"
    run, _ = write_synthetic_preprocess_run(root)
    manifest = _manifest(run)
    payload = gzip.decompress((run / "processed" / "mc_events.csv.gz").read_bytes())
    lines = payload.splitlines(keepends=True)
    split_index = INPUT_COLUMNS.index("split")
    tokens = lines[1].rstrip(b"\n").split(b",")
    tokens[split_index] = split
    tokens[0] = b"must-not-be-decoded"
    lines[1] = b",".join(tokens) + b"\n"
    _replace_table_payload(run, b"".join(lines), manifest)
    with pytest.raises(InputBindingError, match="split token is invalid") as captured:
        _read(run, root)
    assert "must-not-be-decoded" not in str(captured.value)


def test_reader_rejects_header_count_and_duplicate_identity_drift(tmp_path: Path) -> None:
    root = tmp_path / "runs-header"
    run, _ = write_synthetic_preprocess_run(root)
    manifest = _manifest(run)
    payload = gzip.decompress((run / "processed" / "mc_events.csv.gz").read_bytes())
    lines = payload.splitlines(keepends=True)
    lines[0] = lines[0].replace(b"lep1_pt", b"changed", 1)
    _replace_table_payload(run, b"".join(lines), manifest)
    with pytest.raises(InputBindingError, match="header changed"):
        _read(run, root)

    root2 = tmp_path / "runs-count"
    run2, _ = write_synthetic_preprocess_run(root2)
    manifest2 = _manifest(run2)
    manifest2["counts"]["totals"]["selected_count"] += 1
    _write_manifest(run2, manifest2)
    with pytest.raises(InputBindingError, match="split counts changed"):
        _read(run2, root2)

    root3 = tmp_path / "runs-identity"
    run3, _ = write_synthetic_preprocess_run(root3)
    manifest3 = _manifest(run3)
    payload3 = gzip.decompress((run3 / "processed" / "mc_events.csv.gz").read_bytes())
    lines3 = payload3.splitlines(keepends=True)
    entry_index = INPUT_COLUMNS.index("source_entry")
    first = lines3[1].rstrip(b"\n").split(b",")
    second = lines3[2].rstrip(b"\n").split(b",")
    second[entry_index] = first[entry_index]
    lines3[2] = b",".join(second) + b"\n"
    _replace_table_payload(run3, b"".join(lines3), manifest3)
    with pytest.raises(InputBindingError, match="identity must be unique"):
        _read(run3, root3)


def test_reader_rejects_corrupt_gzip_with_no_row_or_value_in_error(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    run, _ = write_synthetic_preprocess_run(root)
    table = run / "processed" / "mc_events.csv.gz"
    table.write_bytes(b"not-gzip")
    manifest = _manifest(run)
    record = _table_record(manifest)
    record["sha256"] = sha256_file(table)
    record["size_bytes"] = table.stat().st_size
    _write_manifest(run, manifest)
    with pytest.raises(InputBindingError, match="gzip is invalid") as captured:
        _read(run, root)
    assert "not-gzip" not in str(captured.value)
