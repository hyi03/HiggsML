from __future__ import annotations

import subprocess
import sys
from importlib.metadata import distribution

import pytest


@pytest.mark.parametrize("module", ["src.cli.preprocess", "src.cli.xgboost"])
def test_cli_modules_expose_help(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


@pytest.mark.parametrize(
    "module, arguments, expected",
    [
        ("src.cli.preprocess", [], 2),
        ("src.cli.preprocess", ["--unknown"], 2),
        ("src.cli.xgboost", [], 2),
        ("src.cli.xgboost", ["--unknown"], 2),
        (
            "src.cli.preprocess",
            ["--protocol", "p", "--run-config", "r", "--run-dir", "out"],
            1,
        ),
        (
            "src.cli.xgboost",
            ["develop", "--input-run", "in", "--protocol", "p", "--run-dir", "out"],
            1,
        ),
    ],
)
def test_cli_modules_fail_closed(module: str, arguments: list[str], expected: int) -> None:
    result = subprocess.run(
        [sys.executable, "-m", module, *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected, result.stderr


def test_distribution_registers_only_the_approved_console_scripts() -> None:
    entry_points = {
        entry.name: entry.value
        for entry in distribution("higgsml-xgboost").entry_points
        if entry.group == "console_scripts"
    }
    assert entry_points == {
        "higgsml-preprocess": "src.cli.preprocess:main",
        "higgsml-xgboost": "src.cli.xgboost:main",
    }
