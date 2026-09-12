"""Synthetic, MC-only fixtures shared by sample-efficiency Sprint tests."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.research.artifacts import ResearchRun, read_run
from src.research.data import role_for_group, write_research_data
from src.research.protocol import load_protocol
from src.research.representations import representation_features
from src.research.sample_efficiency_protocol import SampleEfficiencyProtocol, freeze_compact_candidate
from src.research.training_subsets import publish_training_subsets


def _groups(protocol, role, count):
    values = []
    index = 0
    while len(values) < count:
        group = f"m3-{role}-{index}"
        if role_for_group(group, protocol.to_dict()) == role:
            values.append(group)
        index += 1
    return values


def build_sample_efficiency_fixture(tmp_path, *, fractions=(0.5, 1.0), draws=(100, 101),
                                    minimum_groups=2, minimum_effective=2.0, template_groups=80):
    base = load_protocol()
    rng = np.random.default_rng(20260912)
    rows = []
    role_counts = {"train": 48, "validation": 40, "calibration": 240, "template": template_groups}
    features = list(representation_features("engineered19"))
    serial = 0
    for role, count in role_counts.items():
        for index, group in enumerate(_groups(base, role, count)):
            label = index % 2
            row = {name: float(rng.normal(loc=0.2 * label, scale=1.0)) for name in features}
            row["m4l"] = 106.0 + 33.0 * ((index + 0.25 * label) % count) / count
            row["y4l"] = float(rng.normal())
            probability = base["roles"][role] * base["development_probability"]
            row.update(event_id=f"m3-event-{serial}", source_row_id=f"m3-row-{serial}",
                       event_group_id=group, split="development", dataset=base["dataset"], label=label,
                       role=role, physical_weight=1.0 + 0.01 * (index % 5),
                       sampling_probability=probability,
                       yield_weight=(1.0 + 0.01 * (index % 5)) / probability,
                       process="signal" if label else "background")
            rows.append(row)
            serial += 1
    frame = pd.DataFrame(rows)
    frame.attrs["source_kind"] = "synthetic"
    prepared_root = tmp_path / "prepared"
    with ResearchRun(prepared_root, allowed_root=tmp_path, stage="prepare", dataset=base["dataset"],
                     protocol=base.to_dict()) as run:
        receipt = write_research_data(frame, run.path / "events.jsonl", base)
        run.register_streamed_file("events.jsonl", sha256=receipt.sha256, size_bytes=receipt.size_bytes)
        run.manifest["context"]["population_id"] = receipt.population_id
    prepared = read_run(prepared_root, dataset=base["dataset"], protocol=base.to_dict(), stages=("prepare",))

    metadata = {"discovery_prepared_artifact_ids": ["synthetic-discovery"],
        "discovery_report_artifact_ids": ["synthetic-report"], "selection_artifact_ids": ["synthetic-report"],
        "discovery_population_ids": ["synthetic-discovery-population"],
        "browsed_population_ids": ["synthetic-discovery-population"],
        "excluded_population_ids": ["synthetic-discovery-population"],
        "selection_rule_version": "synthetic-m3-v1", "selection_reason": "synthetic software test",
        "evidence_status": "exploratory_only", "delta_w68": 0.1, "delta_source": "synthetic-test-only"}
    freeze = freeze_compact_candidate(metadata, groups=["A", "B"], base_protocol=base)
    freeze_root = tmp_path / "freeze"
    with ResearchRun(freeze_root, allowed_root=tmp_path, stage="compact-freeze", dataset=base["dataset"],
                     protocol=base.to_dict()) as run:
        run.write_json("freeze.json", freeze.to_dict())
    freeze_run = read_run(freeze_root, dataset=base["dataset"], protocol=base.to_dict(),
                          stages=("compact-freeze",))

    raw = json.loads((Path(__file__).resolve().parents[2] /
                      "config/research_sample_efficiency_protocol_v1.json").read_text(encoding="utf-8"))
    raw.update(protocol_id="synthetic-m3", base_research_protocol_sha256=base.digest,
        prepared_artifact_id=prepared.manifest["artifact_id"], population_id=receipt.population_id,
        compact_candidate_freeze_artifact_id=freeze_run.manifest["artifact_id"],
        compact_candidate_freeze_sha256=freeze.digest,
        representations=["decay7", "compact:AB", "engineered19"],
        sample_fractions=list(fractions), sample_draw_seeds=list(draws))
    raw["subset_algorithm"].update(min_groups_per_label=minimum_groups,
                                    min_effective_count=minimum_effective)
    raw["noninferiority"].update(delta_w68=0.1, delta_source="synthetic-test-only",
                                  confidence_level=0.95, bootstrap_replicates=20, bootstrap_seed=300)
    raw["evaluation_uncertainty"].update(replicates=20, seed=200)
    raw["capacity_control"].update(enabled=False, sample_fractions=[], network_seeds=[])
    raw["cdf_check"].update(enabled=False, representations=raw["representations"], sample_fractions=[])
    raw["quality_target"].update(enabled=False)
    overlay = SampleEfficiencyProtocol(raw, base_protocol=base,
        prepared_artifact_id=prepared.manifest["artifact_id"], population_id=receipt.population_id,
        compact_freeze=freeze, compact_freeze_artifact_id=freeze_run.manifest["artifact_id"])
    subset_run = publish_training_subsets(tmp_path / "subsets", allowed_root=tmp_path,
        prepared=prepared, freeze_run=freeze_run, base=base, overlay=overlay)
    return base, prepared, freeze_run, overlay, subset_run
