#!/usr/bin/env python3
"""Run the registered five-seed H4l feature and primary-comparison batch."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import uuid

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from tqdm.auto import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = (PROJECT_ROOT / "runs").resolve()
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "protocols" / "feature_combinations_seed42.json"
T1_SCHEMA = PROJECT_ROOT / "config" / "schemas" / "t1_validation_v1.schema.json"
EXPECTED_SEEDS = tuple(range(42, 47))
EXPECTED_COMBINATIONS = (
    "A", "B", "C", "D", "AB", "AC", "AD", "BC", "BD", "CD",
    "ABC", "ABD", "ACD", "BCD", "ABCD",
)

SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from higgsml.artifacts import digest_json, read_run  # noqa: E402
from higgsml.cleanup import remove_run_directories  # noqa: E402
from higgsml.errors import ResearchError  # noqa: E402
from higgsml.protocol import load_protocol  # noqa: E402
from higgsml.qualification import contract_checked  # noqa: E402
from higgsml.run_names import prepare_directory_name, workflow_directory_name  # noqa: E402


class WorkflowError(Exception):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Run the registered five-seed H4l feature-combination and "
                     "M4/M5 primary-comparison batch."),
    )
    parser.add_argument(
        "--seed", type=int, choices=EXPECTED_SEEDS,
        help="Run one diagnostic seed instead of the default complete seed 42-46 workflow.",
    )
    parser.add_argument(
        "--run-name",
        help=("Short experiment name; resolves global prepared inputs and the "
              "experiment's G1 gate, then writes its batch output."),
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--prepared-run", type=Path)
    parser.add_argument("--gate-run", type=Path)
    parser.add_argument("--t1-validation", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--show-command", action="store_true",
                        help="Print each stage command before it is run.")
    parser.add_argument(
        "--continue", dest="continue_run", action="store_true",
        help=("Continue an existing batch: skip valid complete stages and quarantine "
              "an invalid stage directory before retrying it once."),
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Delete the complete or explicit single-seed batch selected by this command.",
    )
    parser.add_argument("--no-progress", action="store_true",
                        help="Disable the complete-batch progress bar.")
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
        "schema_version": "h4l-feature-combination-batch-v3",
        "dataset": "atlas2020_4lep",
        "seeds": list(EXPECTED_SEEDS),
        "family_id": "engineered19_raw_T1",
        "mass_input_comparison_family_id": "engineered19_raw_T1_m4l_on_off",
        "mass_input_variants": ["on", "off"],
        "empty_baseline_candidate": "M0c",
        "combination_candidate": "M3",
        "calibration_transform": "raw",
        "inference_layer": "T1",
        "injection_mu": 1.0,
        "primary_candidates": ["M4", "M5"],
        "primary_transform": "physical",
    }
    if any(config.get(key) != value for key, value in expected.items()):
        raise WorkflowError(
            "Batch configuration differs from the registered five-seed workflow contract.", 3
        )
    if config.get("feature_combinations") != list(EXPECTED_COMBINATIONS):
        raise WorkflowError(
            "Batch configuration differs from the registered five-seed workflow contract.", 3
        )
    for key in ("protocol", "prepared_run", "g1_gate_run", "t1_validation", "output_root"):
        if not isinstance(config.get(key), str) or not config[key]:
            raise WorkflowError(f"Batch configuration is missing {key}", 3)
    if "{seed}" in config["output_root"]:
        raise WorkflowError("The v2 batch output_root must be a single common directory", 3)
    return config


def _invoke(arguments: list[str], *, plan_only: bool, show_command: bool = False) -> None:
    command = [sys.executable, "-m", "higgsml.cli", *arguments]
    if show_command:
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
        raise WorkflowError(f"higgsml failed with exit code {return_code}", return_code)


def _continue_stage(
    arguments: list[str], *, batch_root: Path, dataset: str, protocol: dict,
) -> str:
    """Classify a continued stage, quarantining an invalid existing run."""
    run_dir = Path(arguments[arguments.index("--run-dir") + 1])
    try:
        relative = run_dir.relative_to(batch_root)
    except ValueError as error:
        raise WorkflowError(f"Stage run directory is outside OutputRoot: {run_dir}", 4) from error
    if not relative.parts:
        raise WorkflowError(f"Stage run directory cannot be OutputRoot: {run_dir}", 4)
    if not os.path.lexists(run_dir):
        return "run"
    try:
        read_run(run_dir, dataset=dataset, protocol=protocol, stages=(arguments[0],))
    except ResearchError as error:
        quarantine = run_dir.parent / f".{run_dir.name}.{uuid.uuid4().hex}.invalid"
        try:
            run_dir.rename(quarantine)
        except OSError as rename_error:
            raise WorkflowError(
                f"Cannot quarantine invalid stage run: {run_dir}", 4
            ) from rename_error
        print(f"QUARANTINE invalid: {run_dir} -> {quarantine} ({error})", flush=True)
        return "retry"
    print(f"SKIP complete: {run_dir}", flush=True)
    return "skip"


def _validate_t1(path: Path, protocol_path: Path, dataset: str) -> None:
    try:
        evidence = json.loads(path.read_text(encoding="utf-8-sig"))
        schema_path = (T1_SCHEMA.with_name("t1_validation_v2.schema.json")
                       if isinstance(evidence, dict)
                       and evidence.get("schema_version") == "h4l-t1-validation-v2" else T1_SCHEMA)
        schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
        Draft202012Validator(schema).validate(evidence)
        checked = contract_checked(evidence, "t1")
        protocol = load_protocol(protocol_path, dataset=dataset).to_dict()
    except (OSError, json.JSONDecodeError, ValidationError, ResearchError) as error:
        raise WorkflowError(f"Invalid T1 validation evidence: {path}: {error}", 3) from error
    if evidence.get("status") == "pending":
        raise WorkflowError(
            "T1 evidence is pending; exploratory execution requires bound software contract checks.", 3
        )
    if (not checked
            or evidence.get("dataset") != dataset
            or evidence.get("protocol_sha256") != digest_json(protocol)):
        raise WorkflowError(
            "T1 software contract evidence is not checked and bound to the current dataset/protocol.", 3
        )


def _print_conclusions(report: dict, report_path: Path, *, complete: bool) -> None:
    summary = report.get("feature_combination_summary", {})
    comparisons = report.get("feature_combination_comparisons", [])
    print("\nFeature-combination evaluation (MC-only educational/technical demo):")
    if summary.get("status") == "valid":
        seeds = summary["seeds"]
        print("subset  " + "  ".join(f"s{seed}:W68/improvement" for seed in seeds) +
              "  median W68  median improvement")
        for row in summary["combinations"]:
            values = "  ".join(f"{item['width68']:.6g}/{item['relative_improvement_vs_empty']:.4%}"
                               for item in row["per_seed"])
            print(f"{row['subset']:<6}  {values}  {row['median_width68']:.6g}  "
                  f"{row['median_relative_improvement_vs_empty']:.4%}")
        best = summary["best_combination"]
        print(f"Best combination: {best['subset']} "
              f"(median improvement {best['median_relative_improvement_vs_empty']:.4%}, "
              f"median W68 {best['median_width68']:.6g})")
        print("Group-level Shapley contributions:")
        for group, row in summary["shapley"]["groups"].items():
            values = ", ".join(f"s{item['seed']}={item['contribution']:.6g}"
                               for item in row["per_seed"])
            print(f"  {group}: {values}; median={row['median_contribution']:.6g}; "
                  f"range=[{row['min_contribution']:.6g}, {row['max_contribution']:.6g}]")
        interactions = summary["shapley"]["interactions"]
        positive = max(interactions, key=lambda row:row["median_second_difference"])
        negative = min(interactions, key=lambda row:row["median_second_difference"])
        print(f"Strongest positive interaction: {positive['pair']} | "
              f"{positive['conditioning_subset'] or 'empty'} = "
              f"{positive['median_second_difference']:.6g}")
        print(f"Strongest negative interaction: {negative['pair']} | "
              f"{negative['conditioning_subset'] or 'empty'} = "
              f"{negative['median_second_difference']:.6g}")
    elif len(comparisons) == 1 and comparisons[0].get("status") == "valid":
        comparison = comparisons[0]
        print(f"Single-seed diagnostic: seed {comparison['seed']}")
        for row in comparison["nonempty_combinations"]:
            print(f"  {row['subset']}: W68={row['width68']:.6g}, "
                  f"improvement={row['relative_improvement_vs_empty']:.4%}")
        best = comparison["nonempty_combinations"][0]
        print(f"Best single-seed combination: {best['subset']} (W68={best['width68']:.6g})")
        print("Group-level Shapley contributions: " + ", ".join(
            f"{group}={value:.6g}"
            for group,value in comparison["shapley"]["contributions"].items()
        ))
    else:
        print(f"Feature-combination summary unavailable: {summary.get('status', 'missing')}")

    primary = report.get("primary_comparison", {})
    print(f"Primary M5/M4 comparison: {primary.get('status', 'missing')}")
    for row in primary.get("paired_seeds", []):
        print(f"  seed {row['seed']}: M4={row['M4_width68']:.6g}, "
              f"M5={row['M5_width68']:.6g}, improvement={row['relative_improvement']:.4%}")
    if primary.get("median_relative_improvement") is not None:
        print(f"  five-seed median improvement={primary['median_relative_improvement']:.4%}")
    elif not complete:
        print("  A single-seed diagnostic cannot complete the registered five-seed primary comparison.")
    print(f"Primary comparison cohort: {report.get('primary_comparison_cohort_id')}")
    mass_summary = report.get("mass_input_summary", {})
    print(f"m4l on/off comparison: {mass_summary.get('status', 'missing')}")
    for row in mass_summary.get("combinations", []):
        print(f"  {row['subset']}: median delta AUC={row['median_delta_auc_on_minus_off']:.6g}, "
              f"median W68 improvement={row['median_relative_w68_improvement_from_m4l']:.4%}")
    print("Independent scientific numerical validation remains separate from software execution.")
    print(f"Report: {report_path}")


def _clean_batch_root(args: argparse.Namespace) -> Path:
    """Return the exact batch directory selected by a cleanup command."""
    seed = getattr(args, "seed", None)
    run_name = getattr(args, "run_name", None)
    output_root = getattr(args, "output_root", None)
    if run_name is not None:
        explicit_inputs = (
            getattr(args, "prepared_run", None),
            getattr(args, "gate_run", None),
            getattr(args, "t1_validation", None),
            output_root,
        )
        if any(value is not None for value in explicit_inputs):
            raise WorkflowError(
                "--run-name cannot be combined with --prepared-run, --gate-run, "
                "--t1-validation, or --output-root", 2
            )
        try:
            workflow_root = RUNS_ROOT / workflow_directory_name(run_name)
        except ValueError as error:
            raise WorkflowError(str(error), 2) from error
        leaf = "all-seeds" if seed is None else f"seed{seed}"
        return workflow_root / "batch" / leaf
    if output_root is None:
        raise WorkflowError("--clean requires --run-name or --output-root", 2)
    candidate = Path(output_root).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.absolute()


def _clean(args: argparse.Namespace) -> None:
    if getattr(args, "plan_only", False):
        raise WorkflowError("--clean cannot be combined with --plan-only", 2)
    batch_root = _clean_batch_root(args)
    try:
        result = remove_run_directories([batch_root], allowed_root=RUNS_ROOT)
    except (OSError, ValueError) as error:
        raise WorkflowError(f"Cannot clean H4l batch output: {error}", 4) from error
    if result["removed"]:
        print(f"Removed H4l batch output: {batch_root}")
    else:
        print(f"No H4l batch output found: {batch_root}")


def _run(args: argparse.Namespace) -> None:
    continue_run = getattr(args, "continue_run", False)
    if continue_run and (getattr(args, "clean", False) or args.plan_only):
        raise WorkflowError("--continue cannot be combined with --clean or --plan-only", 2)
    if getattr(args, "clean", False):
        _clean(args)
        return
    config = _load_config(_resolve(args.config))
    protocol = _resolve(args.protocol or config["protocol"])
    seeds = list(config["seeds"]) if args.seed is None else [args.seed]
    complete = seeds == list(EXPECTED_SEEDS)
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
            prepare_root = RUNS_ROOT / prepare_directory_name(run_name)
        except ValueError as error:
            raise WorkflowError(str(error), 2) from error
        prepared = prepare_root / "prepare"
        gate = root / "g1" / "templates"
        t1_validation = prepare_root / "inputs" / "t1-validation.json"
        batch_root = root / "batch" / ("all-seeds" if complete else f"seed{seeds[0]}")
    else:
        prepared = _resolve(args.prepared_run or config["prepared_run"])
        gate = _resolve(args.gate_run or config["g1_gate_run"])
        t1_validation = _resolve(args.t1_validation or config["t1_validation"])
        configured_value = args.output_root or config["output_root"]
        configured_root = _resolve(configured_value)
        batch_root = (configured_root / f"seed{seeds[0]}"
                      if args.output_root is None and not complete else configured_root)

    try:
        relative = batch_root.relative_to(RUNS_ROOT)
    except ValueError as error:
        raise WorkflowError(
            f"OutputRoot must be a child of the runs directory: {batch_root}", 4
        ) from error
    if not relative.parts:
        raise WorkflowError("OutputRoot cannot be the runs directory itself", 4)
    if not protocol.is_file():
        raise WorkflowError(f"Research protocol does not exist: {protocol}", 3)
    if not args.plan_only:
        for required in (prepared, gate, t1_validation):
            if not required.exists():
                raise WorkflowError(f"Required bound input does not exist: {required}", 3)
        _validate_t1(t1_validation, protocol, config["dataset"])
        if continue_run and (not batch_root.is_dir() or batch_root.is_symlink()):
            raise WorkflowError(
                f"OutputRoot must be an existing ordinary directory for --continue: {batch_root}", 4
            )
        if not continue_run and batch_root.exists():
            raise WorkflowError(f"OutputRoot already exists and cannot be reused: {batch_root}", 4)

    continuation_protocol = (
        load_protocol(protocol, dataset=config["dataset"]).to_dict() if continue_run else None
    )

    common = ["--dataset", config["dataset"], "--protocol", str(protocol)]
    calibration_runs: list[Path] = []
    training_runs: list[Path] = []
    steps: list[tuple[str, list[str]]] = []
    for seed in seeds:
        seed_root = batch_root / f"seed{seed}"
        train_root = seed_root / "train"
        calibration_root = seed_root / "calibrate"
        model_runs = {name:train_root / name.lower() for name in ("M0c", "M2", "M3")}
        for candidate in ("M0c", "M2", "M3"):
            steps.append((f"train {candidate} seed {seed}", [
                "train", *common, "--input-run", str(prepared), "--gate-run", str(gate),
                "--candidate", candidate, "--seed", str(seed),
                "--run-dir", str(model_runs[candidate]),
            ]))
            training_runs.append(model_runs[candidate])
        for candidate, transform, name in (
            ("M0c", "raw", "m0c-raw"),
            ("M2", "raw", "m2-raw"),
            ("M2", "physical", "m4-physical"),
            ("M3", "raw", "m3-raw"),
            ("M3", "physical", "m5-physical"),
        ):
            calibration_run = calibration_root / name
            steps.append((f"calibrate {name} seed {seed}", [
                "calibrate", *common, "--input-run", str(prepared),
                "--model-run", str(model_runs[candidate]), "--transform", transform,
                "--seed", str(seed), "--run-dir", str(calibration_run),
            ]))
            calibration_runs.append(calibration_run)

        for groups in EXPECTED_COMBINATIONS:
            train_run = train_root / f"groups-{groups}"
            calibration_run = calibration_root / f"groups-{groups}"
            steps.append((f"train groups {groups} seed {seed}", [
                "train", *common, "--input-run", str(prepared), "--gate-run", str(gate),
                "--candidate", "M3", "--groups", groups, "--seed", str(seed),
                "--run-dir", str(train_run),
            ]))
            training_runs.append(train_run)
            steps.append((f"calibrate groups {groups} seed {seed}", [
                "calibrate", *common, "--input-run", str(prepared),
                "--model-run", str(train_run), "--transform", "raw", "--seed", str(seed),
                "--run-dir", str(calibration_run),
            ]))
            calibration_runs.append(calibration_run)
            off_train_run = train_root / f"groups-{groups}-m4l-off"
            off_calibration_run = calibration_root / f"groups-{groups}-m4l-off"
            steps.append((f"train groups {groups} m4l off seed {seed}", [
                "train", *common, "--input-run", str(prepared), "--gate-run", str(gate),
                "--candidate", "M3", "--groups", groups, "--mass-input", "off",
                "--seed", str(seed), "--run-dir", str(off_train_run),
            ]))
            training_runs.append(off_train_run)
            steps.append((f"calibrate groups {groups} m4l off seed {seed}", [
                "calibrate", *common, "--input-run", str(prepared),
                "--model-run", str(off_train_run), "--transform", "raw", "--seed", str(seed),
                "--run-dir", str(off_calibration_run),
            ]))
            calibration_runs.append(off_calibration_run)

    template_run = batch_root / "templates"
    template_arguments = [
        "templates", *common, "--input-run", str(prepared),
        "--t1-validation", str(t1_validation), "--seed", str(seeds[0]),
        "--run-dir", str(template_run),
    ]
    for calibration_run in calibration_runs:
        template_arguments.extend(["--calibration-run", str(calibration_run)])
    steps.append(("templates common grid", template_arguments))

    inference_run = batch_root / "inference"
    steps.append(("infer common T1", [
        "infer", *common, "--template-run", str(template_run), "--layer", "T1",
        "--mu", "1", "--seed", str(seeds[0]), "--run-dir", str(inference_run),
    ]))
    report_run = batch_root / "report"
    report_arguments = [
        "report", *common, "--result-run", str(inference_run),
        "--evaluation-run", str(template_run),
        "--seed", str(seeds[0]), "--run-dir", str(report_run),
    ]
    for training_run in training_runs:
        report_arguments.extend(["--training-run", str(training_run)])
    steps.append(("report conclusions", report_arguments))

    description = "H4l complete seeds 42-46" if complete else f"H4l diagnostic seed {seeds[0]}"
    with tqdm(steps, desc=description, unit="stage",
              disable=args.plan_only or args.no_progress) as progress:
        for label, arguments in progress:
            progress.set_postfix_str(label, refresh=True)
            if continue_run:
                action = _continue_stage(
                    arguments, batch_root=batch_root, dataset=config["dataset"],
                    protocol=continuation_protocol,
                )
                if action == "skip":
                    continue
                run_dir = arguments[arguments.index("--run-dir") + 1]
                print(f"{action.upper()}: {run_dir}", flush=True)
            invoke_options = {"plan_only": args.plan_only}
            if getattr(args, "show_command", False):
                invoke_options["show_command"] = True
            _invoke(arguments, **invoke_options)

    if args.plan_only:
        print(f"Plan complete: {len(seeds)} seed(s), {33 * len(seeds)} model trainings, "
              f"{35 * len(seeds)} calibrations, one common template, inference, and report; "
              "no run was created.")
        return

    report_path = report_run / "report.json"
    try:
        with report_path.open(encoding="utf-8") as stream:
            report = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowError(f"Cannot read batch report: {report_path}: {error}", 3) from error
    comparisons = report.get("feature_combination_comparisons", [])
    valid_seeds = sorted(item.get("seed") for item in comparisons if item.get("status") == "valid")
    if valid_seeds != seeds:
        raise WorkflowError(
            "The batch completed, but one or more complete 15-combination comparisons are unavailable.", 5
        )
    mass_valid_seeds = sorted(item.get("seed") for item in report.get("mass_input_comparisons", [])
                              if item.get("status") == "valid")
    if mass_valid_seeds != seeds:
        raise WorkflowError(
            "The batch completed, but one or more complete m4l on/off comparisons are unavailable.", 5
        )
    if complete:
        if report.get("feature_combination_summary", {}).get("status") != "valid":
            raise WorkflowError("The five-seed feature-combination summary is unavailable.", 5)
        if report.get("primary_comparison", {}).get("status") != "valid":
            raise WorkflowError("The five-seed M4/M5 primary comparison is unavailable.", 5)
        if report.get("mass_input_summary", {}).get("status") != "valid":
            raise WorkflowError("The five-seed m4l on/off comparison is unavailable.", 5)
    _print_conclusions(report, report_run / "report.md", complete=complete)


def main() -> int:
    try:
        _run(_parser().parse_args())
    except WorkflowError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
