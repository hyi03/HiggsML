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

sys.path.insert(0, str(PROJECT_ROOT / 'src'))
from higgsml.hpc import add_arguments, activation, settings
from higgsml.errors import ResearchError


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
    add_arguments(parser)
    parser.add_argument('--plan-only', action='store_true', help='Print stages without running or creating artifacts.')
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
    if settings():
        from higgsml.hpc_execution import supervised_run
        code = supervised_run(command, cwd=PROJECT_ROOT)
    else:
        code = subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode
    if code:
        raise WorkflowError(
            f"Workflow command failed with exit code {code}: {command[1]}", code,
        )


def _resume_flag(path: Path) -> list[str]:
    """Use continuation only when the stage's aggregate root already exists."""
    return ["--continue"] if path.is_dir() else []


def _run(args: argparse.Namespace) -> None:
    name = args.run_name
    python = sys.executable
    train_root = RUNS_ROOT / f"h4l-train-{name}"
    off_root = RUNS_ROOT / f"h4l-off-{name}"
    policy = settings()
    workers = str(policy['workers']) if policy else OFF_WORKERS
    threads = str(policy['worker_threads']) if policy else OFF_WORKER_THREADS
    commands = [
        [python, str(SCRIPTS_ROOT / "h4l_prepare.py"),
         *_resume_flag(RUNS_ROOT / "h4l-prepare")],
        [python, str(SCRIPTS_ROOT / "h4l_check.py"),
         "--run-name", name, *_resume_flag(train_root / "g1")],
        [python, str(SCRIPTS_ROOT / "h4l_run.py"),
         "--run-name", name, *_resume_flag(train_root / "batch" / "all-seeds")],
        [python, str(SCRIPTS_ROOT / "h4l_off_run.py"),
         "--source-run-name", name, "--run-name", name,
         "--stage-b", *_resume_flag(off_root),
         "--workers", workers, "--worker-threads", threads],
    ]
    if args.plan_only:
        import shlex
        for command in commands:
            print(shlex.join(command))
        print('Then reuse or create the named self-review; run evaluation and final report.')
        print('Training/calibration dependencies: train -> its calibrations; all calibrations -> templates -> inference -> report.')
        print(f'Evaluation: mc-bootstrap; model-self mu=0,1,2; assessment mu=0,1,2; t2; report. workers={workers}, threads={threads}')
        return
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
        "--evaluation", *_resume_flag(off_root / "evaluation"),
        "--workers", workers, "--worker-threads", threads,
    ])
    print(
        "H4l workflow complete. Final report: "
        f"{RUNS_ROOT / f'h4l-off-{name}' / 'evaluation' / 'report' / 'report.md'}"
    )


def main() -> int:
    try:
        args = _parser().parse_args()
        with activation(args):
            _run(args)
    except (WorkflowError, ResearchError) as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
