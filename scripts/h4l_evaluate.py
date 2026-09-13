#!/usr/bin/env python3
"""Execute a sealed H4l evaluation matrix and publish one enhanced report."""
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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = (PROJECT_ROOT / "runs").resolve()
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from higgsml.artifacts import digest_json  # noqa: E402
from higgsml.protocol import load_protocol  # noqa: E402


DEFAULT_PROTOCOL = PROJECT_ROOT / "config" / "protocols" / "h4l_protocol.json"
PLAN_SCHEMA = PROJECT_ROOT / "config" / "schemas" / "h4l_evaluation_plan_v1.schema.json"


class EvaluationError(Exception):
    def __init__(self, message, exit_code=3):
        super().__init__(message)
        self.exit_code = exit_code


def _parser():
    parser = argparse.ArgumentParser(description="Run a sealed MC bootstrap, Toy, assessment, T2, and stress evaluation matrix.")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--prepared-run", type=Path, required=True)
    parser.add_argument("--template-run", type=Path, required=True)
    parser.add_argument("--freeze-run", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--training-run", type=Path, action="append", default=[])
    parser.add_argument("--evidence-run", type=Path, action="append", default=[])
    parser.add_argument("--plan-only", action="store_true")
    return parser


def _resolve(path):
    value = path.expanduser()
    return (value if value.is_absolute() else PROJECT_ROOT / value).resolve()


def _display(command):
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


def _load_plan(path, protocol):
    try:
        plan = json.loads(path.read_text(encoding="utf-8-sig"))
        schema = json.loads(PLAN_SCHEMA.read_text(encoding="utf-8-sig"))
        Draft202012Validator(schema).validate(plan)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        raise EvaluationError(f"Invalid evaluation plan: {error}") from error
    if plan["protocol_sha256"] != digest_json(protocol):
        raise EvaluationError("Evaluation plan protocol digest mismatch")
    budget = protocol["inference"]
    for section in ("model_self", "assessment"):
        if plan[section]["toys_per_injection"] > budget["toy_count"] or plan[section]["seed"] != budget["toy_seed"]:
            raise EvaluationError(f"{section} exceeds the frozen protocol budget")
    if plan["stress"]["toys"] > budget["toy_count"] or plan["stress"]["seed"] != budget["toy_seed"]:
        raise EvaluationError("stress evaluation exceeds the frozen protocol budget")
    if plan["t2"] != {"mu": 1, "seed": budget["toy_seed"],
                       "outer_replicas": budget["outer_replicas"],
                       "inner_toys": budget["inner_toys"]}:
        raise EvaluationError("T2 plan differs from the registered pilot endpoint")
    return plan


def _run(args):
    protocol_path = _resolve(args.protocol)
    protocol = load_protocol(protocol_path).to_dict()
    plan_path = _resolve(args.plan)
    plan = _load_plan(plan_path, protocol)
    prepared, templates, freeze, output = map(_resolve, (args.prepared_run, args.template_run, args.freeze_run, args.output_root))
    try:
        relative = output.relative_to(RUNS_ROOT)
    except ValueError as error:
        raise EvaluationError("Evaluation output must be below runs", 4) from error
    if not relative.parts:
        raise EvaluationError("Evaluation output cannot be the runs root", 4)
    if not args.plan_only:
        for path in (prepared, templates, freeze):
            if not path.is_dir():
                raise EvaluationError(f"Required run does not exist: {path}")
        for name, path in (("prepared_artifact_id", prepared), ("template_artifact_id", templates),
                           ("freeze_artifact_id", freeze)):
            try:
                manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as error:
                raise EvaluationError(f"Cannot read bound input manifest: {path}") from error
            if manifest.get("artifact_id") != plan["inputs"][name]:
                raise EvaluationError(f"Evaluation plan {name} mismatch")
        if output.exists():
            raise EvaluationError(f"Evaluation output already exists: {output}", 4)
    common = ["--dataset", plan["dataset"], "--protocol", str(protocol_path)]
    steps = []
    bootstrap = output / "mc-bootstrap"
    steps.append((bootstrap, ["mc-bootstrap", *common, "--input-run", str(prepared), "--template-run", str(templates),
        "--evaluation-plan", str(plan_path), "--replicas", str(plan["mc_bootstrap"]["replicas"]),
        "--bootstrap-seed", str(plan["mc_bootstrap"]["seed"]), "--run-dir", str(bootstrap)]))
    model_self = []
    primary_model_self = None
    for mu in plan["model_self"]["injections"]:
        target = output / "model-self" / f"mu{mu}"
        model_self.append(target)
        if mu == 1:
            primary_model_self = target
        steps.append((target, ["infer", *common, "--template-run", str(templates), "--layer", "T1", "--mu", str(mu),
            "--toys", str(plan["model_self"]["toys_per_injection"]), "--seed", str(plan["model_self"]["seed"]), "--run-dir", str(target)]))
    assessment = []
    first_assessment = True
    for mu in plan["assessment"]["injections"]:
        target = output / "assessment" / f"mu{mu}"
        command = ["infer", *common, "--input-run", str(prepared), "--template-run", str(templates), "--freeze-run", str(freeze),
            "--expectation-kind", "assessment", "--layer", "T1", "--mu", str(mu),
            "--toys", str(plan["assessment"]["toys_per_injection"]), "--seed", str(plan["assessment"]["seed"]), "--run-dir", str(target)]
        if not first_assessment:
            command.append("--repeat-assessment")
        first_assessment = False
        assessment.append(target); steps.append((target, command))
    t2 = output / "t2"
    steps.append((t2, ["infer", *common, "--input-run", str(prepared), "--template-run", str(templates), "--freeze-run", str(freeze),
        "--expectation-kind", "assessment", "--procedure", "t2", "--layer", "T1", "--mu", str(plan["t2"]["mu"]),
        "--seed", str(plan["t2"]["seed"]), "--repeat-assessment", "--run-dir", str(t2)]))
    stresses = []
    for kind in plan["stress"]["kinds"]:
        for direction in plan["stress"]["directions"]:
            for mode in plan["stress"]["modes"]:
                direction_name = "minus1" if direction < 0 else "plus1"
                target = output / "stress" / f"{kind}-{direction_name}-{mode}"
                stresses.append(target)
                steps.append((target, ["infer", *common, "--input-run", str(prepared), "--template-run", str(templates),
                    "--freeze-run", str(freeze), "--expectation-kind", "assessment", "--procedure", "stress",
                    "--stress-kind", kind, "--stress-direction", str(direction), "--stress-mode", mode, "--layer", "T1",
                    "--mu", str(plan["stress"]["mu"]), "--toys", str(plan["stress"]["toys"]),
                    "--seed", str(plan["stress"]["seed"]), "--repeat-assessment", "--run-dir", str(target)]))
    report = output / "report"
    if primary_model_self is None:
        raise EvaluationError("Evaluation plan has no mu=1 model-self result")
    report_command = ["report", *common, "--result-run", str(primary_model_self),
                      "--evaluation-plan", str(plan_path), "--evaluation-run", str(templates),
                      "--evaluation-run", str(bootstrap), "--run-dir", str(report)]
    for path in [*(path for path in model_self if path != primary_model_self), *assessment, t2, *stresses]:
        report_command.extend(["--evaluation-run", str(path)])
    for path in args.training_run:
        report_command.extend(["--training-run", str(_resolve(path))])
    for path in args.evidence_run:
        report_command.extend(["--evidence-run", str(_resolve(path))])
    steps.append((report, report_command))
    for _, arguments in steps:
        command = [sys.executable, "-m", "higgsml.cli", *arguments]
        print(_display(command), flush=True)
        if not args.plan_only:
            completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
            if completed.returncode:
                raise EvaluationError(f"Evaluation stage failed with exit code {completed.returncode}", completed.returncode)
    state = "validated; input receipts deferred" if args.plan_only else "completed"
    print(f"Evaluation plan {state}: {len(steps)} stages; registration={plan['registration_status']}; plan_id={digest_json(plan)}")


def main():
    try:
        _run(_parser().parse_args())
    except EvaluationError as error:
        print(error, file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
