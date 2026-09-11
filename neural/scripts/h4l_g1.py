#!/usr/bin/env python3
"""Run the minimal seed-42 H4l model, calibration, template, and G1 gate."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from tqdm.auto import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = (PROJECT_ROOT / "runs").resolve()
DEFAULT_PROTOCOL = (PROJECT_ROOT / "config" / "research_protocol_v1.json").resolve()
RUN_SCRIPT = (PROJECT_ROOT / "scripts" / "h4l_run.py").resolve()
T1_SCHEMA = (PROJECT_ROOT / "config" / "validation" / "t1_validation_v1.schema.json").resolve()
DATASET = "atlas2020_4lep"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.artifacts import digest_json  # noqa: E402
from src.research.errors import ResearchError  # noqa: E402
from src.research.protocol import load_protocol  # noqa: E402
from src.research.run_names import workflow_directory_name  # noqa: E402


class WorkflowError(Exception):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run G1 from an existing reusable H4l prepared artifact.",
    )
    parser.add_argument(
        "--run-name",
        help=("Short shared workflow name; for example 001 resolves all inputs "
              "and outputs below runs/h4l-feature-combinations-prerequisites-001."),
    )
    parser.add_argument("--prepared-run", type=Path)
    parser.add_argument("--t1-validation", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the G1-stage progress bar.",
    )
    return parser


def _resolve(value: Path) -> Path:
    candidate = value.expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


def _workflow_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    run_name = getattr(args, "run_name", None)
    explicit = (args.prepared_run, args.t1_validation, args.output_root)
    if run_name is not None:
        if any(value is not None for value in explicit):
            raise WorkflowError(
                "--run-name cannot be combined with --prepared-run, "
                "--t1-validation, or --output-root", 2
            )
        try:
            root = RUNS_ROOT / workflow_directory_name(run_name)
        except ValueError as error:
            raise WorkflowError(str(error), 2) from error
        return root / "prepare", root / "inputs" / "t1-validation.json", root / "g1"
    if any(value is None for value in explicit):
        raise WorkflowError(
            "provide --run-name or all of --prepared-run, --t1-validation, and --output-root",
            2,
        )
    return tuple(_resolve(value) for value in explicit)


def _display(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowError(f"Invalid JSON artifact: {path}: {error}", 3) from error
    if not isinstance(value, dict):
        raise WorkflowError(f"JSON artifact must be an object: {path}", 3)
    return value


def _validate_t1(path: Path, protocol_path: Path) -> None:
    try:
        evidence = _load_json(path)
        schema = _load_json(T1_SCHEMA)
        Draft202012Validator(schema).validate(evidence)
        protocol = load_protocol(protocol_path, dataset=DATASET).to_dict()
    except (ValidationError, ResearchError) as error:
        raise WorkflowError(f"Invalid T1 validation evidence: {path}: {error}", 3) from error
    if (
        evidence.get("status") != "validated"
        or evidence.get("dataset") != DATASET
        or evidence.get("protocol_sha256") != digest_json(protocol)
    ):
        raise WorkflowError(
            "T1 validation evidence is not validated and bound to the current dataset/protocol.",
            3,
        )


def _invoke(arguments: list[str], *, plan_only: bool) -> None:
    command = [sys.executable, "-m", "src.cli.research", *arguments]
    print(_display(command), flush=True)
    if plan_only:
        return
    process = subprocess.Popen(command, cwd=PROJECT_ROOT)
    progress_started = False
    while True:
        try:
            return_code = process.wait(timeout=1)
            break
        except subprocess.TimeoutExpired:
            if not progress_started:
                sys.stderr.write(f"[h4l] stage '{arguments[0]}' running ")
                progress_started = True
            sys.stderr.write(".")
            sys.stderr.flush()
    if progress_started:
        sys.stderr.write("\n")
        sys.stderr.flush()
    if return_code != 0:
        raise WorkflowError(
            f"higgsml-research failed with exit code {return_code}",
            return_code,
        )


def _validate_paths(prepared: Path, t1_validation: Path, output_root: Path,
                    protocol_path: Path, *, plan_only: bool) -> None:
    try:
        relative = output_root.relative_to(RUNS_ROOT)
    except ValueError as error:
        raise WorkflowError(
            f"OutputRoot must be a child of the neural/runs directory: {output_root}", 4
        ) from error
    if not relative.parts:
        raise WorkflowError("OutputRoot cannot be the neural/runs directory itself", 4)
    for required in (protocol_path, RUN_SCRIPT):
        if not required.is_file():
            raise WorkflowError(f"Required project file does not exist: {required}", 3)
    if plan_only:
        return
    if not prepared.is_dir():
        raise WorkflowError(f"Prepared run does not exist: {prepared}", 3)
    if not t1_validation.is_file():
        raise WorkflowError(f"T1 validation evidence does not exist: {t1_validation}", 3)
    if output_root.exists():
        raise WorkflowError(f"OutputRoot already exists and cannot be reused: {output_root}", 4)
    _validate_t1(t1_validation, protocol_path)


def _run(args: argparse.Namespace) -> None:
    prepared, t1_validation, output_root = _workflow_paths(args)
    protocol_path = _resolve(args.protocol or DEFAULT_PROTOCOL)
    _validate_paths(prepared, t1_validation, output_root, protocol_path,
                    plan_only=args.plan_only)

    train_root = output_root / "train"
    calibration_root = output_root / "calibrate"
    model_runs = {name: train_root / name.lower() for name in ("M0c", "M2", "M3")}
    calibration_runs = {
        "m0c_raw": calibration_root / "m0c-raw",
        "m2_raw": calibration_root / "m2-raw",
        "m4": calibration_root / "m4-physical",
        "m3_raw": calibration_root / "m3-raw",
        "m5": calibration_root / "m5-physical",
    }
    gate_run = output_root / "templates"
    common = ["--dataset", DATASET, "--protocol", str(protocol_path)]
    steps: list[tuple[str, list[str]]] = []

    for candidate in ("M0c", "M2", "M3"):
        steps.append((
            f"train {candidate}",
            [
                "train", *common, "--input-run", str(prepared),
                "--candidate", candidate, "--seed", "42",
                "--run-dir", str(model_runs[candidate]),
            ],
        ))

    for candidate, transform, output in (
        ("M0c", "raw", calibration_runs["m0c_raw"]),
        ("M2", "raw", calibration_runs["m2_raw"]),
        ("M2", "physical", calibration_runs["m4"]),
        ("M3", "raw", calibration_runs["m3_raw"]),
        ("M3", "physical", calibration_runs["m5"]),
    ):
        steps.append((
            f"calibrate {candidate} {transform}",
            [
                "calibrate", *common, "--input-run", str(prepared),
                "--model-run", str(model_runs[candidate]),
                "--transform", transform, "--run-dir", str(output),
            ],
        ))

    template_arguments = ["templates", *common, "--input-run", str(prepared)]
    for calibration_run in calibration_runs.values():
        template_arguments.extend(["--calibration-run", str(calibration_run)])
    template_arguments.extend(
        ["--t1-validation", str(t1_validation), "--run-dir", str(gate_run)]
    )
    steps.append(("templates", template_arguments))

    with tqdm(
        steps,
        desc="H4l G1",
        unit="stage",
        disable=args.plan_only or args.no_progress,
    ) as progress:
        for label, arguments in progress:
            progress.set_postfix_str(label, refresh=True)
            _invoke(arguments, plan_only=args.plan_only)

    if not args.plan_only:
        status = _load_json(gate_run / "g1.json").get("status")
        print(f"G1 status: {status}")
        if status != "passed":
            raise WorkflowError(
                "G1 did not pass; retry with the same prepared run and a new output root.", 5
            )

    next_command = [
        sys.executable, str(RUN_SCRIPT), "--seed", "42",
        "--protocol", str(protocol_path),
    ]
    run_name = getattr(args, "run_name", None)
    if run_name is not None:
        next_command.extend(["--run-name", run_name])
    else:
        next_command.extend([
            "--prepared-run", str(prepared), "--gate-run", str(gate_run),
            "--t1-validation", str(t1_validation),
            "--output-root", str(output_root.parent / "batch" / "seed42"),
        ])
    print("Next batch command:")
    print(_display(next_command))
    if args.plan_only:
        print("G1 plan complete; no run was created.")
    else:
        print("G1 complete; assessment remains unopened.")


def main() -> int:
    try:
        _run(_parser().parse_args())
    except WorkflowError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
