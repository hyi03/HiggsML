from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    ("module", "program_name"),
    [
        ("src.cli.preprocess", "higgsml-preprocess"),
        ("src.cli.train", "higgsml-train"),
        ("src.cli.test", "higgsml-test"),
    ],
)
def test_cli_help(module: str, program_name: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert f"usage: {program_name}" in completed.stdout


@pytest.mark.parametrize(
    "module", ["src.cli.preprocess", "src.cli.train", "src.cli.test"]
)
def test_cli_usage_error_returns_two(module: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", module, "--not-a-real-option"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert (
        "unrecognized arguments" in completed.stderr
        or "the following arguments are required" in completed.stderr
    )


def test_preprocess_requires_protocol_run_config_and_run_dir() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "src.cli.preprocess"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "--protocol" in completed.stderr
    assert "--run-config" in completed.stderr
    assert "--run-dir" in completed.stderr


def test_train_requires_input_protocol_and_run_dir() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "src.cli.train"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "--input-run" in completed.stderr
    assert "--protocol" in completed.stderr
    assert "--run-dir" in completed.stderr


def test_train_help_has_no_removed_subcommands() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "src.cli.train", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "develop" not in completed.stdout
    assert "open-test" not in completed.stdout


def test_test_requires_development_and_run_dir() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "src.cli.test"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "--train-run" in completed.stderr
    assert "--run-dir" in completed.stderr


@pytest.mark.parametrize(
    ("module", "arguments"),
    [
        (
            "src.cli.train",
            [
                "develop",
                "--input-run", "runs/input",
                "--protocol", "protocol.yaml",
                "--run-dir", "runs/output",
            ],
        ),
        (
            "src.cli.train",
            [
                "open-test",
                "--train-run", "runs/development",
                "--run-dir", "runs/test",
            ],
        ),
        (
            "src.cli.test",
            [
                "open-test",
                "--train-run", "runs/development",
                "--run-dir", "runs/test",
            ],
        ),
    ],
)
def test_removed_subcommands_are_rejected(
    module: str, arguments: list[str]
) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", module, *arguments],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2


def test_test_rejects_removed_development_run_option() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.cli.test",
            "--development-run", "runs/development",
            "--run-dir", "runs/test",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
