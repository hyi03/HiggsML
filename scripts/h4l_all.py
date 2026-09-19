#!/usr/bin/env python3
"""Run the complete prepared H4l workflow through the off-only final report."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
RUNS_ROOT = PROJECT_ROOT / "runs"
DEFAULT_RUN_NAME = "default"
MAX_OFF_WORKERS = 4
LOCAL_MEMORY_RESERVE = 2 * 1024**3
# A worker's steady-state RSS can be much smaller than its transient peak while
# pyhf/SciPy fits and result serialization overlap.  Budget the complete process
# peak here so a 16 GiB workstation starts at most two evaluation workers.
AVAILABLE_MEMORY_PER_WORKER = 5 * 1024**3
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
    parser.add_argument('--access-review', type=Path)
    return parser


def _invoke(command: list[str]) -> None:
    label = command[2] if command[1] == "-m" else Path(command[1]).name
    print(f"RUN: {label}", flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode:
        raise WorkflowError(
            f"Workflow command failed with exit code {completed.returncode}: {command[1]}",
            completed.returncode,
        )


def _resume_flag(path: Path) -> list[str]:
    """Use continuation only when the stage's aggregate root already exists."""
    return ["--continue"] if path.is_dir() else []


def _physical_memory_bytes() -> int | None:
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
            return int(status.total_physical)
        return None
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def _off_workers() -> int:
    physical = _physical_memory_bytes()
    if physical is None or physical < 0:
        return 1
    worker_memory = max(0, physical - LOCAL_MEMORY_RESERVE)
    return max(1, min(MAX_OFF_WORKERS, worker_memory // AVAILABLE_MEMORY_PER_WORKER))


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
        _invoke(command)

    if not (off_root/'evaluation-plan'/'evaluation-plan.json').is_file():
        print(f'Support qualification blocked freeze. Report: {off_root / "gate-failure-report" / "report.md"}')
        return
    access_review = args.access_review
    if access_review is None:
        source_review = off_root/'source-access-review'/'validated-off-assessment-access.json'
        if not source_review.is_file():
            _invoke([python,str(SCRIPTS_ROOT/'h4l_off_self_review.py'),'--run-name',name])
        access_review = off_root/'access-review'/'validated-off-assessment-access.json'
        if not access_review.is_file():
            _invoke([python,'-m','higgsml.cli','attribution','access-review',
                '--registration-run',str(off_root/'register'),'--template-run',str(off_root/'nominal'),
                '--freeze-run',str(off_root/'freeze'),'--result-run',str(off_root/'asimov'),
                '--evaluation-plan',str(off_root/'evaluation-plan'/'evaluation-plan.json'),
                '--access-review',str(source_review),'--run-dir',str(off_root/'access-review')])
    _invoke([python,str(SCRIPTS_ROOT/'h4l_off_run.py'),
        '--source-run-name',name,'--run-name',name,'--evaluation',*_resume_flag(off_root/'evaluation'),
        '--access-review',str(access_review),'--workers',off_workers,'--worker-threads',OFF_WORKER_THREADS])


def main() -> int:
    try:
        _run(_parser().parse_args())
    except WorkflowError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
