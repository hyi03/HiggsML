from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from src.cli import xgboost as xgboost_cli
from src.training import dataset as training_dataset
from src.training import trainer as training_trainer
from src.training.trainer import run_development
from tests.refactor_training_support import (
    development_frame,
    fake_factory,
    write_preprocess_run,
)


PROJECT = Path(__file__).resolve().parents[2]


def test_development_run_publishes_frozen_layout_without_opening_test(
    tmp_path: Path, monkeypatch
) -> None:
    frame = development_frame()
    frame["m4l"] = 125.0
    input_run = write_preprocess_run(tmp_path, frame)
    runs = tmp_path / "runs"
    runs.mkdir()
    output = runs / "development-1"
    test_path = (input_run / "processed/test.csv.gz").absolute()
    original = Path.read_bytes
    opened: list[Path] = []

    def deny_test(path: Path) -> bytes:
        opened.append(path.absolute())
        if path.absolute() == test_path:
            raise AssertionError("held-out test was opened by run_development")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", deny_test)

    manifest = run_development(
        input_run=input_run,
        protocol_path=PROJECT / "config/xgboost_protocol_v1.yaml",
        run_dir=output,
        model_factory=fake_factory,
    )

    assert manifest["test_opened"] is False
    expected = {
        "config.yaml",
        "artifacts/candidate_metrics.csv",
        "artifacts/fold_metrics.csv",
        "artifacts/qualification.json",
        "artifacts/working_points.json",
        "artifacts/manifest.json",
        "predictions/oof_scores.csv.gz",
        "plots/oof_scores.png",
        "model/model.json",
    }
    files = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
    assert files == expected
    assert test_path not in opened
    assert "state/test_opening.json" not in files
    qualification = json.loads((output / "artifacts/qualification.json").read_text(encoding="utf-8"))
    assert qualification["eligible"] is True
    assert (output / "model/model.json").is_file()
    assert manifest["upstream_run"]["protocol"] == {
        "path": "preprocessing_protocol_v1.yaml",
        "schema_version": "1.0",
        "sha256": "a" * 64,
    }
    assert manifest["upstream_run"]["run_config"] == {
        "path": "local.yaml",
        "sha256": "b" * 64,
    }


def test_no_eligible_run_has_no_model_or_test_claim(tmp_path: Path) -> None:
    input_run = write_preprocess_run(tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    output = runs / "not-eligible"

    manifest = run_development(
        input_run=input_run,
        protocol_path=PROJECT / "config/xgboost_protocol_v1.yaml",
        run_dir=output,
        model_factory=fake_factory,
    )

    assert manifest["status"] == "no_eligible_candidate"
    assert not (output / "model").exists()
    assert not (output / "state/test_opening.json").exists()
    files = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
    assert files == {
        "config.yaml",
        "artifacts/candidate_metrics.csv",
        "artifacts/fold_metrics.csv",
        "artifacts/qualification.json",
        "artifacts/working_points.json",
        "artifacts/manifest.json",
        "predictions/oof_scores.csv.gz",
        "plots/oof_scores.png",
    }


def test_occupied_output_is_rejected_before_any_input_read(
    tmp_path: Path, monkeypatch
) -> None:
    input_run = write_preprocess_run(tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    output = runs / "occupied"
    output.mkdir()
    marker = output / "user-owned.txt"
    marker.write_text("preserve", encoding="utf-8")

    def deny_read(*args, **kwargs):
        pytest.fail("occupied output attempted to read an input")

    monkeypatch.setattr(training_trainer, "read_regular_bytes", deny_read)
    monkeypatch.setattr(training_dataset, "read_regular_bytes", deny_read)

    with pytest.raises(FileExistsError):
        run_development(
            input_run=input_run,
            protocol_path=PROJECT / "config/xgboost_protocol_v1.yaml",
            run_dir=output,
            model_factory=fake_factory,
        )

    assert marker.read_text(encoding="utf-8") == "preserve"
    assert {path.name for path in output.iterdir()} == {"user-owned.txt"}


def test_tampered_input_writes_failure_without_success_manifest(tmp_path: Path) -> None:
    input_run = write_preprocess_run(tmp_path)
    development = input_run / "processed/development.csv.gz"
    development.write_bytes(development.read_bytes() + b"tamper")
    runs = tmp_path / "runs"
    runs.mkdir()
    output = runs / "failed"

    try:
        run_development(
            input_run=input_run,
            protocol_path=PROJECT / "config/xgboost_protocol_v1.yaml",
            run_dir=output,
            model_factory=fake_factory,
        )
    except ValueError as exc:
        assert "compressed SHA-256" in str(exc)
    else:
        raise AssertionError("tampered development input was accepted")
    assert (output / "failure.json").is_file()
    assert not (output / "artifacts/manifest.json").exists()


def test_develop_parser_rejects_scientific_overrides() -> None:
    from src.cli.xgboost import build_parser

    parser = build_parser()
    for option in ("--overwrite", "--seed", "--folds", "--threshold", "--features"):
        try:
            parser.parse_args(["develop", "--input-run", "in", "--protocol", "p", "--run-dir", "out", option, "1"])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError(f"scientific override was accepted: {option}")


def test_develop_cli_normalizes_runtime_errors(monkeypatch, capsys) -> None:
    def fail(**kwargs):
        raise ValueError("invalid development input")

    monkeypatch.setattr(xgboost_cli, "run_development", fail)
    result = xgboost_cli.main(
        [
            "develop",
            "--input-run", "input",
            "--protocol", "protocol",
            "--run-dir", "runs/output",
        ]
    )

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert captured.err == (
        "higgsml-xgboost failed: ValueError: invalid development input\n"
    )


def test_real_xgboost_micro_development_smoke(tmp_path: Path) -> None:
    input_run = write_preprocess_run(tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    output = runs / "real-xgboost"

    result = subprocess.run(
        [
            sys.executable, "-m", "src.cli.xgboost", "develop",
            "--input-run", str(input_run),
            "--protocol", str(PROJECT / "config/xgboost_protocol_v1.yaml"),
            "--run-dir", str(output),
        ],
        cwd=PROJECT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / "artifacts/manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] in {"eligible", "no_eligible_candidate"}
    assert manifest["counts"]["development"] == 30
    assert (output / "artifacts/manifest.json").is_file()
