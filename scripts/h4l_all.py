#!/usr/bin/env python3
"""Run the complete prepared H4l workflow through the off-only final report."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
RUNS_ROOT = PROJECT_ROOT / "runs"
DEFAULT_RUN_NAME = "default"
OFF_WORKERS = "4"
OFF_WORKER_THREADS = "1"


class WorkflowError(Exception):
    def __init__(self, message: str, exit_code: int = 3) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resume the complete H4l workflow after data initialization.",
    )
    parser.add_argument(
        "--run-name", default=DEFAULT_RUN_NAME,
        help=f"Shared standard/off-only run name (default: {DEFAULT_RUN_NAME}).",
    )
    return parser


def _reviewer_name() -> str:
    completed = subprocess.run(
        ["git", "config", "user.name"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=False,
    )
    reviewer = completed.stdout.strip() if completed.returncode == 0 else ""
    if not reviewer:
        reviewer = getpass.getuser().strip()
    if not reviewer or "automat" in reviewer.lower():
        raise WorkflowError(
            "Cannot infer a named human reviewer from git user.name or the local account.", 3
        )
    return reviewer


def _invoke(command: list[str]) -> None:
    print(f"RUN: {Path(command[1]).name}", flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode:
        raise WorkflowError(
            f"Workflow command failed with exit code {completed.returncode}: {command[1]}",
            completed.returncode,
        )


def _run(args: argparse.Namespace) -> None:
    name = args.run_name
    python = sys.executable
    commands = [
        [python, str(SCRIPTS_ROOT / "h4l_prepare.py"), "--continue"],
        [python, str(SCRIPTS_ROOT / "h4l_check.py"),
         "--run-name", name, "--continue"],
        [python, str(SCRIPTS_ROOT / "h4l_run.py"),
         "--run-name", name, "--continue"],
        [python, str(SCRIPTS_ROOT / "h4l_off_run.py"),
         "--source-run-name", name, "--run-name", name,
         "--stage-b", "--continue",
         "--workers", OFF_WORKERS, "--worker-threads", OFF_WORKER_THREADS],
    ]
    for command in commands:
        _invoke(command)

    access_review = (
        RUNS_ROOT / f"h4l-off-{name}" / "access-review"
        / "validated-off-assessment-access.json"
    )
    if not access_review.is_file():
        _invoke([
            python, str(SCRIPTS_ROOT / "h4l_off_self_review.py"),
            "--run-name", name, "--reviewer", _reviewer_name(),
        ])

    _invoke([
        python, str(SCRIPTS_ROOT / "h4l_off_run.py"),
        "--source-run-name", name, "--run-name", name,
        "--evaluation", "--continue",
        "--workers", OFF_WORKERS, "--worker-threads", OFF_WORKER_THREADS,
    ])
    print(
        "H4l workflow complete. Final report: "
        f"{RUNS_ROOT / f'h4l-off-{name}' / 'evaluation' / 'report' / 'report.md'}"
    )


def main() -> int:
    try:
        _run(_parser().parse_args())
    except WorkflowError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
