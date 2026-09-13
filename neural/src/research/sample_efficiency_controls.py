"""Protocol-bound capacity and physical-CDF mechanism checks for M6."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .artifacts import LoadedRun, ResearchRun, digest_json, read_run
from src.artifacts.transaction import RunPathError
from .calibration import (apply_calibration, assign_categories, build_raw_calibration_bundle,
                          fit_calibration, fit_thresholds)
from .errors import ResearchError, ResearchStateError
from .discriminants import ResearchClassifier
from .inference import run_asimov
from .protocol import ResearchProtocol, canonical
from .sample_efficiency import read_sample_efficiency_report
from .sample_efficiency_protocol import SampleEfficiencyProtocol
from .sample_efficiency_training import (
    ARCHITECTURE_VARIANT, CAPACITY_ARCHITECTURE_VARIANT, architecture_for,
    _ids,
    load_bound_prepared_role, predict_subset_discriminant, publish_subset_discriminant,
    read_subset_discriminant_run,
)
from .sample_efficiency_workflow import read_learning_curve_batch
from .representations import representation_features
from .templates import build_sample_efficiency_template
from .training_subsets import read_training_subsets


CAPACITY_SCHEMA = "h4l-sample-efficiency-capacity-control-v1"
CDF_SCHEMA = "h4l-sample-efficiency-cdf-check-v1"
CONTROLS_STAGE = "sample-efficiency-controls"
CAPACITY_CALIBRATION_STAGE = "sample-efficiency-capacity-calibration"
CAPACITY_TEMPLATE_STAGE = "sample-efficiency-capacity-template"
CAPACITY_INFERENCE_STAGE = "sample-efficiency-capacity-inference"
CAPACITY_CALIBRATION_SCHEMA = "h4l-capacity-calibration-v1"
CAPACITY_TEMPLATE_SCHEMA = "h4l-capacity-template-v1"
CAPACITY_INFERENCE_SCHEMA = "h4l-capacity-inference-v1"
WIDTH_RULE = "nearest_positive_integer_ties_lower_5568_over_d_plus_67"
_CDF_TERMINALS = {
    "insufficient_statistics", "nonpositive_calibration_yield",
    "outside_calibration_support", "template_stat_model_unvalidated",
}


def _fail(message):
    raise ResearchError(message, status="training_subset_binding_mismatch")


def _verified(run, base, stages, name):
    path = run.path if isinstance(run, LoadedRun) else run
    try:
        return read_run(path, dataset=base["dataset"], protocol=base.to_dict(), stages=tuple(stages))
    except ResearchError as exc:
        raise ResearchError(f"invalid {name} run", status="training_subset_binding_mismatch") from exc


def _upstream(run):
    return {"artifact_id": run.manifest["artifact_id"], "stage": run.manifest["stage"],
            "path": str(run.path)}


def _publish_json_run(path, *, allowed_root, stage, base, upstreams, filename, payload):
    with ResearchRun(path, allowed_root=allowed_root, stage=stage, dataset=base["dataset"],
                     protocol=base.to_dict(), upstreams=upstreams) as run:
        run.write_json(filename, payload)
    return read_run(path, dataset=base["dataset"], protocol=base.to_dict(), stages=(stage,))


def _envelope(schema, cell_id, key, value, **extra):
    payload = {"schema_version": schema, "experiment_cell_id": cell_id, key: value, **extra}
    payload["record_id"] = digest_json(payload)
    return payload


def _subset_entries(prepared, freeze_run, subset_run, base, overlay):
    plan, _, ledger = read_training_subsets(
        subset_run, prepared=prepared, freeze_run=freeze_run, base=base, overlay=overlay,
    )
    entries = {item["subset_id"]: item for item in plan["subsets"]}
    aliases = sorted(ledger["cells"], key=lambda item: canonical([
        item["fraction"], "full" if item["fraction"] == 1.0 else item["sample_draw_seed"],
    ]))
    return plan, entries, aliases


def build_capacity_control_plan(*, prepared, freeze_run, subset_run, base, overlay):
    """Return the unique registered capacity coordinates without opening event payloads."""
    if not isinstance(base, ResearchProtocol) or not isinstance(overlay, SampleEfficiencyProtocol):
        _fail("validated protocols are required")
    control = overlay["capacity_control"]
    root = {
        "schema_version": CAPACITY_SCHEMA, "enabled": control["enabled"],
        "status": "planned" if control["enabled"] else "disabled",
        "capacity_control_id": None, "architecture_variant": CAPACITY_ARCHITECTURE_VARIANT,
        "width_rule": WIDTH_RULE, "planned_alias_count": 0, "canonical_cell_count": 0,
        "cells": [],
    }
    if not control["enabled"]:
        root["capacity_control_id"] = digest_json({k: v for k, v in root.items()
                                                    if k != "capacity_control_id"})
        return root
    plan, entries, aliases = _subset_entries(prepared, freeze_run, subset_run, base, overlay)
    selected_aliases = [item for item in aliases if item["fraction"] in control["sample_fractions"]]
    canonical_entries, seen = [], set()
    for alias in selected_aliases:
        entry = entries[alias["subset_id"]]
        if entry["subset_id"] not in seen:
            seen.add(entry["subset_id"])
            canonical_entries.append(entry)
    for entry in canonical_entries:
        draw = None if entry["draw_or_full"] == "full" else entry["draw_or_full"]
        for representation in overlay["representations"]:
            if representation == "decay7":
                dimension = 8
            elif representation == "engineered19":
                dimension = 20
            else:
                groups = freeze_run.read_json("freeze.json")["candidate"]["groups"]
                dimension = len(representation_features("engineered19", groups=groups))
            architecture = architecture_for(dimension, CAPACITY_ARCHITECTURE_VARIANT)
            for seed in control["network_seeds"]:
                ids = {"sample_efficiency_protocol_sha256": overlay.digest,
                       "training_subset_artifact_id": subset_run.manifest["artifact_id"],
                       "training_subset_id": entry["subset_id"],
                       "sample_fraction_target": entry["fraction"],
                       "sample_draw_seed_or_full": entry["draw_or_full"],
                       "network_seed": seed, "architecture_variant": CAPACITY_ARCHITECTURE_VARIANT,
                       "representation_id": representation}
                experiment_id, pairing_id = _ids(ids)
                prefix = f"capacity-cells/{experiment_id}"
                root["cells"].append({
                    "plan_index": len(root["cells"]), "representation_id": representation,
                    "sample_fraction_target": entry["fraction"], "sample_draw_seed": draw,
                    "sample_draw_seed_or_full": entry["draw_or_full"],
                    "training_subset_id": entry["subset_id"],
                    "membership_digest": entry["membership_digest"], "network_seed": seed,
                    "architecture_variant": CAPACITY_ARCHITECTURE_VARIANT,
                    "input_dimension": dimension, "resolved_first_width": architecture[1],
                    "architecture": architecture,
                    "trainable_parameter_count": sum(
                        parameter.numel() for parameter in ResearchClassifier(dimension, architecture[1]).parameters()),
                    "experiment_cell_id": experiment_id, "pairing_id": pairing_id,
                    "relative_paths": {stage: f"{prefix}/{stage}" for stage in
                                       ("model", "calibration", "template", "inference")},
                })
    root["planned_alias_count"] = (len(selected_aliases) * len(overlay["representations"])
                                    * len(control["network_seeds"]))
    root["canonical_cell_count"] = len(root["cells"])
    root["capacity_control_id"] = digest_json({k: v for k, v in root.items()
                                                if k != "capacity_control_id"})
    return root


def _w68(result):
    rows = result.get("results", []) if type(result) is dict else []
    if len(rows) != 1:
        _fail("capacity inference result is incomplete")
    values = [item["width"] for item in rows[0].get("intervals", [])
              if item.get("confidence") == 0.68]
    if len(values) != 1 or type(values[0]) not in (int, float) or not np.isfinite(values[0]):
        _fail("capacity W68 is not uniquely available")
    return float(values[0])


def _capacity_cell_common(cell, model, calibration, template, artifacts):
    return dict(
        cell,
        stage_artifact_ids=artifacts,
        model_artifact_id=model.run.manifest["artifact_id"],
        model_id=model.model["model_id"],
        trainable_parameter_count=model.model["trainable_parameter_count"],
        primary_engineered19_parameter_count=7937,
        validation_absolute_weight_auc=model.model["validation_absolute_weight_auc"],
        calibration_id=calibration["calibration_id"],
        template_id=template["template_id"],
    )


def cdf_metrics(calibration_frame, template_frame, *, raw_calibration_scores,
                mapped_calibration_scores, raw_template_scores, mapped_template_scores,
                raw_thresholds, mapped_thresholds, model_id, raw_mapping_id,
                mapped_mapping_id, mass_edges):
    """Compute the two frozen absolute-weight CDF mechanism metrics."""
    cal_bg = calibration_frame.label.to_numpy() == 0
    template_bg = template_frame.label.to_numpy() == 0
    cal_weights = np.abs(calibration_frame.physical_weight.to_numpy(float))[cal_bg]
    template_weights = np.abs(template_frame.physical_weight.to_numpy(float))[template_bg]
    if cal_weights.sum() <= 0:
        raise ResearchStateError("CDF calibration has zero absolute-weight denominator",
                                 status="insufficient_statistics")
    mapped_cal_category = assign_categories(
        mapped_thresholds, np.asarray(mapped_calibration_scores)[cal_bg],
        model_id=model_id, mapping_id=mapped_mapping_id,
    )
    acceptance = float(cal_weights[mapped_cal_category == 1].sum() / cal_weights.sum())
    raw_category = assign_categories(raw_thresholds, np.asarray(raw_template_scores)[template_bg],
                                     model_id=model_id, mapping_id=raw_mapping_id)
    mapped_category = assign_categories(mapped_thresholds, np.asarray(mapped_template_scores)[template_bg],
                                        model_id=model_id, mapping_id=mapped_mapping_id)
    masses = template_frame.m4l.to_numpy(float)[template_bg]
    edges = np.asarray(mass_edges, float)
    if edges.ndim != 1 or len(edges) < 2 or not np.isfinite(edges).all() or (np.diff(edges) <= 0).any():
        _fail("invalid frozen M4 mass grid")
    bins = np.searchsorted(edges, masses, side="right") - 1
    bins[masses == edges[-1]] = len(edges) - 2
    distortions = []
    for index in range(len(edges) - 1):
        mask = bins == index
        denominator = float(template_weights[mask].sum())
        if denominator > 0:
            raw_rate = float(template_weights[mask & (raw_category == 1)].sum() / denominator)
            mapped_rate = float(template_weights[mask & (mapped_category == 1)].sum() / denominator)
            distortions.append(abs(mapped_rate - raw_rate))
    if not distortions:
        raise ResearchStateError("CDF template has no effective mass bin",
                                 status="insufficient_statistics")
    return {
        "calibration_absolute_weight_acceptance": acceptance,
        "calibration_acceptance_target": 0.5,
        "calibration_acceptance_max_absolute_error": abs(acceptance - 0.5),
        "template_mass_bin_max_absolute_acceptance_deformation": max(distortions),
        "calibration_background_absolute_weight_denominator": float(cal_weights.sum()),
        "template_effective_mass_bin_count": len(distortions),
    }


def _load_baseline_cell(batch, cell, *, prepared, freeze_run, subset_run, base, overlay):
    draw = overlay["sample_draw_seeds"][0] if cell["sample_draw_seed"] is None else cell["sample_draw_seed"]
    return read_subset_discriminant_run(
        batch.path / cell["relative_paths"]["model"], prepared=prepared, freeze_run=freeze_run,
        subset_run=subset_run, base=base, overlay=overlay,
        fraction=cell["sample_fraction_target"], draw=draw,
        representation_id=cell["representation_id"], network_seed=cell["network_seed"],
        architecture_variant=ARCHITECTURE_VARIANT,
    )


def _load_grid(batch, base):
    run = _verified(batch.path / "common-grid", base,
                    ("sample-efficiency-common-grid",), "M4 common grid")
    return run, run.read_json("common-grid.json")


def _compute_cdf_check(batch, *, prepared, freeze_run, subset_run, base, overlay):
    cfg = overlay["cdf_check"]
    result = {"schema_version": CDF_SCHEMA, "enabled": cfg["enabled"],
              "status": "planned" if cfg["enabled"] else "disabled", "cdf_check_id": None,
              "grid_id": None, "final_mass_edges": None, "cells": []}
    if not cfg["enabled"]:
        result["cdf_check_id"] = digest_json({k: v for k, v in result.items()
                                              if k != "cdf_check_id"})
        return result
    _, grid = _load_grid(batch, base)
    result["grid_id"], result["final_mass_edges"] = grid["grid_id"], grid["final_mass_edges"]
    for cell, outcome in zip(batch.plan["cells"], batch.ledger["cells"]):
        if (cell["sample_fraction_target"] not in cfg["sample_fractions"]
                or cell["representation_id"] not in cfg["representations"]):
            continue
        record = {"experiment_cell_id": cell["experiment_cell_id"],
                  "pairing_id": cell["pairing_id"], "representation_id": cell["representation_id"],
                  "sample_fraction_target": cell["sample_fraction_target"],
                  "sample_draw_seed_or_full": cell["sample_draw_seed_or_full"],
                  "network_seed": cell["network_seed"], "status": None, "reason": None,
                  "mapping": None, "thresholds": None, "metrics": None}
        if outcome["cell_status"] != "complete":
            record.update(status="raw_cell_unavailable",
                          reason=f"raw cell terminal: {outcome['status']}")
            result["cells"].append(record)
            continue
        try:
            model = _load_baseline_cell(batch, cell, prepared=prepared, freeze_run=freeze_run,
                                        subset_run=subset_run, base=base, overlay=overlay)
            raw = build_raw_calibration_bundle(prepared, model, base)
            calibration_frame = load_bound_prepared_role(prepared, model, base, "calibration")
            template_frame = load_bound_prepared_role(prepared, model, base, "template")
            raw_calibration_scores = predict_subset_discriminant(model, calibration_frame)
            raw_template_scores = predict_subset_discriminant(model, template_frame)
            mapping = fit_calibration(calibration_frame, raw_calibration_scores, base,
                                      target="physical", model_id=model.model["model_id"])
            mapped_calibration_scores = apply_calibration(
                mapping, calibration_frame.m4l.to_numpy(float), raw_calibration_scores,
                model_id=model.model["model_id"])
            mapped_template_scores = apply_calibration(
                mapping, template_frame.m4l.to_numpy(float), raw_template_scores,
                model_id=model.model["model_id"])
            thresholds = fit_thresholds(calibration_frame, mapped_calibration_scores, base,
                model_id=model.model["model_id"], mapping_id=mapping["mapping_id"])
            metrics = cdf_metrics(calibration_frame, template_frame,
                raw_calibration_scores=raw_calibration_scores,
                mapped_calibration_scores=mapped_calibration_scores,
                raw_template_scores=raw_template_scores,
                mapped_template_scores=mapped_template_scores,
                raw_thresholds=raw["thresholds"], mapped_thresholds=thresholds,
                model_id=model.model["model_id"], raw_mapping_id=raw["mapping_id"],
                mapped_mapping_id=mapping["mapping_id"], mass_edges=grid["final_mass_edges"])
            record.update(status="complete", mapping=mapping, thresholds=thresholds, metrics=metrics)
        except ResearchStateError as exc:
            if exc.status not in _CDF_TERMINALS:
                raise
            record.update(status="calibration_uncertainty_dominant", reason=str(exc))
        result["cells"].append(record)
    result["status"] = ("complete" if all(item["status"] == "complete" for item in result["cells"])
                        else "calibration_uncertainty_dominant")
    result["cdf_check_id"] = digest_json({k: v for k, v in result.items() if k != "cdf_check_id"})
    return result


@dataclass(frozen=True)
class _ManifestBoundBatch:
    path: Path
    run: LoadedRun


@dataclass(frozen=True)
class _ManifestBoundReport:
    run: LoadedRun


def _build_controls(*, target, prepared, freeze_run, subset_run, gate_run, t1_validation,
                    batch_path, report_path, base, overlay):
    if not overlay["capacity_control"]["enabled"] and not overlay["cdf_check"]["enabled"]:
        prepared = _verified(prepared, base, ("prepare",), "prepared")
        freeze_run = _verified(freeze_run, base, ("compact-freeze",), "compact freeze")
        subset_run = _verified(subset_run, base, ("training-subsets",), "training subsets")
        gate_run = _verified(gate_run, base, ("templates",), "G1 gate")
        batch_run = _verified(Path(batch_path) / "batch", base,
                              ("sample-efficiency-batch",), "M4 batch")
        report = _verified(report_path, base, ("sample-efficiency-report",), "M5 report")
        if report.manifest.get("upstreams") != [_upstream(batch_run)]:
            _fail("disabled controls M5 report does not bind the supplied M4 batch")
        capacity = build_capacity_control_plan(prepared=prepared, freeze_run=freeze_run,
            subset_run=subset_run, base=base, overlay=overlay)
        cdf = _compute_cdf_check(None, prepared=prepared, freeze_run=freeze_run,
                                 subset_run=subset_run, base=base, overlay=overlay)
        return (_ManifestBoundBatch(Path(batch_path).resolve(), batch_run),
                _ManifestBoundReport(report), capacity, cdf, [])
    batch = read_learning_curve_batch(batch_path, prepared=prepared, freeze_run=freeze_run,
        subset_run=subset_run, gate_run=gate_run, t1_validation=t1_validation,
        base=base, overlay=overlay)
    report = read_sample_efficiency_report(report_path, batch_path=batch_path, prepared=prepared,
        freeze_run=freeze_run, subset_run=subset_run, gate_run=gate_run,
        t1_validation=t1_validation, base=base, overlay=overlay)
    capacity = build_capacity_control_plan(prepared=prepared, freeze_run=freeze_run,
        subset_run=subset_run, base=base, overlay=overlay)
    capacity_runs = []
    if capacity["enabled"]:
        results = []
        grid_run = _verified(batch.path / "common-grid", base,
                             ("sample-efficiency-common-grid",), "M4 common grid")
        grid = grid_run.read_json("common-grid.json")
        for cell in capacity["cells"]:
            draw = overlay["sample_draw_seeds"][0] if cell["sample_draw_seed"] is None else cell["sample_draw_seed"]
            model = publish_subset_discriminant(
                Path(target) / cell["relative_paths"]["model"], allowed_root=target,
                prepared=prepared, freeze_run=freeze_run, subset_run=subset_run, base=base,
                overlay=overlay, fraction=cell["sample_fraction_target"], draw=draw,
                representation_id=cell["representation_id"], network_seed=cell["network_seed"],
                architecture_variant=CAPACITY_ARCHITECTURE_VARIANT,
            )
            if (model.model["experiment_cell_id"] != cell["experiment_cell_id"]
                    or model.model["pairing_id"] != cell["pairing_id"]):
                _fail("capacity model differs from the sealed coordinate")
            calibration = build_raw_calibration_bundle(prepared, model, base)
            calibration_envelope = _envelope(
                CAPACITY_CALIBRATION_SCHEMA, cell["experiment_cell_id"], "calibration",
                calibration.to_dict(), grid_id=grid["grid_id"])
            calibration_run = _publish_json_run(
                Path(target) / cell["relative_paths"]["calibration"], allowed_root=target,
                stage=CAPACITY_CALIBRATION_STAGE, base=base,
                upstreams=[prepared, subset_run, model.run, grid_run],
                filename="calibration.json", payload=calibration_envelope)
            template = build_sample_efficiency_template(
                prepared, model, calibration, base, mass_edges=grid["final_mass_edges"],
            )
            template_envelope = _envelope(
                CAPACITY_TEMPLATE_SCHEMA, cell["experiment_cell_id"], "template", template,
                grid_id=grid["grid_id"])
            template_run = _publish_json_run(
                Path(target) / cell["relative_paths"]["template"], allowed_root=target,
                stage=CAPACITY_TEMPLATE_STAGE, base=base,
                upstreams=[prepared, calibration_run, grid_run],
                filename="template.json", payload=template_envelope)
            stage_artifacts = {
                "model": model.run.manifest["artifact_id"],
                "calibration": calibration_run.manifest["artifact_id"],
                "template": template_run.manifest["artifact_id"],
                "inference": None,
            }
            capacity_runs.extend([model.run, calibration_run, template_run])
            if template.get("status") != "valid":
                results.append(dict(
                    _capacity_cell_common(cell, model, calibration, template, stage_artifacts),
                    status="scientific_terminal",
                    reason="template is a registered terminal",
                    terminal_stage="template",
                    blocked_stages=["inference"],
                    inference_result_id=None,
                    w68=None,
                    metric_sources={},
                ))
                continue
            inference = run_asimov(template, protocol=base, layer="T1",
                t1_validation=t1_validation, injections=(1.0,), experiment_lineage=model.lineage)
            inference_envelope = _envelope(
                CAPACITY_INFERENCE_SCHEMA, cell["experiment_cell_id"], "result", inference,
                grid_id=grid["grid_id"],
                metric_pointers={"w68": "/result/results/0/intervals/confidence=0.68/width"})
            inference_run = _publish_json_run(
                Path(target) / cell["relative_paths"]["inference"], allowed_root=target,
                stage=CAPACITY_INFERENCE_STAGE, base=base,
                upstreams=[template_run, grid_run, gate_run],
                filename="inference.json", payload=inference_envelope)
            stage_artifacts["inference"] = inference_run.manifest["artifact_id"]
            results.append(dict(
                _capacity_cell_common(cell, model, calibration, template, stage_artifacts),
                status="complete", reason=None, terminal_stage=None, blocked_stages=[],
                inference_result_id=inference["result_id"], w68=_w68(inference),
                metric_sources={"w68": {"artifact_id": inference_run.manifest["artifact_id"],
                    "filename": "inference.json",
                    "json_pointer": "/result/results/0/intervals/confidence=0.68/width"}}))
            capacity_runs.append(inference_run)
        capacity["cells"] = results
        capacity["status"] = ("complete" if all(item["status"] == "complete" for item in results)
                              else "scientific_terminal")
        capacity["capacity_control_id"] = digest_json({k: v for k, v in capacity.items()
                                                        if k != "capacity_control_id"})
    cdf = _compute_cdf_check(batch, prepared=prepared, freeze_run=freeze_run,
                             subset_run=subset_run, base=base, overlay=overlay)
    return batch, report, capacity, cdf, capacity_runs


def _replay_capacity(target, batch, *, prepared, freeze_run, subset_run, gate_run,
                     t1_validation, base, overlay):
    capacity = build_capacity_control_plan(prepared=prepared, freeze_run=freeze_run,
        subset_run=subset_run, base=base, overlay=overlay)
    if not capacity["enabled"]:
        return capacity, []
    grid_run, grid = _load_grid(batch, base)
    results, stage_runs = [], []
    for cell in capacity["cells"]:
        draw = overlay["sample_draw_seeds"][0] if cell["sample_draw_seed"] is None else cell["sample_draw_seed"]
        model = read_subset_discriminant_run(
            Path(target) / cell["relative_paths"]["model"], prepared=prepared,
            freeze_run=freeze_run, subset_run=subset_run, base=base, overlay=overlay,
            fraction=cell["sample_fraction_target"], draw=draw,
            representation_id=cell["representation_id"], network_seed=cell["network_seed"],
            architecture_variant=CAPACITY_ARCHITECTURE_VARIANT)
        calibration = build_raw_calibration_bundle(prepared, model, base)
        calibration_run = _verified(Path(target) / cell["relative_paths"]["calibration"], base,
                                    (CAPACITY_CALIBRATION_STAGE,), "capacity calibration")
        expected_calibration = _envelope(
            CAPACITY_CALIBRATION_SCHEMA, cell["experiment_cell_id"], "calibration",
            calibration.to_dict(), grid_id=grid["grid_id"])
        if (calibration_run.manifest.get("upstreams")
                != [_upstream(item) for item in (prepared, subset_run, model.run, grid_run)]
                or canonical(calibration_run.read_json("calibration.json")) != canonical(expected_calibration)):
            _fail("capacity calibration replay mismatch")
        template = build_sample_efficiency_template(
            prepared, model, calibration, base, mass_edges=grid["final_mass_edges"])
        template_run = _verified(Path(target) / cell["relative_paths"]["template"], base,
                                 (CAPACITY_TEMPLATE_STAGE,), "capacity template")
        expected_template = _envelope(
            CAPACITY_TEMPLATE_SCHEMA, cell["experiment_cell_id"], "template", template,
            grid_id=grid["grid_id"])
        if (template_run.manifest.get("upstreams")
                != [_upstream(item) for item in (prepared, calibration_run, grid_run)]
                or canonical(template_run.read_json("template.json")) != canonical(expected_template)):
            _fail("capacity template replay mismatch")
        artifacts = {"model": model.run.manifest["artifact_id"],
            "calibration": calibration_run.manifest["artifact_id"],
            "template": template_run.manifest["artifact_id"], "inference": None}
        stage_runs.extend([model.run, calibration_run, template_run])
        if template.get("status") != "valid":
            results.append(dict(
                _capacity_cell_common(cell, model, calibration, template, artifacts),
                status="scientific_terminal", reason="template is a registered terminal",
                terminal_stage="template", blocked_stages=["inference"],
                inference_result_id=None, w68=None, metric_sources={},
            ))
            continue
        inference = run_asimov(template, protocol=base, layer="T1",
            t1_validation=t1_validation, injections=(1.0,), experiment_lineage=model.lineage)
        inference_run = _verified(Path(target) / cell["relative_paths"]["inference"], base,
                                  (CAPACITY_INFERENCE_STAGE,), "capacity inference")
        metric_sources = {"w68": {"artifact_id": inference_run.manifest["artifact_id"],
            "filename": "inference.json",
            "json_pointer": "/result/results/0/intervals/confidence=0.68/width"}}
        expected_inference = _envelope(
            CAPACITY_INFERENCE_SCHEMA, cell["experiment_cell_id"], "result", inference,
            grid_id=grid["grid_id"],
            metric_pointers={"w68": metric_sources["w68"]["json_pointer"]})
        if (inference_run.manifest.get("upstreams")
                != [_upstream(item) for item in (template_run, grid_run, gate_run)]
                or canonical(inference_run.read_json("inference.json")) != canonical(expected_inference)):
            _fail("capacity inference replay mismatch")
        artifacts["inference"] = inference_run.manifest["artifact_id"]
        results.append(dict(
            _capacity_cell_common(cell, model, calibration, template, artifacts),
            status="complete", reason=None, terminal_stage=None, blocked_stages=[],
            inference_result_id=inference["result_id"], w68=_w68(inference),
            metric_sources=metric_sources))
        stage_runs.append(inference_run)
    capacity["cells"] = results
    capacity["status"] = ("complete" if all(item["status"] == "complete" for item in results)
                          else "scientific_terminal")
    capacity["capacity_control_id"] = digest_json({k: v for k, v in capacity.items()
                                                   if k != "capacity_control_id"})
    return capacity, stage_runs


@dataclass(frozen=True)
class LoadedSampleEfficiencyControls:
    run: LoadedRun
    capacity: dict
    cdf: dict


def publish_sample_efficiency_controls(output_dir, *, allowed_root, prepared, freeze_run,
                                       subset_run, gate_run, t1_validation, batch_path,
                                       report_path, base, overlay):
    root = Path(allowed_root).resolve(strict=True)
    target = Path(output_dir)
    if target.parent.resolve(strict=True) != root or target.exists():
        raise RunPathError("controls target must be a fresh direct child")
    target.mkdir()
    try:
        batch, report, capacity, cdf, capacity_runs = _build_controls(target=target,
            prepared=prepared, freeze_run=freeze_run, subset_run=subset_run, gate_run=gate_run,
            t1_validation=t1_validation, batch_path=batch_path, report_path=report_path,
            base=base, overlay=overlay)
        with ResearchRun(target / "artifact", allowed_root=target, stage=CONTROLS_STAGE,
                         dataset=base["dataset"], protocol=base.to_dict(),
                         upstreams=[prepared, freeze_run, subset_run, gate_run, batch.run, report.run]
                                   + capacity_runs,
                         context={"capacity_control_id": capacity["capacity_control_id"],
                                  "cdf_check_id": cdf["cdf_check_id"]}) as run:
            run.write_json("sample-efficiency-protocol.json", overlay.to_dict())
            run.write_json("capacity-control.json", capacity)
            run.write_json("cdf-check.json", cdf)
    except BaseException:
        # ResearchRun owns published stage directories; only remove the empty container created above.
        if target.exists() and not any(target.iterdir()):
            target.rmdir()
        raise
    return read_sample_efficiency_controls(target / "artifact", batch_path=batch_path,
        report_path=report_path, prepared=prepared, freeze_run=freeze_run, subset_run=subset_run,
        gate_run=gate_run, t1_validation=t1_validation, base=base, overlay=overlay)


def read_sample_efficiency_controls(path, *, batch_path, report_path, prepared, freeze_run,
                                    subset_run, gate_run, t1_validation, base, overlay):
    prepared = _verified(prepared, base, ("prepare",), "prepared")
    freeze_run = _verified(freeze_run, base, ("compact-freeze",), "compact freeze")
    subset_run = _verified(subset_run, base, ("training-subsets",), "training subsets")
    gate_run = _verified(gate_run, base, ("templates",), "G1 gate")
    disabled = not overlay["capacity_control"]["enabled"] and not overlay["cdf_check"]["enabled"]
    if disabled:
        batch_run = _verified(Path(batch_path) / "batch", base,
                              ("sample-efficiency-batch",), "M4 batch")
        report_run = _verified(report_path, base, ("sample-efficiency-report",), "M5 report")
        if report_run.manifest.get("upstreams") != [_upstream(batch_run)]:
            _fail("disabled controls M5 report does not bind M4")
        batch = _ManifestBoundBatch(Path(batch_path).resolve(), batch_run)
        report = _ManifestBoundReport(report_run)
    else:
        batch = read_learning_curve_batch(batch_path, prepared=prepared, freeze_run=freeze_run,
            subset_run=subset_run, gate_run=gate_run, t1_validation=t1_validation,
            base=base, overlay=overlay)
        report = read_sample_efficiency_report(report_path, batch_path=batch_path, prepared=prepared,
            freeze_run=freeze_run, subset_run=subset_run, gate_run=gate_run,
            t1_validation=t1_validation, base=base, overlay=overlay)
    run = read_run(path, dataset=base["dataset"], protocol=base.to_dict(), stages=(CONTROLS_STAGE,))
    if set(run.manifest["files"]) != {"protocol.json", "sample-efficiency-protocol.json",
                                      "capacity-control.json", "cdf-check.json"}:
        _fail("controls artifact file surface mismatch")
    if run.read_json("sample-efficiency-protocol.json") != overlay.to_dict():
        _fail("controls overlay binding mismatch")
    capacity, cdf = run.read_json("capacity-control.json"), run.read_json("cdf-check.json")
    for value, schema, id_key in ((capacity, CAPACITY_SCHEMA, "capacity_control_id"),
                                  (cdf, CDF_SCHEMA, "cdf_check_id")):
        if (type(value) is not dict or value.get("schema_version") != schema
                or value.get(id_key) != digest_json({k: v for k, v in value.items() if k != id_key})):
            _fail("controls payload digest mismatch")
    expected_capacity, stage_runs = _replay_capacity(Path(path).resolve().parent, batch,
        prepared=prepared, freeze_run=freeze_run, subset_run=subset_run, gate_run=gate_run,
        t1_validation=t1_validation, base=base, overlay=overlay)
    expected_cdf = _compute_cdf_check(batch, prepared=prepared, freeze_run=freeze_run,
                                      subset_run=subset_run, base=base, overlay=overlay)
    expected_upstreams = [_upstream(item) for item in
                          (prepared, freeze_run, subset_run, gate_run, batch.run, report.run)]
    expected_upstreams += [_upstream(item) for item in stage_runs]
    if run.manifest.get("upstreams") != expected_upstreams:
        _fail("controls direct-upstream binding mismatch")
    if canonical(capacity) != canonical(expected_capacity) or canonical(cdf) != canonical(expected_cdf):
        _fail("controls semantic replay mismatch")
    if not capacity["enabled"] and (capacity["status"] != "disabled" or capacity["cells"]
                                    or capacity["canonical_cell_count"] != 0):
        _fail("disabled capacity control decoded payloads")
    if not cdf["enabled"] and (cdf["status"] != "disabled" or cdf["cells"]):
        _fail("disabled CDF check decoded payloads")
    return LoadedSampleEfficiencyControls(run, capacity, cdf)
