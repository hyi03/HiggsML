"""Thin CLI for the isolated MC-only sample-efficiency batch."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4

from src.research.artifacts import read_json, read_run
from src.research.errors import ResearchError
from src.research.protocol import canonical, load_protocol
from src.research.resources import load_resources
from src.research.sample_efficiency_protocol import (load_compact_candidate_freeze,
                                                       load_sample_efficiency_protocol)
from src.research.sample_efficiency_workflow import (build_learning_curve_plan,
                                                       execute_learning_curve)


CONFIG_SCHEMA = "h4l-sample-efficiency-batch-config-v1"
CONFIG_KEYS = {"schema_version", "dataset", "protocol", "sample_efficiency_protocol",
               "prepared_run", "compact_freeze_run", "training_subsets_run", "gate_run",
               "t1_validation", "output_root", "output_name"}
_REPARSE_POINT = 0x400
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = (PROJECT_ROOT / "runs").resolve()


def build_parser():
    parser = argparse.ArgumentParser(prog="h4l-learning-curve",
        description="Run the registered MC-only H4l sample-efficiency batch.")
    parser.add_argument("--dataset", choices=["atlas2020_4lep"], required=True)
    parser.add_argument("--config")
    parser.add_argument("--protocol")
    parser.add_argument("--sample-efficiency-protocol")
    parser.add_argument("--prepared-run")
    parser.add_argument("--compact-freeze-run")
    parser.add_argument("--training-subsets-run")
    parser.add_argument("--gate-run")
    parser.add_argument("--t1-validation")
    parser.add_argument("--output-root")
    parser.add_argument("--resources")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    return parser


def _is_reparse(path):
    if path.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(path)):
        return True
    try:
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & _REPARSE_POINT)
    except FileNotFoundError:
        return False


def clean_unstarted_batch(target, *, allowed_root, execution_plan_id):
    raw_target = Path(target)
    raw_root = Path(allowed_root)
    if ".." in raw_target.parts or ".." in raw_root.parts:
        raise ResearchError("clean target contains parent traversal",
                            status="training_subset_binding_mismatch")
    root = raw_root.resolve(strict=True)
    target = raw_target.resolve(strict=True)
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise ResearchError("clean target is outside the allowed run root",
                            status="training_subset_binding_mismatch") from exc
    if len(relative.parts) != 1 or not target.is_dir() or _is_reparse(root):
        raise ResearchError("clean target is not an owned batch child",
                            status="training_subset_binding_mismatch")
    if _is_reparse(target):
        raise ResearchError("clean target contains a link or reparse point",
                            status="training_subset_binding_mismatch")
    allowed = {".sample-efficiency-owner.json", "staging"}
    if {item.name for item in target.iterdir()} - allowed:
        raise ResearchError("clean target contains published or unknown evidence",
                            status="training_subset_binding_mismatch")
    staging = target / "staging"
    if staging.exists() and (not staging.is_dir() or _is_reparse(staging) or any(staging.iterdir())):
        raise ResearchError("clean staging directory is not empty and owned",
                            status="training_subset_binding_mismatch")
    marker_path = target / ".sample-efficiency-owner.json"
    marker = read_json(marker_path)
    if (type(marker) is not dict or set(marker) != {"schema_version", "execution_plan_id", "target"}
            or marker.get("schema_version") != "h4l-sample-efficiency-owner-v1"
            or marker.get("execution_plan_id") != execution_plan_id
            or marker.get("target") != str(target.resolve())):
        raise ResearchError("clean ownership proof mismatch",
                            status="training_subset_binding_mismatch")
    quarantine = root / f".{target.name}.cleaning-{uuid4().hex}"
    target.rename(quarantine)
    resolved_quarantine = quarantine.resolve(strict=True)
    if (resolved_quarantine.parent != root or _is_reparse(resolved_quarantine)
            or {item.name for item in resolved_quarantine.iterdir()} - allowed):
        quarantine.rename(target)
        raise ResearchError("clean target changed during deletion",
                            status="training_subset_binding_mismatch")
    shutil.rmtree(resolved_quarantine)


def _load_config(path):
    if path is None:
        return {}
    raw = read_json(Path(path))
    if (type(raw) is not dict or set(raw) != CONFIG_KEYS
            or raw.get("schema_version") != CONFIG_SCHEMA
            or raw.get("dataset") != "atlas2020_4lep"
            or any(type(raw[key]) is not str or not raw[key] for key in CONFIG_KEYS - {"schema_version", "dataset"})):
        raise ResearchError("invalid sample-efficiency batch config",
                            status="training_subset_binding_mismatch")
    return raw


def _value(args, config, name):
    value = getattr(args, name)
    return value if value is not None else config.get(name)


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.clean and args.plan_only:
        build_parser().error("--clean and --plan-only are mutually exclusive")
    try:
        config = _load_config(args.config)
        if config and config["dataset"] != args.dataset:
            raise ResearchError("CLI dataset differs from batch config",
                                status="training_subset_binding_mismatch")
        required = ("protocol", "sample_efficiency_protocol", "prepared_run", "compact_freeze_run",
                    "training_subsets_run", "gate_run", "t1_validation", "output_root")
        values = {name: _value(args, config, name) for name in required}
        if any(not value for value in values.values()):
            raise ResearchError("batch paths must be supplied by CLI or exact config",
                                status="training_subset_binding_mismatch")
        if Path(values["output_root"]).resolve() != RUNS_ROOT:
            raise ResearchError("batch output root must be the project runs directory",
                                status="training_subset_binding_mismatch")
        output_name = config.get("output_name", "sample-efficiency")
        base = load_protocol(values["protocol"], dataset=args.dataset)
        prepared = read_run(values["prepared_run"], dataset=args.dataset,
                            protocol=base.to_dict(), stages=("prepare",))
        freeze_run = read_run(values["compact_freeze_run"], dataset=args.dataset,
                             protocol=base.to_dict(), stages=("compact-freeze",))
        subset_run = read_run(values["training_subsets_run"], dataset=args.dataset,
                             protocol=base.to_dict(), stages=("training-subsets",))
        gate_run = read_run(values["gate_run"], dataset=args.dataset,
                           protocol=base.to_dict(), stages=("templates",))
        subset_plan = subset_run.read_json("training-subsets.json")
        freeze = load_compact_candidate_freeze(freeze_run.file("freeze.json"), base_protocol=base)
        overlay = load_sample_efficiency_protocol(values["sample_efficiency_protocol"],
            base_protocol=base, prepared_artifact_id=prepared.manifest["artifact_id"],
            population_id=subset_plan["population_id"], compact_freeze=freeze,
            compact_freeze_artifact_id=freeze_run.manifest["artifact_id"])
        evidence = read_json(Path(values["t1_validation"]))
        resources = {"workers": load_resources(args.resources)["workers"]}
        kwargs = dict(prepared=prepared, freeze_run=freeze_run, subset_run=subset_run,
            gate_run=gate_run, t1_validation=evidence, base=base, overlay=overlay,
            output_root=Path(values["output_root"]), output_name=output_name,
            resources=resources, progress=not args.no_progress)
        plan = build_learning_curve_plan(**kwargs)
        if args.plan_only:
            print(canonical(plan).decode("utf-8"))
            return 0
        target = Path(values["output_root"]).resolve() / output_name
        if args.clean:
            clean_unstarted_batch(target, allowed_root=RUNS_ROOT,
                                  execution_plan_id=plan["execution_plan_id"])
            return 0
        result = execute_learning_curve(**kwargs)
        print(canonical(result.summary).decode("utf-8"))
        return 0
    except ResearchError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
