#!/usr/bin/env python3
"""Run the registered off-only attribution study with one command."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys

from tqdm.auto import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = (PROJECT_ROOT / "runs").resolve()
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from higgsml.errors import ResearchError  # noqa: E402
from higgsml.protocol import DEFAULT_PATH, load_protocol  # noqa: E402
from higgsml.run_names import workflow_directory_name  # noqa: E402
from higgsml.workflow_resume import classify_stage  # noqa: E402
from higgsml.hpc import add_arguments, activation, settings


class WorkflowError(Exception):
    def __init__(self, message: str, exit_code: int = 3) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Reuse one complete H4l five-seed batch and run the registered "
                     "off-only attribution workflow."),
    )
    parser.add_argument(
        "--source-run-name", required=True,
        help="Existing H4l batch name, for example 02 or T2.",
    )
    parser.add_argument(
        "--run-name", required=True,
        help="New short name; writes runs/h4l-off-<name>.",
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PATH)
    parser.add_argument(
        "--prepared-run", type=Path, default=Path("runs/h4l-prepare/prepare"),
    )
    parser.add_argument("--t1-validation", type=Path)
    parser.add_argument(
        "--access-review", type=Path,
        help=("Validated review path. Evaluation defaults to "
              "runs/h4l-off-<name>/access-review/validated-off-assessment-access.json."),
    )
    parser.add_argument(
        "--stage-b", action="store_true",
        help="Stop after the exploratory Asimov report and evaluation-plan publication.",
    )
    parser.add_argument(
        "--evaluation", action="store_true",
        help="Reuse this run name's completed Stage B and execute C-E.",
    )
    parser.add_argument("--plan", action="store_true")
    parser.add_argument(
        "--continue", dest="continue_run", action="store_true",
        help="Resume Stage B/evaluation and skip valid complete stages.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help=("Debug only: bypass source protocol consistency checks. "
              "Generated outputs are marked non-authoritative."),
    )
    parser.add_argument("--show-command", action="store_true")
    parser.add_argument("--no-progress", action="store_true",
                        help="Disable stage progress bars.")
    parser.add_argument("--workers", type=int, default=None,
                        help="Process workers for evaluation stages (default: 1).")
    parser.add_argument("--worker-threads", type=int, default=None)
    add_arguments(parser)
    return parser


def _resolve(path: Path) -> Path:
    value = path.expanduser()
    return (value if value.is_absolute() else PROJECT_ROOT / value).resolve()


def _safe_run_leaf(prefix: str, name: str) -> str:
    try:
        validated = workflow_directory_name(name)
    except ValueError as error:
        raise WorkflowError(str(error), 2) from error
    return prefix + validated.removeprefix("h4l-train-")


def _display(command: list[str]) -> str:
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


def _invoke(command: list[str], *, show_command: bool, progress=None) -> None:
    if settings():
        from higgsml.hpc_execution import supervised_run
        if show_command:
            print(_display(command), flush=True)
        code = supervised_run(command, cwd=PROJECT_ROOT)
        if code:
            raise WorkflowError(f'Off-only workflow stage failed with exit code {code}', code)
        return
    if show_command:
        print(_display(command), flush=True)
    process = subprocess.Popen(command, cwd=PROJECT_ROOT)
    while True:
        try:
            return_code = process.wait(timeout=1)
            break
        except subprocess.TimeoutExpired:
            if progress is not None:
                progress.refresh()
    if return_code:
        raise WorkflowError(
            f"Off-only workflow stage failed with exit code {return_code}",
            return_code,
        )


def _run(args: argparse.Namespace) -> None:
    policy = settings()
    if args.workers is None:
        args.workers = policy['workers'] if policy else 1
    if args.worker_threads is None:
        args.worker_threads = policy['worker_threads'] if policy else 1
    if args.workers < 1:
        raise WorkflowError("--workers must be positive", 2)
    if args.worker_threads < 1:
        raise WorkflowError("--worker-threads must be positive", 2)
    if args.stage_b and args.evaluation:
        raise WorkflowError("--stage-b cannot be combined with --evaluation", 2)
    if not args.stage_b and not args.evaluation and not args.plan and args.access_review is None:
        raise WorkflowError("Full evaluation requires --access-review; use --stage-b for Stage B", 2)

    source_leaf = _safe_run_leaf("h4l-train-", args.source_run_name)
    source = RUNS_ROOT / source_leaf / "batch" / "all-seeds"
    output = RUNS_ROOT / _safe_run_leaf("h4l-off-", args.run_name)
    prepared = _resolve(args.prepared_run)
    protocol = _resolve(args.protocol)
    t1_validation = _resolve(
        args.t1_validation or source / "templates" / "t1-validation.json"
    )
    if args.access_review:
        access_review = _resolve(args.access_review)
    elif args.evaluation:
        access_review = output / "access-review" / "validated-off-assessment-access.json"
    else:
        access_review = None

    if not args.plan:
        required = [("prepared run", prepared), ("protocol", protocol)]
        if not args.evaluation:
            required.extend((("source batch", source), ("T1 validation", t1_validation)))
        for label, path in required:
            if not path.exists():
                raise WorkflowError(f"Required {label} does not exist: {path}")
        if access_review is not None and not access_review.is_file():
            raise WorkflowError(f"Assessment access review does not exist: {access_review}")
        if args.evaluation and not output.is_dir():
            raise WorkflowError(f"Stage B output root does not exist: {output}", 4)
        if not args.evaluation and output.exists() and not args.continue_run:
            raise WorkflowError(f"Output root already exists and cannot be reused: {output}", 4)
        if output.exists() and (output.is_symlink() or not output.is_dir()):
            raise WorkflowError(f"Output root is not a reusable directory: {output}", 4)

    register = output / "register"
    nominal = output / "nominal"
    freeze = output / "freeze"
    asimov = output / "asimov"
    report_b = output / "report-B"
    evaluation = output / "evaluation"
    evaluation_plan = report_b / "evaluation-plan.json"
    common = ["--protocol", str(protocol), "--worker-threads", str(args.worker_threads)]
    if args.force:
        common.append("--force")

    cli = [sys.executable, "-m", "higgsml.cli", "attribution"]
    stage_b_commands = [
        [*cli, "register", *common, "--source-root", str(source),
         "--prepared-run", str(prepared), "--t1-validation", str(t1_validation),
         "--run-dir", str(register)],
        [*cli, "nominal", *common, "--registration-run", str(register),
         "--run-dir", str(nominal)],
        [*cli, "freeze", *common, "--registration-run", str(register),
         "--template-run", str(nominal), "--run-dir", str(freeze)],
        [*cli, "asimov", *common, "--registration-run", str(register),
         "--template-run", str(nominal), "--freeze-run", str(freeze),
         "--run-dir", str(asimov)],
        [*cli, "report", *common, "--registration-run", str(register),
         "--template-run", str(nominal), "--freeze-run", str(freeze),
         "--result-run", str(asimov), "--run-dir", str(report_b)],
    ]
    commands = [] if args.evaluation else stage_b_commands
    if not args.stage_b:
        evaluation_command = [
            sys.executable, str(PROJECT_ROOT / "scripts" / "h4l_evaluate.py"),
            "--plan", str(evaluation_plan), "--registration-run", str(register),
            "--prepared-run", str(prepared), "--template-run", str(nominal),
            "--freeze-run", str(freeze), "--result-run", str(asimov),
            "--output-root", str(evaluation), "--workers", str(args.workers),
            "--worker-threads", str(args.worker_threads),
        ]
        if access_review is not None:
            evaluation_command.extend(["--access-review", str(access_review)])
        if args.force:
            evaluation_command.append("--force")
        if args.no_progress:
            evaluation_command.append("--no-progress")
        if args.continue_run:
            evaluation_command.append("--continue")
        commands.append(evaluation_command)

    if not args.plan and args.evaluation:
        for label, path in (
            ("registration run", register), ("nominal run", nominal),
            ("freeze run", freeze), ("Asimov run", asimov),
            ("evaluation plan", evaluation_plan),
        ):
            if not path.exists():
                raise WorkflowError(f"Required completed Stage B {label} does not exist: {path}")
        if evaluation.exists() and not args.continue_run:
            raise WorkflowError(f"Evaluation output already exists and cannot be reused: {evaluation}", 4)

    if args.plan:
        for command in commands:
            print(_display(command))
        if args.evaluation:
            scope = "C-E evaluation from completed Stage B"
        else:
            scope = "Stage B and complete C-E evaluation" if not args.stage_b else "Stage B"
        print(f"Plan complete: {scope}; no run was created. Output root: {output}")
        if not args.stage_b and access_review is None:
            print("Execution requires --access-review.")
        return

    if args.force:
        print("WARNING: --force bypasses source protocol consistency checks; "
              "all generated outputs are debug-only and non-authoritative.", file=sys.stderr)
    visible_commands = commands if args.stage_b else ([] if args.evaluation else commands[:-1])
    protocol_value = load_protocol(protocol).to_dict()
    with tqdm(visible_commands, desc="H4l off Stage B", unit="stage",
              disable=args.no_progress) as progress:
        for command in progress:
            label = (command[command.index("attribution") + 1]
                     if "attribution" in command else "evaluation C-E")
            progress.set_postfix_str(label, refresh=True)
            if args.continue_run:
                target = Path(command[command.index("--run-dir") + 1])
                try:
                    action = classify_stage(
                        target, allowed_root=output, dataset=protocol_value["dataset"],
                        protocol=protocol_value, stages=(f"attribution-{label}",),
                    )
                except ResearchError as error:
                    raise WorkflowError(str(error), 4) from error
                if action == "skip":
                    continue
            _invoke(command, show_command=args.show_command, progress=progress)
    if not args.stage_b:
        _invoke(commands[-1], show_command=args.show_command)
    final_report = evaluation / "report" / "report.md" if not args.stage_b else report_b / "report.md"
    print(f"Off-only workflow complete. Report: {final_report}")


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
