#!/usr/bin/env python3
"""Run the registered single-seed H4l feature-combination batch."""

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
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "research_feature_combinations_seed42.json"
T1_SCHEMA = PROJECT_ROOT / "config" / "validation" / "t1_validation_v1.schema.json"
EXPECTED_COMBINATIONS = (
    "A", "B", "C", "D", "AB", "AC", "AD", "BC", "BD", "CD",
    "ABC", "ABD", "ACD", "BCD", "ABCD",
)

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
        description="Run the registered H4l feature-combination batch.",
    )
    parser.add_argument("--seed", type=int, choices=range(42, 47), default=42)
    parser.add_argument(
        "--run-name",
        help=("Short shared workflow name; for example 001 resolves all inputs "
              "and the seed-specific batch output below the shared run root."),
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--prepared-run", type=Path)
    parser.add_argument("--gate-run", type=Path)
    parser.add_argument("--t1-validation", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the batch-stage progress bar.",
    )
    return parser


def _resolve(value: str | Path) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


def _display(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _load_config(path: Path) -> dict:
    if not path.is_file():
        raise WorkflowError(f"Batch configuration does not exist: {path}", 3)
    try:
        with path.open(encoding="utf-8") as stream:
            config = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowError(f"Invalid batch configuration: {path}: {error}", 3) from error
    expected = {
        "schema_version": "h4l-feature-combination-batch-v1",
        "dataset": "atlas2020_4lep",
        "default_seed": 42,
        "family_id": "engineered19_raw_T1",
        "empty_baseline_candidate": "M0c",
        "combination_candidate": "M3",
        "calibration_transform": "raw",
        "inference_layer": "T1",
        "injection_mu": 1.0,
    }
    if any(config.get(key) != value for key, value in expected.items()):
        raise WorkflowError(
            "Batch configuration differs from the registered single-seed feature-combination contract.",
            3,
        )
    if config.get("feature_combinations") != list(EXPECTED_COMBINATIONS):
        raise WorkflowError(
            "Batch configuration differs from the registered single-seed feature-combination contract.",
            3,
        )
    for key in ("protocol", "prepared_run", "g1_gate_run", "t1_validation", "output_root"):
        if not isinstance(config.get(key), str) or not config[key]:
            raise WorkflowError(f"Batch configuration is missing {key}", 3)
    return config


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


def _validate_t1(path: Path, protocol_path: Path, dataset: str) -> None:
    try:
        evidence = json.loads(path.read_text(encoding="utf-8-sig"))
        schema = json.loads(T1_SCHEMA.read_text(encoding="utf-8-sig"))
        Draft202012Validator(schema).validate(evidence)
        protocol = load_protocol(protocol_path, dataset=dataset).to_dict()
    except (OSError, json.JSONDecodeError, ValidationError, ResearchError) as error:
        raise WorkflowError(f"Invalid T1 validation evidence: {path}: {error}", 3) from error
    if evidence.get("status") == "pending":
        raise WorkflowError(
            "T1 evidence is pending; the controlled MC batch cannot start before independent review.",
            3,
        )
    if (
        evidence.get("status") != "validated"
        or evidence.get("dataset") != dataset
        or evidence.get("protocol_sha256") != digest_json(protocol)
    ):
        raise WorkflowError(
            "T1 validation evidence is not validated and bound to the current dataset/protocol.",
            3,
        )


def _run(args: argparse.Namespace) -> None:
    config = _load_config(_resolve(args.config))
    protocol = _resolve(args.protocol or config["protocol"])
    run_name = getattr(args, "run_name", None)
    explicit = (args.prepared_run, args.gate_run, args.t1_validation, args.output_root)
    if run_name is not None:
        if any(value is not None for value in explicit):
            raise WorkflowError(
                "--run-name cannot be combined with --prepared-run, --gate-run, "
                "--t1-validation, or --output-root", 2
            )
        try:
            root = RUNS_ROOT / workflow_directory_name(run_name)
        except ValueError as error:
            raise WorkflowError(str(error), 2) from error
        prepared = root / "prepare"
        gate = root / "g1" / "templates"
        t1_validation = root / "inputs" / "t1-validation.json"
        batch_root = root / "batch" / f"seed{args.seed}"
    else:
        prepared = _resolve(args.prepared_run or config["prepared_run"])
        gate = _resolve(args.gate_run or config["g1_gate_run"])
        t1_validation = _resolve(args.t1_validation or config["t1_validation"])
        output_value = str(args.output_root or config["output_root"]).replace(
            "{seed}", str(args.seed)
        )
        batch_root = _resolve(output_value)

    try:
        relative = batch_root.relative_to(RUNS_ROOT)
    except ValueError as error:
        raise WorkflowError(
            f"OutputRoot must be a child of the neural/runs directory: {batch_root}", 4
        ) from error
    if not relative.parts:
        raise WorkflowError("OutputRoot cannot be the neural/runs directory itself", 4)
    if not protocol.is_file():
        raise WorkflowError(f"Research protocol does not exist: {protocol}", 3)
    if not args.plan_only:
        for required in (prepared, gate, t1_validation):
            if not required.exists():
                raise WorkflowError(f"Required bound input does not exist: {required}", 3)
        _validate_t1(t1_validation, protocol, config["dataset"])
        if batch_root.exists():
            raise WorkflowError(
                f"OutputRoot already exists and cannot be reused: {batch_root}", 4
            )

    common = ["--dataset", config["dataset"], "--protocol", str(protocol)]
    calibration_runs: list[Path] = []
    baseline_train = batch_root / "train" / "empty"
    baseline_calibration = batch_root / "calibrate" / "empty"
    steps = [
        (
            "train M0c baseline",
            [
                "train", *common,
                "--input-run", str(prepared), "--gate-run", str(gate),
                "--candidate", "M0c", "--seed", str(args.seed),
                "--run-dir", str(baseline_train),
            ],
        ),
        (
            "calibrate M0c baseline",
            [
                "calibrate", *common,
                "--input-run", str(prepared), "--model-run", str(baseline_train),
                "--transform", "raw", "--seed", str(args.seed),
                "--run-dir", str(baseline_calibration),
            ],
        ),
    ]
    calibration_runs.append(baseline_calibration)

    for groups in EXPECTED_COMBINATIONS:
        train_run = batch_root / "train" / f"groups-{groups}"
        calibration_run = batch_root / "calibrate" / f"groups-{groups}"
        steps.extend(
            [
                (
                    f"train groups {groups}",
                    [
                        "train", *common,
                        "--input-run", str(prepared), "--gate-run", str(gate),
                        "--candidate", "M3", "--groups", groups,
                        "--seed", str(args.seed), "--run-dir", str(train_run),
                    ],
                ),
                (
                    f"calibrate groups {groups}",
                    [
                        "calibrate", *common,
                        "--input-run", str(prepared), "--model-run", str(train_run),
                        "--transform", "raw", "--seed", str(args.seed),
                        "--run-dir", str(calibration_run),
                    ],
                ),
            ]
        )
        calibration_runs.append(calibration_run)

    template_run = batch_root / "templates"
    template_arguments = [
        "templates", *common,
        "--input-run", str(prepared),
        "--t1-validation", str(t1_validation),
        "--seed", str(args.seed),
        "--run-dir", str(template_run),
    ]
    for calibration_run in calibration_runs:
        template_arguments.extend(["--calibration-run", str(calibration_run)])
    steps.append(("templates", template_arguments))

    inference_run = batch_root / "inference"
    steps.append(
        (
            "infer T1",
            [
                "infer", *common,
                "--template-run", str(template_run),
                "--layer", "T1", "--mu", "1", "--seed", str(args.seed),
                "--run-dir", str(inference_run),
            ],
        )
    )
    report_run = batch_root / "report"
    steps.append(
        (
            "report",
            [
                "report", *common,
                "--result-run", str(inference_run),
                "--seed", str(args.seed), "--run-dir", str(report_run),
            ],
        )
    )

    with tqdm(
        steps,
        desc=f"H4l batch seed {args.seed}",
        unit="stage",
        disable=args.plan_only or args.no_progress,
    ) as progress:
        for label, arguments in progress:
            progress.set_postfix_str(label, refresh=True)
            _invoke(arguments, plan_only=args.plan_only)

    if args.plan_only:
        print("Plan complete: 15 nonempty combinations plus the M0c empty baseline; no run was created.")
        return

    report_path = report_run / "report.json"
    try:
        with report_path.open(encoding="utf-8") as stream:
            report = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowError(f"Cannot read batch report: {report_path}: {error}", 3) from error
    comparisons = report.get("feature_combination_comparisons", [])
    if (
        len(comparisons) != 1
        or comparisons[0].get("status") != "valid"
        or comparisons[0].get("seed") != args.seed
    ):
        raise WorkflowError(
            "The batch completed, but the complete 15-combination comparison is unavailable.",
            5,
        )
    print(
        f"Completed seed {args.seed}: 15 combination models, M0c baseline, "
        "common T1 inference and exact Shapley comparison."
    )
    print(f"Report: {report_run / 'report.md'}")


def main() -> int:
    try:
        _run(_parser().parse_args())
    except WorkflowError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
