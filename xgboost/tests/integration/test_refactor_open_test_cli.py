from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from src.cli import xgboost as xgboost_cli
from tests.refactor_training_support import write_eligible_development_run


PROJECT = Path(__file__).resolve().parents[2]


def test_open_test_parser_rejects_all_overrides() -> None:
    parser = xgboost_cli.build_parser()
    base = ["open-test", "--development-run", "development", "--run-dir", "runs/test"]
    for option in (
        "--overwrite", "--protocol", "--model", "--features", "--seed", "--folds",
        "--candidate", "--threshold", "--qualification", "--development-r",
    ):
        try:
            parser.parse_args([*base, option, "value"])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError(f"open-test override was accepted: {option}")


def test_open_test_cli_normalizes_runtime_errors(monkeypatch, capsys) -> None:
    def fail(**kwargs):
        raise ValueError("invalid frozen development run")

    monkeypatch.setattr(xgboost_cli, "run_open_test", fail)
    result = xgboost_cli.main(
        [
            "open-test",
            "--development-run", "development",
            "--run-dir", "runs/test",
        ]
    )
    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert captured.err == (
        "higgsml-xgboost failed: ValueError: invalid frozen development run\n"
    )


def test_module_and_console_open_test_smoke(tmp_path: Path) -> None:
    _, module_development = write_eligible_development_run(tmp_path / "module")
    module_output = tmp_path / "module/runs/test"
    module_result = subprocess.run(
        [
            sys.executable, "-m", "src.cli.xgboost", "open-test",
            "--development-run", str(module_development),
            "--run-dir", str(module_output),
        ],
        cwd=PROJECT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert module_result.returncode == 0, module_result.stderr
    assert module_result.stdout == "succeeded\n"
    assert json.loads(
        (module_output / "artifacts/manifest.json").read_text(encoding="utf-8")
    )["run_type"] == "xgboost_test"

    input_run = Path(
        json.loads(
            (module_development / "artifacts/manifest.json").read_text(encoding="utf-8")
        )["upstream_run"]["path"]
    )
    test_path = input_run / "processed/test.csv.gz"
    damaged = bytearray(test_path.read_bytes())
    damaged[-1] ^= 0x01
    test_path.write_bytes(damaged)
    second_output = tmp_path / "module/runs/test-second"
    second_result = subprocess.run(
        [
            sys.executable, "-m", "src.cli.xgboost", "open-test",
            "--development-run", str(module_development),
            "--run-dir", str(second_output),
        ],
        cwd=PROJECT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert second_result.returncode == 1
    assert "already been opened" in second_result.stderr
    assert (second_output / "failure.json").is_file()
    assert not (second_output / "artifacts/manifest.json").exists()
    assert hashlib.sha256(test_path.read_bytes()).hexdigest() != json.loads(
        (input_run / "artifacts/manifest.json").read_text(encoding="utf-8")
    )["outputs"]["test"]["sha256_compressed"]

    _, console_development = write_eligible_development_run(tmp_path / "console")
    console_output = tmp_path / "console/runs/test"
    executable = Path(sys.executable).with_name(
        "higgsml-xgboost.exe" if sys.platform == "win32" else "higgsml-xgboost"
    )
    console_result = subprocess.run(
        [
            str(executable), "open-test",
            "--development-run", str(console_development),
            "--run-dir", str(console_output),
        ],
        cwd=PROJECT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert console_result.returncode == 0, console_result.stderr
    assert console_result.stdout == "succeeded\n"
