from __future__ import annotations

from pathlib import Path
import json

import pytest

from src.preprocessing.pipeline import OUTPUT_COLUMNS
from src.training.dataset import load_development_input
from tests.refactor_training_support import development_frame, write_preprocess_run


def test_loader_binds_committed_schema_and_never_reads_test(tmp_path: Path, monkeypatch) -> None:
    run = write_preprocess_run(tmp_path)
    test_path = run / "processed" / "test.csv.gz"
    original = Path.read_bytes
    opened: list[Path] = []

    def spy(path: Path) -> bytes:
        opened.append(path.absolute())
        if path.absolute() == test_path.absolute():
            raise AssertionError("held-out test was opened")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", spy)
    loaded = load_development_input(run)

    assert tuple(loaded.frame.columns) == OUTPUT_COLUMNS
    assert set(loaded.frame["split"]) == {"train", "validation"}
    assert test_path.absolute() not in opened


def test_loader_rejects_tampered_development_bytes(tmp_path: Path) -> None:
    run = write_preprocess_run(tmp_path)
    path = run / "processed" / "development.csv.gz"
    path.write_bytes(path.read_bytes() + b"tamper")

    with pytest.raises(ValueError, match="compressed SHA-256"):
        load_development_input(run)


def test_loader_rejects_unknown_upstream_manifest_fields(tmp_path: Path) -> None:
    run = write_preprocess_run(tmp_path)
    path = run / "artifacts" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["unknown"] = True
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="keys mismatch"):
        load_development_input(run)


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    (
        ("protocol", "sha256", "not-a-sha", "protocol SHA-256"),
        ("protocol", "schema_version", "2.0", "protocol identity"),
        ("run_config", "sha256", "g" * 64, "run-config SHA-256"),
    ),
)
def test_loader_rejects_invalid_upstream_identity(
    tmp_path: Path,
    section: str,
    field: str,
    value: str,
    message: str,
) -> None:
    run = write_preprocess_run(tmp_path)
    path = run / "artifacts" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest[section][field] = value
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_development_input(run)


@pytest.mark.parametrize("split", ("train", "validation"))
def test_loader_requires_both_labels_in_each_development_split(
    tmp_path: Path, split: str
) -> None:
    frame = development_frame()
    frame.loc[frame["split"] == split, "label"] = 0
    run = write_preprocess_run(tmp_path, frame)

    with pytest.raises(ValueError, match=rf"split {split} must contain labels 0 and 1"):
        load_development_input(run)
