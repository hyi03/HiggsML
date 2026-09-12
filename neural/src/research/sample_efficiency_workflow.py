"""Receipt-bound orchestration for the sample-efficiency learning-curve batch."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .artifacts import LoadedRun, ResearchRun, digest_json, read_run
from .calibration import build_raw_calibration_bundle
from .errors import ResearchError, ResearchStateError
from .inference import run_asimov
from .protocol import ResearchProtocol, canonical
from .sample_efficiency_protocol import SampleEfficiencyProtocol
from .sample_efficiency_training import _ids, publish_subset_discriminant, read_subset_discriminant_run
from .templates import (build_sample_efficiency_template, common_mass_grid,
                        prepare_sample_efficiency_template_frame, require_template_lineage)
from .training_subsets import read_training_subsets


PLAN_SCHEMA = "h4l-sample-efficiency-batch-plan-v1"
CALIBRATION_SCHEMA = "h4l-sample-efficiency-calibration-v1"
GRID_SCHEMA = "h4l-sample-efficiency-common-grid-v1"
TEMPLATE_SCHEMA = "h4l-sample-efficiency-template-v1"
INFERENCE_SCHEMA = "h4l-sample-efficiency-inference-v1"
LEDGER_SCHEMA = "h4l-sample-efficiency-batch-ledger-v1"
SUMMARY_SCHEMA = "h4l-sample-efficiency-batch-summary-v1"
PLAN_STAGE = "sample-efficiency-plan"
CALIBRATION_STAGE = "sample-efficiency-calibration"
GRID_STAGE = "sample-efficiency-common-grid"
TEMPLATE_STAGE = "sample-efficiency-template"
INFERENCE_STAGE = "sample-efficiency-inference"
BATCH_STAGE = "sample-efficiency-batch"
ARCHITECTURE_VARIANT = "baseline-fixed64x64x32"
T1_CONTRACT = {"status": "validated", "correlation": "independent_process_bins",
               "auxiliary": "poisson_tau_gamma", "modifier": "shapesys",
               "pyhf_version": "0.7.6"}
RESOURCE_KEYS = {"workers"}
G1_KEYS = {"status", "reasons", "allowed_roles", "assessment_used"}
_T1_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "config" / "validation" / "t1_validation_v1.schema.json"


def _fail(message):
    raise ResearchError(message, status="training_subset_binding_mismatch")


def _keys(value, expected, name):
    if type(value) is not dict or set(value) != set(expected):
        _fail(f"invalid {name} schema")


def _verified(run, base, stages, name):
    if not isinstance(base, ResearchProtocol):
        _fail("validated base protocol is required")
    path = run.path if isinstance(run, LoadedRun) else run
    try:
        return read_run(path, dataset=base["dataset"], protocol=base.to_dict(), stages=tuple(stages))
    except ResearchError as exc:
        raise ResearchError(f"invalid {name} run", status="training_subset_binding_mismatch") from exc


def _upstream(run):
    return {"artifact_id": run.manifest["artifact_id"], "stage": run.manifest["stage"],
            "path": str(run.path)}


def _require_upstreams(run, expected):
    if run.manifest.get("upstreams") != [_upstream(item) for item in expected]:
        _fail(f"{run.manifest.get('stage')} upstream binding mismatch")


def _validate_t1_gate(gate_run, prepared, evidence, base):
    gate = _verified(gate_run, base, ("templates",), "G1 gate")
    prepared = _verified(prepared, base, ("prepare",), "prepared")
    matches = [item for item in gate.manifest.get("upstreams", [])
               if item == _upstream(prepared)]
    if len(matches) != 1:
        _fail("G1 gate does not bind the prepared run exactly once")
    try:
        g1 = gate.read_json("g1.json")
        snapshot = gate.read_json("t1-validation.json")
    except ResearchError as exc:
        raise ResearchError("invalid G1/T1 evidence receipt",
                            status="training_subset_binding_mismatch") from exc
    _keys(g1, G1_KEYS, "G1 evidence")
    if (g1.get("status") != "passed" or g1.get("reasons") != []
            or g1.get("allowed_roles") != ["calibration", "template"]
            or g1.get("assessment_used") is not False):
        _fail("G1 prerequisite evidence is not eligible")
    if type(evidence) is not dict or canonical(snapshot) != canonical(evidence):
        _fail("external T1 evidence differs from the gate snapshot")
    try:
        schema = json.loads(_T1_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(evidence)
    except Exception as exc:
        raise ResearchError("invalid T1 evidence schema",
                            status="training_subset_binding_mismatch") from exc
    if (evidence.get("dataset") != base["dataset"]
            or evidence.get("protocol_sha256") != base.digest
            or not evidence.get("independent_reference")
            or any(evidence.get(key) != value for key, value in T1_CONTRACT.items())):
        _fail("T1 evidence contract mismatch")
    return gate, snapshot


def _validate_resources(resources):
    if (type(resources) is not dict or set(resources) != RESOURCE_KEYS
            or any(type(value) is not int or value < 1 for value in resources.values())):
        _fail("invalid batch resource settings")
    if resources["workers"] != 1:
        _fail("M4 reference execution requires workers=1")
    return dict(resources)


def _cell_ids(overlay, subset_run, entry, representation, network_seed):
    return _ids({"sample_efficiency_protocol_sha256": overlay.digest,
                 "training_subset_artifact_id": subset_run.manifest["artifact_id"],
                 "training_subset_id": entry["subset_id"],
                 "sample_fraction_target": entry["fraction"],
                 "sample_draw_seed_or_full": entry["draw_or_full"],
                 "network_seed": network_seed, "architecture_variant": ARCHITECTURE_VARIANT,
                 "representation_id": representation})


def _safe_name(value, name):
    if (type(value) is not str or not value or value in {".", ".."}
            or any(character in value for character in "/\\:")):
        _fail(f"invalid {name}")
    return value


def _validate_plan(plan):
    root = {"schema_version", "scientific_batch_id", "execution_plan_id", "dataset",
            "base_research_protocol_sha256", "sample_efficiency_protocol_sha256",
            "prepared_artifact_id", "population_id", "compact_freeze_artifact_id",
            "training_subsets_artifact_id", "training_subset_plan_id", "gate_artifact_id",
            "t1_evidence_sha256", "common_grid_contract", "inference_contract",
            "planned_alias_count", "canonical_cell_count", "cells", "execution"}
    _keys(plan, root, "batch plan")
    if plan.get("schema_version") != PLAN_SCHEMA or type(plan.get("cells")) is not list:
        _fail("invalid batch plan version")
    science = {key: value for key, value in plan.items()
               if key not in {"scientific_batch_id", "execution_plan_id", "execution"}}
    if plan["scientific_batch_id"] != digest_json(science):
        _fail("scientific batch identity mismatch")
    execution = {key: value for key, value in plan.items() if key != "execution_plan_id"}
    if plan["execution_plan_id"] != digest_json(execution):
        _fail("execution plan identity mismatch")
    cell_keys = {"plan_index", "representation_id", "sample_fraction_target",
                 "sample_draw_seed", "sample_draw_seed_or_full", "training_subset_id",
                 "membership_digest", "network_seed", "architecture_variant",
                 "experiment_cell_id", "pairing_id", "relative_paths"}
    for index, cell in enumerate(plan["cells"]):
        _keys(cell, cell_keys, "batch plan cell")
        if cell["plan_index"] != index or cell["architecture_variant"] != ARCHITECTURE_VARIANT:
            _fail("batch plan cell order mismatch")
        _keys(cell["relative_paths"], {"model", "calibration", "template", "inference"},
              "batch cell paths")
    if (plan["canonical_cell_count"] != len(plan["cells"])
            or len({cell["experiment_cell_id"] for cell in plan["cells"]}) != len(plan["cells"])):
        _fail("batch plan cell count or identity mismatch")
    return plan


def build_learning_curve_plan(*, prepared, freeze_run, subset_run, gate_run, t1_validation,
                              base, overlay, output_root, output_name, resources, progress=False):
    """Build the final M2-bound plan without writing or decoding prepared events."""
    if not isinstance(base, ResearchProtocol) or not isinstance(overlay, SampleEfficiencyProtocol):
        _fail("validated base and sample-efficiency protocols are required")
    prepared = _verified(prepared, base, ("prepare",), "prepared")
    freeze_run = _verified(freeze_run, base, ("compact-freeze",), "compact freeze")
    subset_run = _verified(subset_run, base, ("training-subsets",), "training subsets")
    gate_run, evidence = _validate_t1_gate(gate_run, prepared, t1_validation, base)
    resources = _validate_resources(resources)
    output_name = _safe_name(output_name, "batch output name")
    plan_m2, _, ledger_m2 = read_training_subsets(subset_run, prepared=prepared,
        freeze_run=freeze_run, base=base, overlay=overlay)
    if (plan_m2["prepared_artifact_id"] != prepared.manifest["artifact_id"]
            or plan_m2["compact_candidate_freeze_artifact_id"] != freeze_run.manifest["artifact_id"]):
        _fail("M2 plan does not bind M4 inputs")
    entries = {item["subset_id"]: item for item in plan_m2["subsets"]}
    aliases = sorted(ledger_m2["cells"], key=lambda item: canonical(
        [item["fraction"], "full" if item["fraction"] == 1.0 else item["sample_draw_seed"]]))
    canonical_subsets = []
    seen = set()
    for alias in aliases:
        if alias["subset_id"] not in seen:
            seen.add(alias["subset_id"])
            canonical_subsets.append(entries[alias["subset_id"]])
    cells = []
    for entry in canonical_subsets:
        draw = None if entry["draw_or_full"] == "full" else entry["draw_or_full"]
        for network_seed in overlay["network_seeds"]:
            for representation in overlay["representations"]:
                experiment, pairing = _cell_ids(overlay, subset_run, entry, representation, network_seed)
                prefix = f"cells/{experiment}"
                cells.append({"plan_index": len(cells), "representation_id": representation,
                    "sample_fraction_target": entry["fraction"], "sample_draw_seed": draw,
                    "sample_draw_seed_or_full": entry["draw_or_full"],
                    "training_subset_id": entry["subset_id"],
                    "membership_digest": entry["membership_digest"], "network_seed": network_seed,
                    "architecture_variant": ARCHITECTURE_VARIANT,
                    "experiment_cell_id": experiment, "pairing_id": pairing,
                    "relative_paths": {stage: f"{prefix}/{stage}" for stage in
                                       ("model", "calibration", "template", "inference")}})
    root = Path(output_root).resolve()
    plan = {"schema_version": PLAN_SCHEMA, "scientific_batch_id": None,
        "execution_plan_id": None, "dataset": base["dataset"],
        "base_research_protocol_sha256": base.digest,
        "sample_efficiency_protocol_sha256": overlay.digest,
        "prepared_artifact_id": prepared.manifest["artifact_id"],
        "population_id": plan_m2["population_id"],
        "compact_freeze_artifact_id": freeze_run.manifest["artifact_id"],
        "training_subsets_artifact_id": subset_run.manifest["artifact_id"],
        "training_subset_plan_id": digest_json(plan_m2),
        "gate_artifact_id": gate_run.manifest["artifact_id"],
        "t1_evidence_sha256": digest_json(evidence),
        "common_grid_contract": {"algorithm": "leftmost-failing-mass-bin-shared-v1",
                                 "initial_mass_edges": base["templates"]["mass_edges"]},
        "inference_contract": {"layer": "T1", "expectation_kind": "model_self_asimov",
                               "injections": [1.0], "confidence_levels": base["inference"]["confidence_levels"],
                               "mu_bounds": base["inference"]["mu_bounds"]},
        "planned_alias_count": len(ledger_m2["cells"]) * len(overlay["representations"]) * len(overlay["network_seeds"]),
        "canonical_cell_count": len(cells), "cells": cells,
        "execution": {"output_root": str(root), "output_name": output_name,
                      "resources": resources}}
    science = {key: value for key, value in plan.items()
               if key not in {"scientific_batch_id", "execution_plan_id", "execution"}}
    plan["scientific_batch_id"] = digest_json(science)
    plan["execution_plan_id"] = digest_json({key: value for key, value in plan.items()
                                              if key != "execution_plan_id"})
    return _validate_plan(plan)


def _publish_json_run(path, *, allowed_root, stage, base, upstreams, filename, payload, context=None):
    with ResearchRun(path, allowed_root=allowed_root, stage=stage, dataset=base["dataset"],
                     protocol=base.to_dict(), upstreams=upstreams, context=context) as run:
        run.write_json(filename, payload)
    return read_run(path, dataset=base["dataset"], protocol=base.to_dict(), stages=(stage,))


def _envelope(schema, cell, key, value, **extra):
    payload = {"schema_version": schema, "scientific_batch_id": extra.pop("scientific_batch_id"),
               "execution_plan_id": extra.pop("execution_plan_id"),
               "experiment_cell_id": cell["experiment_cell_id"], key: value, **extra}
    payload["record_id"] = digest_json(payload)
    return payload


def _terminal(cell, stage, status, reason, artifacts, *, grid_id=None):
    order = ["model", "calibration", "template", "inference"]
    blocked = order[order.index(stage) + 1:]
    return {"plan_index": cell["plan_index"], "experiment_cell_id": cell["experiment_cell_id"],
            "stage_artifact_ids": dict(artifacts), "grid_id": grid_id,
            "cell_status": "scientific_terminal", "terminal_stage": stage,
            "blocked_stages": blocked, "status": status, "reason": str(reason), "exit_code": 0,
            "metric_sources": {"w68": None, "auc": None}}


@dataclass(frozen=True)
class LoadedLearningCurveBatch:
    path: Path
    run: LoadedRun
    plan: dict
    ledger: dict
    summary: dict


def execute_learning_curve(**kwargs):
    plan = build_learning_curve_plan(**kwargs)
    base, overlay = kwargs["base"], kwargs["overlay"]
    prepared = _verified(kwargs["prepared"], base, ("prepare",), "prepared")
    freeze_run = _verified(kwargs["freeze_run"], base, ("compact-freeze",), "compact freeze")
    subset_run = _verified(kwargs["subset_run"], base, ("training-subsets",), "training subsets")
    gate_run = _verified(kwargs["gate_run"], base, ("templates",), "G1 gate")
    evidence = kwargs["t1_validation"]
    output_root = Path(kwargs["output_root"]).resolve()
    target = (output_root / plan["execution"]["output_name"]).resolve()
    if target.parent != output_root or target.exists() or not output_root.is_dir():
        _fail("batch target must be a fresh child of the allowed output root")
    target.mkdir()
    marker = target / ".sample-efficiency-owner.json"
    marker.write_bytes(canonical({"schema_version": "h4l-sample-efficiency-owner-v1",
                                  "execution_plan_id": plan["execution_plan_id"],
                                  "target": str(target)}))
    try:
        plan_run = _publish_json_run(target / "plan", allowed_root=target, stage=PLAN_STAGE,
            base=base, upstreams=[prepared, freeze_run, subset_run, gate_run],
            filename="batch-plan.json", payload=plan,
            context={"scientific_batch_id": plan["scientific_batch_id"],
                     "execution_plan_id": plan["execution_plan_id"]})
        marker.unlink()
        plan_m2, _, ledger_m2 = read_training_subsets(subset_run, prepared=prepared,
            freeze_run=freeze_run, base=base, overlay=overlay)
        subset_status = {item["subset_id"]: item["status"] for item in plan_m2["subsets"]}
        outcomes, models, calibrations, calibration_runs = [], {}, {}, {}
        stage_runs = []
        for cell in plan["cells"]:
            artifacts = {name: None for name in ("model", "calibration", "template", "inference")}
            if subset_status[cell["training_subset_id"]] != "planned":
                outcomes.append(_terminal(cell, "model", subset_status[cell["training_subset_id"]],
                                          "M2 subset is a registered terminal", artifacts))
                continue
            draw = (overlay["sample_draw_seeds"][0] if cell["sample_draw_seed"] is None
                    else cell["sample_draw_seed"])
            try:
                loaded = publish_subset_discriminant(target / cell["relative_paths"]["model"],
                    allowed_root=target, prepared=prepared, freeze_run=freeze_run,
                    subset_run=subset_run, base=base, overlay=overlay,
                    fraction=cell["sample_fraction_target"], draw=draw,
                    representation_id=cell["representation_id"], network_seed=cell["network_seed"])
                if loaded.model["experiment_cell_id"] != cell["experiment_cell_id"]:
                    _fail("published model differs from sealed cell identity")
                artifacts["model"] = loaded.run.manifest["artifact_id"]
                models[cell["experiment_cell_id"]] = loaded
                stage_runs.append(loaded.run)
                bundle = build_raw_calibration_bundle(prepared, loaded, base)
                envelope = _envelope(CALIBRATION_SCHEMA, cell, "calibration", bundle.to_dict(),
                    scientific_batch_id=plan["scientific_batch_id"],
                    execution_plan_id=plan["execution_plan_id"])
                cal_run = _publish_json_run(target / cell["relative_paths"]["calibration"],
                    allowed_root=target, stage=CALIBRATION_STAGE, base=base,
                    upstreams=[plan_run, prepared, loaded.run], filename="calibration.json",
                    payload=envelope, context={"experiment_cell_id": cell["experiment_cell_id"]})
                artifacts["calibration"] = cal_run.manifest["artifact_id"]
                calibrations[cell["experiment_cell_id"]] = bundle
                calibration_runs[cell["experiment_cell_id"]] = cal_run
                stage_runs.append(cal_run)
                outcomes.append({"cell": cell, "artifacts": artifacts})
            except ResearchStateError as exc:
                outcomes.append(_terminal(cell, "model" if artifacts["model"] is None else "calibration",
                    exc.status, exc, artifacts))

        active = [item for item in outcomes if "cell" in item]
        participants = [{"experiment_cell_id": item["cell"]["experiment_cell_id"],
                         "calibration_artifact_id": calibration_runs[item["cell"]["experiment_cell_id"]].manifest["artifact_id"]}
                        for item in active]
        excluded = [{"experiment_cell_id": item["experiment_cell_id"], "status": item["status"]}
                    for item in outcomes if "cell" not in item]
        grid_upstreams = [plan_run, subset_run] + [calibration_runs[item["cell"]["experiment_cell_id"]]
                                                     for item in active]
        with ResearchRun(target / "common-grid", allowed_root=target, stage=GRID_STAGE,
                         dataset=base["dataset"], protocol=base.to_dict(),
                         upstreams=grid_upstreams,
                         context={"scientific_batch_id": plan["scientific_batch_id"]}) as grid_writer:
            frames = {item["cell"]["experiment_cell_id"]: prepare_sample_efficiency_template_frame(
                        prepared, models[item["cell"]["experiment_cell_id"]],
                        calibrations[item["cell"]["experiment_cell_id"]], base) for item in active}
            try:
                grid = (common_mass_grid(frames, mass_edges=base["templates"]["mass_edges"],
                                         thresholds=base["templates"])
                        if frames else {"status": "insufficient_statistics", "mass_edges": base["templates"]["mass_edges"],
                                        "merge_history": [], "templates": {}})
                grid_reason = None if grid["status"] == "valid" else "common grid has insufficient support"
            except ResearchStateError as exc:
                grid = {"status": exc.status, "mass_edges": base["templates"]["mass_edges"],
                        "merge_history": [], "templates": {}}
                grid_reason = str(exc)
            grid_payload = {"schema_version": GRID_SCHEMA,
                "scientific_batch_id": plan["scientific_batch_id"],
                "execution_plan_id": plan["execution_plan_id"], "participants": participants,
                "excluded": excluded, "initial_mass_edges": base["templates"]["mass_edges"],
                "merge_history": grid["merge_history"], "final_mass_edges": grid["mass_edges"],
                "status": grid["status"], "reason": grid_reason}
            grid_payload["grid_id"] = digest_json(grid_payload)
            grid_writer.manifest["context"]["grid_id"] = grid_payload["grid_id"]
            grid_writer.write_json("common-grid.json", grid_payload)
        grid_run = read_run(target / "common-grid", dataset=base["dataset"],
                            protocol=base.to_dict(), stages=(GRID_STAGE,))

        final_cells = [item for item in outcomes if "cell" not in item]
        for item in active:
            cell, artifacts = item["cell"], item["artifacts"]
            if grid["status"] != "valid":
                final_cells.append(_terminal(cell, "template", grid["status"], grid_reason,
                                              artifacts, grid_id=grid_payload["grid_id"]))
                continue
            loaded, bundle = models[cell["experiment_cell_id"]], calibrations[cell["experiment_cell_id"]]
            try:
                template = build_sample_efficiency_template(prepared, loaded, bundle, base,
                    mass_edges=grid["mass_edges"])
                template_envelope = _envelope(TEMPLATE_SCHEMA, cell, "template", template,
                    scientific_batch_id=plan["scientific_batch_id"],
                    execution_plan_id=plan["execution_plan_id"], grid_id=grid_payload["grid_id"])
                template_run = _publish_json_run(target / cell["relative_paths"]["template"],
                    allowed_root=target, stage=TEMPLATE_STAGE, base=base,
                    upstreams=[plan_run, prepared, calibration_runs[cell["experiment_cell_id"]], grid_run],
                    filename="template.json", payload=template_envelope,
                    context={"experiment_cell_id": cell["experiment_cell_id"],
                             "grid_id": grid_payload["grid_id"]})
                artifacts["template"] = template_run.manifest["artifact_id"]
                stage_runs.append(template_run)
                if template.get("status") != "valid":
                    final_cells.append(_terminal(cell, "template", template["status"],
                        "template is a registered terminal", artifacts, grid_id=grid_payload["grid_id"]))
                    continue
                result = run_asimov(template, protocol=base, layer="T1", t1_validation=evidence,
                                    injections=(1.0,), experiment_lineage=loaded.lineage)
                inference_envelope = _envelope(INFERENCE_SCHEMA, cell, "result", result,
                    scientific_batch_id=plan["scientific_batch_id"],
                    execution_plan_id=plan["execution_plan_id"], grid_id=grid_payload["grid_id"],
                    t1_evidence_sha256=plan["t1_evidence_sha256"],
                    metric_pointers={"w68": "/result/results/0/intervals/confidence=0.68/width",
                                     "auc": "/model/validation_absolute_weight_auc"})
                inference_run = _publish_json_run(target / cell["relative_paths"]["inference"],
                    allowed_root=target, stage=INFERENCE_STAGE, base=base,
                    upstreams=[plan_run, template_run, grid_run], filename="inference.json",
                    payload=inference_envelope, context={"experiment_cell_id": cell["experiment_cell_id"],
                                                         "grid_id": grid_payload["grid_id"]})
                artifacts["inference"] = inference_run.manifest["artifact_id"]
                stage_runs.append(inference_run)
                if result["status"] != "valid":
                    final_cells.append(_terminal(cell, "inference", result["status"],
                        "model-self inference is a registered terminal", artifacts,
                        grid_id=grid_payload["grid_id"]))
                    continue
                final_cells.append({"plan_index": cell["plan_index"],
                    "experiment_cell_id": cell["experiment_cell_id"],
                    "stage_artifact_ids": dict(artifacts), "grid_id": grid_payload["grid_id"],
                    "cell_status": "complete", "terminal_stage": None, "blocked_stages": [],
                    "status": "complete", "reason": None, "exit_code": 0,
                    "metric_sources": {
                        "w68": {"artifact_id": inference_run.manifest["artifact_id"],
                                "filename": "inference.json",
                                "json_pointer": "/result/results/0/intervals/confidence=0.68/width"},
                        "auc": {"artifact_id": loaded.run.manifest["artifact_id"],
                                "filename": "model.json",
                                "json_pointer": "/validation_absolute_weight_auc"}}})
            except ResearchStateError as exc:
                stage = "template" if artifacts["template"] is None else "inference"
                final_cells.append(_terminal(cell, stage, exc.status, exc, artifacts,
                                              grid_id=grid_payload["grid_id"]))
        final_cells.sort(key=lambda item: item["plan_index"])
        complete = sum(item["cell_status"] == "complete" for item in final_cells)
        terminal = sum(item["cell_status"] == "scientific_terminal" for item in final_cells)
        if len(final_cells) != plan["canonical_cell_count"] or complete + terminal != len(final_cells):
            raise ResearchError("batch cell ledger is incomplete", status="learning_curve_incomplete")
        ledger = {"schema_version": LEDGER_SCHEMA,
            "scientific_batch_id": plan["scientific_batch_id"],
            "execution_plan_id": plan["execution_plan_id"], "grid_id": grid_payload["grid_id"],
            "cells": final_cells}
        ledger["ledger_id"] = digest_json(ledger)
        summary = {"schema_version": SUMMARY_SCHEMA,
            "scientific_batch_id": plan["scientific_batch_id"],
            "execution_plan_id": plan["execution_plan_id"], "grid_id": grid_payload["grid_id"],
            "batch_status": "complete" if terminal == 0 else "scientific_terminal",
            "planned_alias_count": plan["planned_alias_count"],
            "canonical_cell_count": plan["canonical_cell_count"],
            "complete_count": complete, "terminal_count": terminal}
        summary["summary_id"] = digest_json(summary)
        with ResearchRun(target / "batch", allowed_root=target, stage=BATCH_STAGE,
                         dataset=base["dataset"], protocol=base.to_dict(),
                         upstreams=[plan_run, subset_run, grid_run] + stage_runs,
                         context={"scientific_batch_id": plan["scientific_batch_id"],
                                  "execution_plan_id": plan["execution_plan_id"]}) as run:
            run.write_json("batch-ledger.json", ledger)
            run.write_json("batch-summary.json", summary)
        batch_run = read_run(target / "batch", dataset=base["dataset"],
                             protocol=base.to_dict(), stages=(BATCH_STAGE,))
        return LoadedLearningCurveBatch(target, batch_run, plan, ledger, summary)
    except BaseException:
        raise


def read_learning_curve_batch(path, *, prepared, freeze_run, subset_run, gate_run,
                              t1_validation, base, overlay):
    """Revalidate a completed M4 batch and every directly bound stage run."""
    target = Path(path).resolve()
    prepared = _verified(prepared, base, ("prepare",), "prepared")
    freeze_run = _verified(freeze_run, base, ("compact-freeze",), "compact freeze")
    subset_run = _verified(subset_run, base, ("training-subsets",), "training subsets")
    gate_run, evidence = _validate_t1_gate(gate_run, prepared, t1_validation, base)
    batch = _verified(target / "batch", base, (BATCH_STAGE,), "sample-efficiency batch")
    plan_run = _verified(target / "plan", base, (PLAN_STAGE,), "sample-efficiency plan")
    _require_upstreams(plan_run, [prepared, freeze_run, subset_run, gate_run])
    plan = _validate_plan(plan_run.read_json("batch-plan.json"))
    expected_plan = build_learning_curve_plan(prepared=prepared, freeze_run=freeze_run,
        subset_run=subset_run, gate_run=gate_run, t1_validation=evidence, base=base, overlay=overlay,
        output_root=Path(plan["execution"]["output_root"]),
        output_name=plan["execution"]["output_name"], resources=plan["execution"]["resources"],
        progress=False)
    if canonical(plan) != canonical(expected_plan):
        _fail("sealed batch plan differs from verified inputs")
    expected_target = (Path(plan["execution"]["output_root"]) /
                       plan["execution"]["output_name"]).resolve()
    if target != expected_target:
        _fail("batch path differs from its execution plan")
    grid_run = _verified(target / "common-grid", base, (GRID_STAGE,), "common grid")
    grid = grid_run.read_json("common-grid.json")
    grid_keys = {"schema_version", "scientific_batch_id", "execution_plan_id", "participants",
                 "excluded", "initial_mass_edges", "merge_history", "final_mass_edges",
                 "status", "reason", "grid_id"}
    _keys(grid, grid_keys, "common grid")
    if (grid["schema_version"] != GRID_SCHEMA
            or grid["grid_id"] != digest_json({key: value for key, value in grid.items()
                                                if key != "grid_id"})
            or grid["scientific_batch_id"] != plan["scientific_batch_id"]
            or grid["execution_plan_id"] != plan["execution_plan_id"]):
        _fail("common grid identity mismatch")
    if grid["initial_mass_edges"] != plan["common_grid_contract"]["initial_mass_edges"]:
        _fail("common grid initial edges differ from sealed plan")
    ledger = batch.read_json("batch-ledger.json")
    summary = batch.read_json("batch-summary.json")
    _keys(ledger, {"schema_version", "scientific_batch_id", "execution_plan_id", "grid_id",
                   "cells", "ledger_id"}, "batch ledger")
    _keys(summary, {"schema_version", "scientific_batch_id", "execution_plan_id", "grid_id",
                    "batch_status", "planned_alias_count", "canonical_cell_count",
                    "complete_count", "terminal_count", "summary_id"}, "batch summary")
    if (ledger.get("schema_version") != LEDGER_SCHEMA or summary.get("schema_version") != SUMMARY_SCHEMA
            or ledger.get("ledger_id") != digest_json({key: value for key, value in ledger.items() if key != "ledger_id"})
            or summary.get("summary_id") != digest_json({key: value for key, value in summary.items() if key != "summary_id"})
            or ledger.get("scientific_batch_id") != plan["scientific_batch_id"]
            or summary.get("scientific_batch_id") != plan["scientific_batch_id"]
            or ledger.get("execution_plan_id") != plan["execution_plan_id"]
            or summary.get("execution_plan_id") != plan["execution_plan_id"]
            or ledger.get("grid_id") != grid["grid_id"] or summary.get("grid_id") != grid["grid_id"]
            or type(ledger.get("cells")) is not list or len(ledger["cells"]) != plan["canonical_cell_count"]):
        _fail("batch ledger or summary integrity mismatch")
    outcome_keys = {"plan_index", "experiment_cell_id", "stage_artifact_ids", "grid_id",
                    "cell_status", "terminal_stage", "blocked_stages", "status", "reason",
                    "exit_code", "metric_sources"}
    artifact_keys = {"model", "calibration", "template", "inference"}
    metric_keys = {"w68", "auc"}
    run_records = {}
    calibration_runs = []
    participants = []
    loaded_models = {}
    verified_calibrations = {}
    for cell, outcome in zip(plan["cells"], ledger["cells"]):
        _keys(outcome, outcome_keys, "batch cell outcome")
        _keys(outcome.get("stage_artifact_ids"), artifact_keys, "stage artifact identities")
        _keys(outcome.get("metric_sources"), metric_keys, "metric sources")
        if (outcome["plan_index"] != cell["plan_index"]
                or outcome["experiment_cell_id"] != cell["experiment_cell_id"]
                or outcome["cell_status"] not in {"complete", "scientific_terminal"}
                or outcome["exit_code"] != 0):
            _fail("batch cell outcome identity mismatch")
        artifacts = outcome["stage_artifact_ids"]
        draw = overlay["sample_draw_seeds"][0] if cell["sample_draw_seed"] is None else cell["sample_draw_seed"]
        if artifacts["model"] is not None:
            model = read_subset_discriminant_run(target / cell["relative_paths"]["model"],
                prepared=prepared, freeze_run=freeze_run, subset_run=subset_run, base=base,
                overlay=overlay, fraction=cell["sample_fraction_target"], draw=draw,
                representation_id=cell["representation_id"], network_seed=cell["network_seed"])
            if model.run.manifest["artifact_id"] != artifacts["model"]:
                _fail("ledger model artifact mismatch")
            loaded_models[cell["experiment_cell_id"]] = model
            run_records[(cell["plan_index"], "model")] = model.run
        if artifacts["calibration"] is not None:
            if artifacts["model"] is None:
                _fail("calibration exists without model")
            cal_run = _verified(target / cell["relative_paths"]["calibration"], base,
                                (CALIBRATION_STAGE,), "cell calibration")
            _require_upstreams(cal_run, [plan_run, prepared, loaded_models[cell["experiment_cell_id"]].run])
            if cal_run.manifest["artifact_id"] != artifacts["calibration"]:
                _fail("ledger calibration artifact mismatch")
            envelope = cal_run.read_json("calibration.json")
            _keys(envelope, {"schema_version", "scientific_batch_id", "execution_plan_id",
                             "experiment_cell_id", "calibration", "record_id"}, "calibration envelope")
            calibration = envelope["calibration"]
            from .discriminants import digest
            expected_bundle = build_raw_calibration_bundle(
                prepared, loaded_models[cell["experiment_cell_id"]], base)
            expected_calibration = expected_bundle.to_dict()
            if (envelope["schema_version"] != CALIBRATION_SCHEMA
                    or envelope["scientific_batch_id"] != plan["scientific_batch_id"]
                    or envelope["execution_plan_id"] != plan["execution_plan_id"]
                    or envelope["record_id"] != digest_json({key: value for key, value in envelope.items()
                                                              if key != "record_id"})
                    or envelope["experiment_cell_id"] != cell["experiment_cell_id"]
                    or calibration.get("calibration_id") != digest({key: value for key, value in calibration.items()
                                                                    if key != "calibration_id"})
                    or canonical(calibration.get("experiment_lineage")) != loaded_models[cell["experiment_cell_id"]].lineage.payload
                    or canonical(calibration) != canonical(expected_calibration)):
                _fail("calibration envelope binding mismatch")
            # Keep the immutable verified bundle for semantic template/grid replay.
            verified_calibrations[cell["experiment_cell_id"]] = expected_bundle
            calibration_runs.append(cal_run)
            participants.append({"experiment_cell_id": cell["experiment_cell_id"],
                                 "calibration_artifact_id": cal_run.manifest["artifact_id"]})
            run_records[(cell["plan_index"], "calibration")] = cal_run
        if artifacts["template"] is not None:
            if artifacts["calibration"] is None:
                _fail("template exists without calibration")
            template_run = _verified(target / cell["relative_paths"]["template"], base,
                                     (TEMPLATE_STAGE,), "cell template")
            _require_upstreams(template_run, [plan_run, prepared,
                run_records[(cell["plan_index"], "calibration")], grid_run])
            if template_run.manifest["artifact_id"] != artifacts["template"]:
                _fail("ledger template artifact mismatch")
            envelope = template_run.read_json("template.json")
            _keys(envelope, {"schema_version", "scientific_batch_id", "execution_plan_id",
                             "experiment_cell_id", "template", "grid_id", "record_id"},
                  "template envelope")
            if (envelope["schema_version"] != TEMPLATE_SCHEMA
                    or envelope["scientific_batch_id"] != plan["scientific_batch_id"]
                    or envelope["execution_plan_id"] != plan["execution_plan_id"]
                    or envelope["record_id"] != digest_json({key: value for key, value in envelope.items()
                                                              if key != "record_id"})
                    or envelope["grid_id"] != grid["grid_id"]
                    or envelope["experiment_cell_id"] != cell["experiment_cell_id"]):
                _fail("template envelope binding mismatch")
            require_template_lineage(envelope["template"], loaded_models[cell["experiment_cell_id"]].lineage)
            if envelope["template"]["mass_edges"] != grid["final_mass_edges"]:
                _fail("template does not use the common grid")
            expected_template = build_sample_efficiency_template(prepared,
                loaded_models[cell["experiment_cell_id"]],
                verified_calibrations[cell["experiment_cell_id"]], base,
                mass_edges=grid["final_mass_edges"])
            if canonical(envelope["template"]) != canonical(expected_template):
                _fail("template differs from direct-upstream replay")
            run_records[(cell["plan_index"], "template")] = template_run
        if artifacts["inference"] is not None:
            if artifacts["template"] is None:
                _fail("inference exists without template")
            inference_run = _verified(target / cell["relative_paths"]["inference"], base,
                                      (INFERENCE_STAGE,), "cell inference")
            _require_upstreams(inference_run, [plan_run, run_records[(cell["plan_index"], "template")], grid_run])
            if inference_run.manifest["artifact_id"] != artifacts["inference"]:
                _fail("ledger inference artifact mismatch")
            envelope = inference_run.read_json("inference.json")
            _keys(envelope, {"schema_version", "scientific_batch_id", "execution_plan_id",
                             "experiment_cell_id", "result", "grid_id", "t1_evidence_sha256",
                             "metric_pointers", "record_id"}, "inference envelope")
            result = envelope["result"]
            intervals = result.get("results", [{}])[0].get("intervals", []) if type(result) is dict else []
            if (envelope["schema_version"] != INFERENCE_SCHEMA
                    or envelope["scientific_batch_id"] != plan["scientific_batch_id"]
                    or envelope["execution_plan_id"] != plan["execution_plan_id"]
                    or envelope["record_id"] != digest_json({key: value for key, value in envelope.items()
                                                              if key != "record_id"})
                    or envelope["grid_id"] != grid["grid_id"]
                    or envelope["t1_evidence_sha256"] != plan["t1_evidence_sha256"]
                    or envelope["metric_pointers"] != {"w68": "/result/results/0/intervals/confidence=0.68/width",
                                                        "auc": "/model/validation_absolute_weight_auc"}
                    or result.get("layer") != "T1" or result.get("expectation_kind") != "model_self_asimov"
                    or [row.get("mu") for row in result.get("results", [])] != [1.0]
                    or not any(row.get("confidence") == 0.68 for row in intervals)
                    or result.get("result_id") != digest_json({key: value for key, value in result.items()
                                                               if key != "result_id"})
                    or canonical(result.get("experiment_lineage")) != loaded_models[cell["experiment_cell_id"]].lineage.payload):
                _fail("inference envelope binding mismatch")
            expected_result = run_asimov(run_records[(cell["plan_index"], "template")].read_json(
                "template.json")["template"], protocol=base, layer="T1", t1_validation=evidence,
                injections=(1.0,), experiment_lineage=loaded_models[cell["experiment_cell_id"]].lineage)
            if canonical(result) != canonical(expected_result):
                _fail("inference differs from fixed T1 model-self replay")
            run_records[(cell["plan_index"], "inference")] = inference_run
        order = ["model", "calibration", "template", "inference"]
        if outcome["cell_status"] == "complete":
            if (any(artifacts[name] is None for name in order)
                    or outcome["grid_id"] != grid["grid_id"]
                    or outcome["terminal_stage"] is not None or outcome["blocked_stages"]):
                _fail("complete cell lacks its full stage chain")
            if outcome["status"] != "complete" or outcome["reason"] is not None:
                _fail("complete cell has invalid terminal fields")
            expected_sources = {
                "w68": {"artifact_id": artifacts["inference"], "filename": "inference.json",
                        "json_pointer": "/result/results/0/intervals/confidence=0.68/width"},
                "auc": {"artifact_id": artifacts["model"], "filename": "model.json",
                        "json_pointer": "/validation_absolute_weight_auc"}}
            if outcome["metric_sources"] != expected_sources:
                _fail("complete cell metric source binding mismatch")
        else:
            allowed_terminal = {"training_subset_insufficient_statistics", "insufficient_statistics",
                                "nonpositive_calibration_yield", "template_stat_model_unvalidated",
                                "training_failed", "fit_failed", "inference_incomplete"}
            if outcome["terminal_stage"] not in order:
                _fail("terminal cell has no valid terminal stage")
            expected_blocked = order[order.index(outcome["terminal_stage"]) + 1:]
            if outcome["blocked_stages"] != expected_blocked:
                _fail("terminal cell blocked-stage sequence mismatch")
            if outcome["metric_sources"] != {"w68": None, "auc": None}:
                _fail("terminal cell cannot publish metric sources")
            if outcome["status"] not in allowed_terminal or type(outcome["reason"]) is not str:
                _fail("unregistered scientific terminal status")
            terminal_index = order.index(outcome["terminal_stage"])
            for index, stage in enumerate(order):
                if index < terminal_index and artifacts[stage] is None:
                    _fail("terminal cell is missing a successful stage prefix")
                if index > terminal_index and artifacts[stage] is not None:
                    _fail("terminal cell publishes a blocked-stage artifact")
            expected_grid = grid["grid_id"] if terminal_index >= order.index("template") else None
            if outcome["grid_id"] != expected_grid:
                _fail("terminal cell grid binding differs from its stage")
    if grid["participants"] != participants:
        _fail("common grid participant set differs from calibration successes")
    expected_excluded = [{"experiment_cell_id": cell["experiment_cell_id"], "status": outcome["status"]}
                         for cell, outcome in zip(plan["cells"], ledger["cells"])
                         if outcome["stage_artifact_ids"]["calibration"] is None]
    if grid["excluded"] != expected_excluded:
        _fail("common grid excluded-cell ledger mismatch")
    replay_frames = {cell_id: prepare_sample_efficiency_template_frame(
                        prepared, loaded_models[cell_id], verified_calibrations[cell_id], base)
                     for cell_id in [item["experiment_cell_id"] for item in participants]}
    replay_grid = (common_mass_grid(replay_frames,
        mass_edges=plan["common_grid_contract"]["initial_mass_edges"], thresholds=base["templates"])
        if replay_frames else {"status": "insufficient_statistics",
                               "mass_edges": plan["common_grid_contract"]["initial_mass_edges"],
                               "merge_history": []})
    expected_grid_reason = (None if replay_grid["status"] == "valid"
                            else "common grid has insufficient support")
    if (replay_grid["status"] != grid["status"]
            or replay_grid["mass_edges"] != grid["final_mass_edges"]
            or replay_grid["merge_history"] != grid["merge_history"]
            or grid["reason"] != expected_grid_reason):
        _fail("common grid differs from all calibration-success cells")
    _require_upstreams(grid_run, [plan_run, subset_run] + calibration_runs)
    # Publication order is model+calibration per cell, followed by template+inference per cell.
    stage_runs = []
    for cell in plan["cells"]:
        for stage in ("model", "calibration"):
            if (cell["plan_index"], stage) in run_records:
                stage_runs.append(run_records[(cell["plan_index"], stage)])
    for cell in plan["cells"]:
        for stage in ("template", "inference"):
            if (cell["plan_index"], stage) in run_records:
                stage_runs.append(run_records[(cell["plan_index"], stage)])
    _require_upstreams(batch, [plan_run, subset_run, grid_run] + stage_runs)
    complete = sum(item["cell_status"] == "complete" for item in ledger["cells"])
    terminal = sum(item["cell_status"] == "scientific_terminal" for item in ledger["cells"])
    expected_summary = {"schema_version": SUMMARY_SCHEMA,
        "scientific_batch_id": plan["scientific_batch_id"],
        "execution_plan_id": plan["execution_plan_id"], "grid_id": grid["grid_id"],
        "batch_status": "complete" if terminal == 0 else "scientific_terminal",
        "planned_alias_count": plan["planned_alias_count"],
        "canonical_cell_count": plan["canonical_cell_count"],
        "complete_count": complete, "terminal_count": terminal}
    expected_summary["summary_id"] = digest_json(expected_summary)
    if canonical(summary) != canonical(expected_summary) or complete + terminal != plan["canonical_cell_count"]:
        _fail("batch summary or completeness count mismatch")
    return LoadedLearningCurveBatch(target, batch, plan, ledger, summary)
