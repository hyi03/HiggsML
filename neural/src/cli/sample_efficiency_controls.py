"""Thin exact-config CLI for M6 controls and noninferiority confirmation."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from src.research.artifacts import read_json, read_run
from src.research.errors import ResearchError
from src.research.protocol import canonical, load_protocol
from src.research.sample_efficiency import read_sample_efficiency_report
from src.research.sample_efficiency_confirmation import publish_confirmation
from src.research.sample_efficiency_controls import publish_sample_efficiency_controls
from src.research.sample_efficiency_protocol import (load_compact_candidate_freeze,
                                                       load_sample_efficiency_protocol)
from src.research.sample_efficiency_workflow import read_learning_curve_batch
from src.artifacts.transaction import RunPathError


CONFIG_SCHEMA = "h4l-sample-efficiency-controls-config-v1"
CONFIG_KEYS = {
    "schema_version", "mode", "dataset", "protocol", "sample_efficiency_protocol",
    "prepared_run", "compact_freeze_run", "training_subsets_run", "gate_run",
    "t1_validation", "batch_run", "report_run", "exclusion_identity_sets",
    "confirmation_input", "output_root", "output_name", "repeat",
}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = (PROJECT_ROOT / "runs").resolve()


def build_parser():
    parser = argparse.ArgumentParser(prog="h4l-sample-efficiency-controls",
        description="Run registered M6 mechanism controls or claim-before-decode confirmation.")
    parser.add_argument("--dataset", choices=["atlas2020_4lep"], required=True)
    parser.add_argument("--config", required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--controls-only", action="store_true")
    modes.add_argument("--confirm", action="store_true")
    return parser


def _config(path):
    raw = read_json(Path(path))
    if type(raw) is not dict or set(raw) != CONFIG_KEYS or raw.get("schema_version") != CONFIG_SCHEMA:
        raise ResearchError("invalid exact M6 config", status="training_subset_binding_mismatch")
    mode = raw.get("mode")
    if mode not in {"controls-only", "confirm"} or raw.get("dataset") != "atlas2020_4lep":
        raise ResearchError("invalid M6 config mode or dataset", status="training_subset_binding_mismatch")
    text_fields = CONFIG_KEYS - {"schema_version", "mode", "dataset", "exclusion_identity_sets",
                                 "confirmation_input", "repeat"}
    if any(type(raw.get(key)) is not str or not raw[key] for key in text_fields):
        raise ResearchError("M6 config requires explicit paths", status="training_subset_binding_mismatch")
    if (type(raw.get("exclusion_identity_sets")) is not list
            or any(type(item) is not str or not item for item in raw["exclusion_identity_sets"])
            or type(raw.get("repeat")) is not bool):
        raise ResearchError("invalid M6 exclusion/repeat config", status="training_subset_binding_mismatch")
    if mode == "controls-only":
        if raw["confirmation_input"] is not None or raw["repeat"] or raw["exclusion_identity_sets"]:
            raise ResearchError("controls-only config cannot access confirmation inputs",
                                status="training_subset_binding_mismatch")
    elif (type(raw["confirmation_input"]) is not str or not raw["confirmation_input"]
          or not raw["exclusion_identity_sets"]):
        raise ResearchError("confirmation config requires input and exclusion identity sets",
                            status="training_subset_binding_mismatch")
    return raw


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = _config(args.config)
        requested_mode = "controls-only" if args.controls_only else "confirm"
        if config["mode"] != requested_mode or config["dataset"] != args.dataset:
            raise ResearchError("CLI mode/dataset differs from exact config",
                                status="training_subset_binding_mismatch")
        if Path(config["output_root"]).resolve() != RUNS_ROOT:
            raise ResearchError("M6 output root must be the project runs directory",
                                status="training_subset_binding_mismatch")
        target = RUNS_ROOT / config["output_name"]
        base = load_protocol(config["protocol"], dataset=args.dataset)
        prepared = read_run(config["prepared_run"], dataset=args.dataset,
                            protocol=base.to_dict(), stages=("prepare",))
        freeze_run = read_run(config["compact_freeze_run"], dataset=args.dataset,
                             protocol=base.to_dict(), stages=("compact-freeze",))
        subset_run = read_run(config["training_subsets_run"], dataset=args.dataset,
                             protocol=base.to_dict(), stages=("training-subsets",))
        gate_run = read_run(config["gate_run"], dataset=args.dataset,
                           protocol=base.to_dict(), stages=("templates",))
        freeze = load_compact_candidate_freeze(freeze_run.file("freeze.json"), base_protocol=base)
        subset_plan = subset_run.read_json("training-subsets.json")
        overlay = load_sample_efficiency_protocol(config["sample_efficiency_protocol"],
            base_protocol=base, prepared_artifact_id=prepared.manifest["artifact_id"],
            population_id=subset_plan["population_id"], compact_freeze=freeze,
            compact_freeze_artifact_id=freeze_run.manifest["artifact_id"])
        evidence = read_json(Path(config["t1_validation"]))
        if requested_mode == "controls-only":
            result = publish_sample_efficiency_controls(target, allowed_root=RUNS_ROOT,
                prepared=prepared, freeze_run=freeze_run, subset_run=subset_run,
                gate_run=gate_run, t1_validation=evidence, batch_path=config["batch_run"],
                report_path=config["report_run"], base=base, overlay=overlay)
            print(canonical({"stage": result.run.manifest["stage"],
                             "artifact_id": result.run.manifest["artifact_id"],
                             "capacity_status": result.capacity["status"],
                             "cdf_status": result.cdf["status"]}).decode("utf-8"))
            return 0
        batch = read_learning_curve_batch(config["batch_run"], prepared=prepared,
            freeze_run=freeze_run, subset_run=subset_run, gate_run=gate_run,
            t1_validation=evidence, base=base, overlay=overlay)
        report = read_sample_efficiency_report(config["report_run"], batch_path=config["batch_run"],
            prepared=prepared, freeze_run=freeze_run, subset_run=subset_run, gate_run=gate_run,
            t1_validation=evidence, base=base, overlay=overlay)
        _, confirmation = publish_confirmation(target, allowed_root=RUNS_ROOT,
            input_path=config["confirmation_input"],
            exclusion_identity_sets=config["exclusion_identity_sets"], base=base,
            overlay=overlay, freeze=freeze, freeze_artifact_id=freeze_run.manifest["artifact_id"],
            upstreams=[freeze_run, batch.run, report.run], repeat=config["repeat"])
        print(canonical(confirmation).decode("utf-8"))
        return 0
    except (ResearchError, RunPathError) as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
