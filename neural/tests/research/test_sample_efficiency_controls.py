from __future__ import annotations

import pytest
import pandas as pd

from src.artifacts.transaction import RunPathError
from src.research.artifacts import ResearchRun, read_run
from src.research.calibration import digest
from src.research.errors import ResearchError
from src.research.sample_efficiency import publish_sample_efficiency_report
from src.research.sample_efficiency_controls import (
    build_capacity_control_plan, cdf_metrics, publish_sample_efficiency_controls,
)
from src.research.sample_efficiency_training import (
    ARCHITECTURE_VARIANT, architecture_for, capacity_first_width,
    read_subset_discriminant_run,
)
from src.research.sample_efficiency_workflow import execute_learning_curve

from sample_efficiency_support import build_sample_efficiency_fixture


def _t1(base):
    return {
        "schema_version": "h4l-t1-validation-v1", "status": "validated",
        "dataset": base["dataset"], "protocol_sha256": base.digest,
        "evidence_id": "synthetic-t1", "independent_reference": "synthetic-reference",
        "correlation": "independent_process_bins", "auxiliary": "poisson_tau_gamma",
        "modifier": "shapesys", "pyhf_version": "0.7.6",
        "validation_summary": {"reviewed_by": "synthetic-reviewer",
            "reviewed_at": "2026-09-12T00:00:00Z", "numerical_tests": ["synthetic"]},
    }


def _gate(path, prepared, base, t1):
    with ResearchRun(
        path, allowed_root=path.parent, stage="templates", dataset=base["dataset"],
        protocol=base.to_dict(), upstreams=[prepared],
    ) as run:
        run.write_json("g1.json", {
            "status": "passed", "reasons": [],
            "allowed_roles": ["calibration", "template"], "assessment_used": False,
        })
        run.write_json("t1-validation.json", t1)
    return read_run(
        path, dataset=base["dataset"], protocol=base.to_dict(), stages=("templates",),
    )


def _threshold(model_id, mapping_id, value=0.5):
    payload = {"model_id": model_id, "mapping_id": mapping_id, "thresholds": [value],
               "source_role": "calibration_background", "ties": "higher-category-at-threshold",
               "distribution_fit": {}, "protocol_id": "test"}
    payload["threshold_id"] = digest(payload)
    return payload


def test_capacity_width_golden_and_parameter_architectures():
    assert [capacity_first_width(value) for value in (8, 13, 20)] == [74, 70, 64]
    assert architecture_for(8, "match_engineered19_parameter_count_v1") == [8, 74, 64, 32, 1]


def test_disabled_capacity_plan_is_named_and_empty_without_payload_decode(tmp_path, monkeypatch):
    base, prepared, freeze_run, overlay, subset_run = build_sample_efficiency_fixture(tmp_path)
    monkeypatch.setattr(
        "src.research.sample_efficiency_controls.read_training_subsets",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("decoded subset payload")),
    )
    plan = build_capacity_control_plan(prepared=prepared, freeze_run=freeze_run,
        subset_run=subset_run, base=base, overlay=overlay)
    assert plan["enabled"] is False
    assert plan["status"] == "disabled"
    assert plan["cells"] == []
    assert plan["planned_alias_count"] == plan["canonical_cell_count"] == 0


def test_enabled_capacity_full_endpoint_is_canonical_and_registered(tmp_path):
    base, prepared, freeze_run, overlay, subset_run = build_sample_efficiency_fixture(
        tmp_path, capacity_enabled=True)
    plan = build_capacity_control_plan(prepared=prepared, freeze_run=freeze_run,
        subset_run=subset_run, base=base, overlay=overlay)
    assert plan["canonical_cell_count"] == 3
    assert [cell["representation_id"] for cell in plan["cells"]] == overlay["representations"]
    assert {cell["sample_draw_seed_or_full"] for cell in plan["cells"]} == {"full"}
    assert {cell["network_seed"] for cell in plan["cells"]} == {42}
    assert [cell["resolved_first_width"] for cell in plan["cells"]] == [74, 70, 64]


def test_enabled_capacity_partial_uses_all_draws_and_full_is_deduplicated(tmp_path):
    base, prepared, freeze_run, overlay, subset_run = build_sample_efficiency_fixture(
        tmp_path, fractions=(0.5, 1.0), draws=(100, 101), capacity_enabled=True,
        capacity_fractions=(0.5, 1.0),
    )
    plan = build_capacity_control_plan(
        prepared=prepared, freeze_run=freeze_run, subset_run=subset_run,
        base=base, overlay=overlay,
    )
    coordinates = [
        (cell["sample_fraction_target"], cell["sample_draw_seed_or_full"],
         cell["representation_id"])
        for cell in plan["cells"]
    ]
    assert len(coordinates) == len(set(coordinates)) == 9
    assert {draw for fraction, draw, _ in coordinates if fraction == 0.5} == {100, 101}
    assert {draw for fraction, draw, _ in coordinates if fraction == 1.0} == {"full"}
    assert plan["planned_alias_count"] == 12
    assert plan["canonical_cell_count"] == 9


