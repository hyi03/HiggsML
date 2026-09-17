#!/usr/bin/env python3
"""Run the complete prepared H4l workflow through the off-only final report."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
RUNS_ROOT = PROJECT_ROOT / "runs"
DEFAULT_RUN_NAME = "default"
MAX_OFF_WORKERS = 4
AVAILABLE_MEMORY_PER_WORKER = 6 * 1024**3
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
    parser.add_argument('--evaluation-version', choices=['v1','v2'], default='v1')
    parser.add_argument('--access-review', type=Path)
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


def _resume_flag(path: Path) -> list[str]:
    """Use continuation only when the stage's aggregate root already exists."""
    return ["--continue"] if path.is_dir() else []


def _available_memory_bytes() -> int | None:
    if sys.platform == "win32":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.available_physical)
        return None
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_AVPHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def _off_workers() -> int:
    available = _available_memory_bytes()
    if available is None or available < 0:
        return 1
    return max(1, min(MAX_OFF_WORKERS, available // AVAILABLE_MEMORY_PER_WORKER))


def _run(args: argparse.Namespace) -> None:
    name = args.run_name
    python = sys.executable
    off_workers = str(_off_workers())
    train_root = RUNS_ROOT / f"h4l-train-{name}"
    off_root = RUNS_ROOT / f"h4l-off-{name}"
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
         "--workers", off_workers, "--worker-threads", OFF_WORKER_THREADS],
    ]
    for command in commands:
        if args.evaluation_version == 'v2' and Path(command[1]).name == 'h4l_off_run.py':
            command += ['--evaluation-version','v2']
        _invoke(command)

    if args.evaluation_version == 'v2':
        if not (off_root/'evaluation-plan'/'evaluation-plan.json').is_file():
            print(f'V2 support qualification blocked freeze. Report: {off_root / "gate-failure-report" / "report.md"}')
            return
        if not args.access_review:
            print(f'V2 assessment requires an eligible source and v2 access receipt. Stage B report: {off_root / "report-B" / "report.md"}')
            return
        _invoke([python,str(SCRIPTS_ROOT/'h4l_off_run.py'),'--evaluation-version','v2',
            '--source-run-name',name,'--run-name',name,'--evaluation',*_resume_flag(off_root/'evaluation'),
            '--access-review',str(args.access_review),'--workers',off_workers,'--worker-threads',OFF_WORKER_THREADS])
        return

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
        "--workers", off_workers, "--worker-threads", OFF_WORKER_THREADS,
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
