from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    ("module", "program_name"),
    [
        ("src.cli.preprocess", "higgsml-preprocess"),
        ("src.cli.train", "higgsml-train"),
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


@pytest.mark.parametrize("module", ["src.cli.preprocess", "src.cli.train"])
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
