from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from src.cli import train as train_cli
from src.config import (
    ExitCode,
    InputBindingError,
    TestOpeningFailure as OpeningFailure,
    TestOpeningRefused as OpeningRefused,
)
from src.training.development import execute_development
from tests.development_fixtures import write_synthetic_preprocess_run
from tests.integration.test_development_run import _install_fast_pipeline


PROJECT = Path(__file__).resolve().parents[2]
PROTOCOL = PROJECT / "config/adversarial_mlp_protocol_normal.yaml"


def test_open_test_requires_all_three_arguments() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "src.cli.train", "open-test"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == int(ExitCode.USAGE)
    assert "--development-run" in completed.stderr
    assert "--run-dir" in completed.stderr
    assert "--authorization-reference" in completed.stderr


def test_blank_authorization_value_returns_refusal(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.cli.train",
            "open-test",
            "--development-run",
            "runs/missing",
            "--run-dir",
            "runs/output",
            "--authorization-reference",
            " ",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert completed.returncode == int(ExitCode.REFUSED)


def test_open_test_cli_runs_only_synthetic_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    allowed_root = tmp_path / "runs"
    preprocess, _ = write_synthetic_preprocess_run(allowed_root)
    _install_fast_pipeline(monkeypatch, eligible_lambda=0.0)
    development = allowed_root / "eligible-development"
    execute_development(
        input_run=preprocess,
        protocol_path=PROTOCOL,
        run_dir=development,
        allowed_root=allowed_root,
    )

    code = train_cli.main(
        [
            "open-test",
            "--development-run",
            str(development),
            "--run-dir",
            str(allowed_root / "test-opening"),
            "--authorization-reference",
            "synthetic-fixture-only",
        ]
    )
    assert code == int(ExitCode.SUCCESS)
    assert (allowed_root / "test-opening/artifacts/manifest.json").is_file()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (OpeningRefused("refused"), ExitCode.REFUSED),
        (InputBindingError("binding"), ExitCode.INPUT_BINDING),
        (OpeningFailure("output_transaction", ExitCode.TRANSACTION), ExitCode.TRANSACTION),
        (RuntimeError("unexpected"), ExitCode.INTERNAL_ERROR),
    ],
)
def test_open_test_cli_exit_mapping(
    monkeypatch: pytest.MonkeyPatch, error: Exception, expected: ExitCode
) -> None:
    monkeypatch.setattr(
        train_cli,
        "execute_test_opening",
        lambda **kwargs: (_ for _ in ()).throw(error),
    )
    code = train_cli.main(
        [
            "open-test",
            "--development-run",
            "runs/development",
            "--run-dir",
            "runs/test",
            "--authorization-reference",
            "synthetic-fixture-only",
        ]
    )
    assert code == int(expected)


def test_terminal_receipt_cli_log_requires_manual_audit(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        train_cli,
        "execute_test_opening",
        lambda **kwargs: (_ for _ in ()).throw(
            OpeningFailure("terminal_receipt", ExitCode.TRANSACTION)
        ),
    )
    code = train_cli.main(
        [
            "open-test",
            "--development-run",
            "runs/development",
            "--run-dir",
            "runs/test",
            "--authorization-reference",
            "synthetic-fixture-only",
        ]
    )
    assert code == int(ExitCode.TRANSACTION)
    assert "manual audit required" in caplog.text
    assert "runs/test" in caplog.text


def test_open_test_input_binding_log_is_stage_and_run_aware(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        train_cli,
        "execute_test_opening",
        lambda **kwargs: (_ for _ in ()).throw(InputBindingError("hidden detail")),
    )
    code = train_cli.main(
        [
            "open-test",
            "--development-run",
            "runs/development",
            "--run-dir",
            "runs/test",
            "--authorization-reference",
            "synthetic-fixture-only",
        ]
    )

    assert code == int(ExitCode.INPUT_BINDING)
    assert "stage=input_binding" in caplog.text
    assert "runs/test" in caplog.text
    assert "hidden detail" not in caplog.text
