#!/usr/bin/env python3
"""Run the complete prepared H4l workflow through the off-only final report."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
RUNS_ROOT = PROJECT_ROOT / "runs"
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from higgsml.errors import ResearchError, ResearchStateError  # noqa: E402
from higgsml.inference.run_readiness import preflight, verify_completion, verify_stage_b  # noqa: E402
from higgsml.protocol import load_protocol  # noqa: E402
from higgsml.run_names import workflow_directory_name  # noqa: E402
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
    parser.add_argument("--threshold-method", choices=["median-v1","joint-support-v1"], default="median-v1")
    parser.add_argument('--plan-only', action='store_true',
                        help='Read metadata and print the plan without launching children or writing outputs.')
    parser.add_argument('--stage-b-only', action='store_true',
                        help='Stop after a successful Stage B; do not generate access reviews or evaluate.')
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


def _read_access_review(path: Path) -> tuple[Path, dict]:
    resolved = (path if path.is_absolute() else PROJECT_ROOT / path).resolve()
    if not resolved.is_file():
        raise WorkflowError(f"Access review not found: {resolved}", 2)

    def strict_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    try:
        review = json.loads(resolved.read_text(encoding="utf-8"),
                            object_pairs_hook=strict_object,
                            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (OSError, ValueError) as error:
        raise WorkflowError(f"Invalid access review JSON: {resolved}", 2) from error
    if not isinstance(review, dict) or review.get("schema_version") not in {
        "h4l-off-assessment-access-v1", "h4l-off-assessment-access-v3",
        "h4l-off-self-review-access-v2",
    }:
        raise WorkflowError(f"Unsupported access review schema: {resolved}", 2)
    return resolved, review


def _run(args: argparse.Namespace) -> None:
    name = args.run_name
    try:
        workflow_directory_name(name)
    except ValueError as error:
        raise WorkflowError(str(error), 2) from error
    explicit_review = _read_access_review(args.access_review) if args.access_review else None
    protocol = load_protocol().to_dict()
    def check():
        try:
            return preflight(RUNS_ROOT, name, args.threshold_method, protocol)
        except ResearchError as error:
            raise WorkflowError(str(error), 5) from error

    readiness = check()
    python = sys.executable
    off_workers = str(_off_workers())
    method_flags = ["--threshold-method",args.threshold_method] if args.threshold_method != "median-v1" else []
    train_root = RUNS_ROOT / f"h4l-train-{name}"
    prepare_root = RUNS_ROOT / f"h4l-prepare-{name}"
    off_root = RUNS_ROOT / f"h4l-off-{name}"
    commands = [
        [python, str(SCRIPTS_ROOT / "h4l_prepare.py"),
         "--run-name", name, *_resume_flag(prepare_root)],
        [python, str(SCRIPTS_ROOT / "h4l_check.py"),
         "--run-name", name, *_resume_flag(train_root / "g1")],
        [python, str(SCRIPTS_ROOT / "h4l_run.py"),
         "--run-name", name, *_resume_flag(train_root / "batch" / "all-seeds")],
        [python, str(SCRIPTS_ROOT / "h4l_off_run.py"),
         "--source-run-name", name, "--run-name", name,
         "--stage-b", *method_flags, *_resume_flag(off_root),
         "--workers", off_workers, "--worker-threads", OFF_WORKER_THREADS],
    ]
    if args.plan_only:
        print(json.dumps({**readiness, 'requested_scope': 'stage_b' if args.stage_b_only else 'full',
            'commands_before_access': commands,
            'evaluation_requires': ['bound access review', 'eligible history', 'registered budget'],
            'run_name': name}, indent=2))
        if readiness['access_blockers'] and not args.stage_b_only:
            raise WorkflowError('Assessment preflight blocked: ' + '; '.join(readiness['access_blockers']), 5)
        return
    if readiness['access_blockers'] and not args.stage_b_only:
        raise WorkflowError('Assessment preflight blocked: ' + '; '.join(readiness['access_blockers']), 5)
    print(f"Threshold method: {args.threshold_method}; scope: exploratory, scientific validation pending", flush=True)
    _invoke(commands[0])
    # A new population is unknowable from a run name. Check immediately after
    # prepare, before the expensive training batch or any assessment access.
    readiness = check()
    if readiness['prepared_artifact_id'] is None:
        raise WorkflowError('Prepare did not publish a bound population manifest', 6)
    if readiness['access_blockers'] and not args.stage_b_only:
        raise WorkflowError('Assessment preflight blocked: ' + '; '.join(readiness['access_blockers']), 5)
    for command in commands[1:]:
        _invoke(command)

    if not (off_root/'evaluation-plan'/'evaluation-plan.json').is_file():
        raise WorkflowError(f'Support qualification blocked freeze. Report: {off_root / "gate-failure-report" / "report.md"}', 5)
    if args.stage_b_only:
        try:
            completion = verify_stage_b(off_root, protocol)
        except (ResearchError, OSError, ValueError) as error:
            raise WorkflowError('Stage B execution incomplete: ' + str(error), 6) from error
        print(json.dumps(completion, indent=2))
        return
    access_review = None
    if explicit_review and explicit_review[1]["schema_version"] == "h4l-off-assessment-access-v3":
        access_review = explicit_review[0]
    else:
        source_review = (explicit_review[0] if explicit_review else
                         off_root/'source-access-review'/'validated-off-assessment-access.json')
        if not source_review.is_file():
            _invoke([python,str(SCRIPTS_ROOT/'h4l_off_self_review.py'),'--run-name',name])
        access_review = off_root/'access-review'/'validated-off-assessment-access.json'
        if not access_review.is_file():
            _invoke([python,'-m','higgsml.cli','attribution','access-review',
                '--registration-run',str(off_root/'register'),'--template-run',str(off_root/'nominal'),
                '--freeze-run',str(off_root/'freeze'),'--result-run',str(off_root/'asimov'),
                '--evaluation-plan',str(off_root/'evaluation-plan'/'evaluation-plan.json'),
                '--access-review',str(source_review),'--run-dir',str(off_root/'access-review')])
        if not access_review.is_file():
            raise WorkflowError('Assessment access remains blocked; evaluation was not started. '
                  f'Stage B report: {off_root / "report-B" / "report.md"}', 5)
    _invoke([python,str(SCRIPTS_ROOT/'h4l_off_run.py'),
        '--source-run-name',name,'--run-name',name,*method_flags,'--evaluation',*_resume_flag(off_root/'evaluation'),
        '--access-review',str(access_review),'--workers',off_workers,'--worker-threads',OFF_WORKER_THREADS])
    try:
        completion = verify_completion(off_root, protocol)
    except (ResearchError, OSError, ValueError) as error:
        raise WorkflowError('Workflow execution incomplete: ' + str(error), 6) from error
    print(json.dumps(completion, indent=2))


def main() -> int:
    try:
        _run(_parser().parse_args())
    except WorkflowError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    except ResearchStateError as error:
        print(str(error), file=sys.stderr)
        return 5
    except (ResearchError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