def test_both_disabled_controls_skip_public_payload_readers_and_reject_collision(
    tmp_path, monkeypatch,
):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    base, prepared, freeze_run, overlay, subset_run = build_sample_efficiency_fixture(inputs)
    t1 = _t1(base)
    gate_run = _gate(inputs / "gate", prepared, base, t1)
    runs = tmp_path / "runs"
    runs.mkdir()
    batch_root = runs / "batch-root"
    batch_root.mkdir()
    with ResearchRun(
        batch_root / "batch", allowed_root=batch_root, stage="sample-efficiency-batch",
        dataset=base["dataset"], protocol=base.to_dict(),
    ):
        pass
    batch_run = read_run(
        batch_root / "batch", dataset=base["dataset"], protocol=base.to_dict(),
        stages=("sample-efficiency-batch",),
    )
    with ResearchRun(
        runs / "report", allowed_root=runs, stage="sample-efficiency-report",
        dataset=base["dataset"], protocol=base.to_dict(), upstreams=[batch_run],
    ):
        pass
    sentinel = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("decoded payload"))
    monkeypatch.setattr("src.research.sample_efficiency_controls.read_learning_curve_batch", sentinel)
    monkeypatch.setattr("src.research.sample_efficiency_controls.read_sample_efficiency_report", sentinel)
    controls = publish_sample_efficiency_controls(
        runs / "controls", allowed_root=runs, prepared=prepared, freeze_run=freeze_run,
        subset_run=subset_run, gate_run=gate_run, t1_validation=t1,
        batch_path=batch_root, report_path=runs / "report", base=base, overlay=overlay,
    )
    assert controls.capacity["status"] == controls.cdf["status"] == "disabled"
    with pytest.raises(RunPathError):
        publish_sample_efficiency_controls(
            runs / "controls", allowed_root=runs, prepared=prepared,
            freeze_run=freeze_run, subset_run=subset_run, gate_run=gate_run,
            t1_validation=t1, batch_path=batch_root, report_path=runs / "report",
            base=base, overlay=overlay,
        )


def test_cdf_metrics_use_absolute_weight_and_absolute_mass_bin_deformation():
    calibration = pd.DataFrame({"label": [0, 0, 0, 0], "physical_weight": [1, -1, 1, -1]})
    template = pd.DataFrame({"label": [0, 0, 0, 0], "physical_weight": [1, -1, 1, -1],
                             "m4l": [0.2, 0.8, 1.2, 1.8]})
    raw = _threshold("model", "raw")
    mapped = _threshold("model", "mapped")
    metrics = cdf_metrics(calibration, template,
        raw_calibration_scores=[0.1, 0.2, 0.8, 0.9],
        mapped_calibration_scores=[0.1, 0.2, 0.8, 0.9],
        raw_template_scores=[0.1, 0.9, 0.1, 0.9],
        mapped_template_scores=[0.9, 0.9, 0.1, 0.1], raw_thresholds=raw,
        mapped_thresholds=mapped, model_id="model", raw_mapping_id="raw",
        mapped_mapping_id="mapped", mass_edges=[0.0, 1.0, 2.0])
    assert metrics["calibration_acceptance_max_absolute_error"] == 0.0
    assert metrics["template_mass_bin_max_absolute_acceptance_deformation"] == 0.5


def test_enabled_controls_publish_and_replay_capacity_stage_chain(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    base, prepared, freeze_run, overlay, subset_run = build_sample_efficiency_fixture(
        inputs, fractions=(0.5, 1.0), draws=(100,), capacity_enabled=True, cdf_enabled=True,
        minimum_groups=20, template_groups=320,
    )
    t1 = _t1(base)
    gate_run = _gate(inputs / "gate", prepared, base, t1)
    runs = tmp_path / "runs"
    runs.mkdir()
    batch = execute_learning_curve(
        prepared=prepared, freeze_run=freeze_run, subset_run=subset_run,
        gate_run=gate_run, t1_validation=t1, base=base, overlay=overlay,
        output_root=runs, output_name="batch", resources={"workers": 1},
    )
    report = publish_sample_efficiency_report(
        runs / "report", allowed_root=runs, batch_path=batch.path,
        prepared=prepared, freeze_run=freeze_run, subset_run=subset_run,
        gate_run=gate_run, t1_validation=t1, base=base, overlay=overlay,
    )
    controls = publish_sample_efficiency_controls(
        runs / "controls", allowed_root=runs, batch_path=batch.path,
        report_path=report.path, prepared=prepared, freeze_run=freeze_run,
        subset_run=subset_run, gate_run=gate_run, t1_validation=t1,
        base=base, overlay=overlay,
    )
    assert controls.capacity["status"] in {"complete", "scientific_terminal"}
    assert len(controls.capacity["cells"]) == 3
    for cell in controls.capacity["cells"]:
        assert set(cell["stage_artifact_ids"]) == {
            "model", "calibration", "template", "inference",
        }
        if cell["status"] == "complete":
            assert (cell["metric_sources"]["w68"]["json_pointer"]
                    == "/result/results/0/intervals/confidence=0.68/width")
        else:
            assert cell["terminal_stage"] == "template"
    assert controls.cdf["enabled"] is True
    assert len(controls.cdf["cells"]) == 15
    first = controls.capacity["cells"][0]
    with pytest.raises(ResearchError):
        read_subset_discriminant_run(
            controls.run.path.parent / first["relative_paths"]["model"],
            prepared=prepared, freeze_run=freeze_run, subset_run=subset_run,
            base=base, overlay=overlay, fraction=1.0, draw=100,
            representation_id=first["representation_id"], network_seed=42,
            architecture_variant=ARCHITECTURE_VARIANT,
        )
