"""CLI for receipt-bound M5 sample-efficiency reports."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from src.artifacts.transaction import RunPathError
from src.research.artifacts import read_json, read_run
from src.research.errors import ResearchError
from src.research.protocol import canonical, load_protocol
from src.research.sample_efficiency import publish_sample_efficiency_report
from src.research.sample_efficiency_protocol import (load_compact_candidate_freeze,
                                                       load_sample_efficiency_protocol)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = (PROJECT_ROOT / "runs").resolve()
CONFIG_SCHEMA = "h4l-sample-efficiency-report-config-v1"
CONFIG_KEYS = {"schema_version", "dataset", "protocol", "sample_efficiency_protocol",
               "prepared_run", "compact_freeze_run", "training_subsets_run", "gate_run",
               "t1_validation", "batch_run", "output_root", "output_name"}


def build_parser():
    parser = argparse.ArgumentParser(prog="h4l-sample-efficiency-report")
    parser.add_argument("--dataset", choices=["atlas2020_4lep"], required=True)
    parser.add_argument("--config")
    for name in ("protocol", "sample-efficiency-protocol", "prepared-run", "compact-freeze-run",
                 "training-subsets-run", "gate-run", "t1-validation", "batch-run",
                 "output-root", "output-name"):
        parser.add_argument(f"--{name}")
    return parser


def _load_config(path):
    if path is None:
        return {}
    value = read_json(Path(path))
    if (type(value) is not dict or set(value) != CONFIG_KEYS
            or value.get("schema_version") != CONFIG_SCHEMA
            or value.get("dataset") != "atlas2020_4lep"
            or any(type(value[key]) is not str or not value[key]
                   for key in CONFIG_KEYS - {"schema_version", "dataset"})):
        raise ResearchError("invalid sample-efficiency report config",
                            status="training_subset_binding_mismatch")
    return value


def _safe_name(value):
    if (type(value) is not str or not value or value in {".", ".."}
            or any(character in value for character in "/\\:")):
        raise ResearchError("invalid report output name", status="training_subset_binding_mismatch")
    return value


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        config = _load_config(args.config)
        if config and config["dataset"] != args.dataset:
            raise ResearchError("CLI dataset differs from report config",
                                status="training_subset_binding_mismatch")
        names = CONFIG_KEYS - {"schema_version", "dataset"}
        values = {name: getattr(args, name) or config.get(name) for name in names}
        if any(not value for value in values.values()):
            raise ResearchError("all report paths and output name are required",
                                status="training_subset_binding_mismatch")
        if Path(values["output_root"]).resolve() != RUNS_ROOT:
            raise ResearchError("report output root must be the project runs directory",
                                status="training_subset_binding_mismatch")
        output_name = _safe_name(values["output_name"])
        target = RUNS_ROOT / output_name
        if target.exists() or target.parent != RUNS_ROOT:
            raise ResearchError("report target must be a fresh runs child",
                                status="training_subset_binding_mismatch")
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
        result = publish_sample_efficiency_report(target, allowed_root=RUNS_ROOT,
            batch_path=values["batch_run"], prepared=prepared, freeze_run=freeze_run,
            subset_run=subset_run, gate_run=gate_run,
            t1_validation=read_json(Path(values["t1_validation"])), base=base, overlay=overlay)
        print(canonical(result.summary).decode("utf-8"))
        return 0
    except ResearchError as exc:
        print(str(exc), file=sys.stderr); return exc.exit_code
    except RunPathError as exc:
        print(str(exc), file=sys.stderr); return 3
    except Exception as exc:
        print(str(exc), file=sys.stderr); return 70


if __name__ == "__main__":
    raise SystemExit(main())
