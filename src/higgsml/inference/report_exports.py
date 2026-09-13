"""Normalized, analysis-ready exports derived from receipt-verified report inputs."""
from __future__ import annotations

import csv
import itertools
import json
from pathlib import Path

import numpy as np

from higgsml.artifacts import digest_json
from higgsml.errors import ResearchError


EXPORT_VERSION = "h4l-analysis-export-v1"


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _write_csv(run, name, rows, fields):
    path = run.path / name
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        for source in rows:
            row = {}
            for field in fields:
                value = source.get(field)
                row[field] = _json(value) if isinstance(value, (dict, list)) else value
            writer.writerow(row)
    run.register_file(name)


def _subset(model):
    groups = model.get("groups")
    return "" if groups is None else "".join(groups)


def _candidate_key(model):
    key = f"{model.get('candidate')}:{model.get('seed')}"
    if model.get("candidate") == "M6":
        key += f":lambda={model.get('target_lambda'):g}"
    if model.get("groups") is not None:
        key += ":groups=" + _subset(model)
    return key


def _source_id(item):
    return item.manifest.get("context", {}).get("prepared_artifact_id")


def _unique_runs(runs):
    result = {}
    for item in runs:
        artifact_id = item.manifest["artifact_id"]
        if artifact_id in result:
            raise ResearchError("duplicate analysis input artifact")
        result[artifact_id] = item
    return list(result.values())


def _model_tables(training_runs):
    models, history, mass = [], [], []
    model_payloads = {}
    for item in training_runs:
        if item.manifest.get("status") != "complete":
            continue
        model = item.read_json("model.json")
        key = _candidate_key(model)
        if key in model_payloads:
            raise ResearchError("duplicate training model in analysis export")
        model_payloads[key] = model
        base = {"candidate_key": key, "candidate": model.get("candidate"), "subset": _subset(model),
                "seed": model.get("seed"), "representation": model.get("representation"),
                "input_count": len(model.get("ordered_inputs", [])), "ordered_inputs": model.get("ordered_inputs", []),
                "status": model.get("status"), "validation_absolute_weight_auc": model.get("validation_absolute_weight_auc"),
                "selected_epoch": model.get("selected_epoch"), "checkpoint_rule": model.get("checkpoint_rule"),
                "target_lambda": model.get("target_lambda"), "effective_lambda": model.get("effective_lambda"),
                "model_id": model.get("model_id"), "artifact_id": item.manifest["artifact_id"],
                "protocol_id": model.get("protocol_id"), "prepared_artifact_id": _source_id(item),
                "metric_role": "validation", "weight_measure": "absolute_physical_weight",
                "selection_note": "checkpoint_selected_on_same_validation_auc"}
        models.append(base)
        for epoch in model.get("history", []):
            diagnostics = epoch.get("diagnostics", {}) or {}
            history.append({"candidate_key": key, "seed": model.get("seed"), "subset": _subset(model),
                            "epoch": epoch.get("epoch"), "loss": epoch.get("loss"),
                            "classification_loss": epoch.get("classification_loss"),
                            "adversary_loss": epoch.get("adversary_loss"),
                            "effective_lambda": epoch.get("effective_lambda"),
                            "validation_absolute_weight_auc": epoch.get("validation_absolute_weight_auc"),
                            "absolute_weight_mass_ks": diagnostics.get("absolute_weight_mass_ks"),
                            "mass_bin_acceptance": diagnostics.get("mass_bin_acceptance"),
                            "is_selected_epoch": epoch.get("epoch") == model.get("selected_epoch"),
                            "detail_status": "recorded" if "classification_loss" in epoch else "not_recorded",
                            "model_id": model.get("model_id")})
        diagnostics = model.get("diagnostics", {}) or {}
        acceptance = diagnostics.get("mass_bin_acceptance", []) or []
        edges = model.get("mass_bin_boundaries", []) or []
        for index, value in enumerate(acceptance):
            mass.append({"candidate_key": key, "seed": model.get("seed"), "subset": _subset(model),
                         "mass_bin_index": index, "mass_low": edges[index] if index < len(edges) - 1 else None,
                         "mass_high": edges[index + 1] if index < len(edges) - 1 else None,
                         "background_acceptance": value,
                         "absolute_weight_mass_ks": diagnostics.get("absolute_weight_mass_ks"),
                         "working_point": diagnostics.get("absolute_weight_working_point"),
                         "threshold": diagnostics.get("threshold"),
                         "threshold_source": diagnostics.get("threshold_source"),
                         "evaluation_source": diagnostics.get("evaluation_source"),
                         "model_id": model.get("model_id")})
    return models, history, mass, model_payloads


def _calibration_tables(evaluation_runs):
    bundles = {}
    for item in evaluation_runs:
        if item.manifest.get("status") != "complete":
            continue
        if item.manifest["stage"] == "calibrate":
            candidates = [item.read_json("calibration.json")]
        elif item.manifest["stage"] == "templates":
            candidates = list(item.read_json("calibrations.json").values())
        else:
            continue
        for bundle in candidates:
            identity = (bundle.get("key"), bundle.get("mapping_id"))
            bundles.setdefault(identity, bundle)
    summaries, slices, bins = [], [], []
    for bundle in bundles.values():
        mapping = bundle.get("mapping")
        fitted_slices = mapping.get("slices", []) if isinstance(mapping, dict) else []
        summaries.append({"candidate_key": bundle.get("key"), "candidate_id": bundle.get("candidate_id"),
                          "seed": bundle.get("seed"), "subset": _subset(bundle.get("model") or {}),
                          "transform": bundle.get("transform"), "status": bundle.get("status"),
                          "model_id": bundle.get("model_id"), "mapping_id": bundle.get("mapping_id"),
                          "threshold_id": (bundle.get("thresholds") or {}).get("threshold_id"),
                          "source_role": mapping.get("source_role") if isinstance(mapping, dict) else "calibration_background",
                          "final_slice_count": len(fitted_slices),
                          "merge_count": len(mapping.get("merges", [])) if isinstance(mapping, dict) else 0,
                          "merge_history": mapping.get("merges", []) if isinstance(mapping, dict) else [],
                          "min_effective_count": min((s.get("effective_count") for s in fitted_slices), default=None),
                          "min_cancellation_ratio": min((s.get("cancellation_ratio") for s in fitted_slices), default=None),
                          "max_correction_chi2": max((s.get("correction_chi2") for s in fitted_slices), default=None),
                          "detail_status": "recorded" if mapping is not None else "not_applicable_raw"})
        if not isinstance(mapping, dict):
            continue
        score_edges = mapping.get("score_edges", [])
        for slice_index, part in enumerate(fitted_slices):
            correction = part.get("correction", [])
            slices.append({"candidate_key": bundle.get("key"), "seed": bundle.get("seed"),
                           "mapping_id": bundle.get("mapping_id"), "slice_index": slice_index,
                           "mass_low": part.get("interval", [None, None])[0],
                           "mass_high": part.get("interval", [None, None])[1], "mass_center": part.get("center"),
                           "effective_count": part.get("effective_count"), "cancellation_ratio": part.get("cancellation_ratio"),
                           "total_yield": part.get("total_yield"), "correction_chi2": part.get("correction_chi2"),
                           "raw_negative_bin_count": sum(value < 0 for value in part.get("raw_yields", [])),
                           "fitted_zero_bin_count": sum(value == 0 for value in part.get("fitted_yields", [])),
                           "sum_absolute_correction": float(np.abs(correction).sum()) if correction else 0.0,
                           "max_absolute_correction": float(np.abs(correction).max()) if correction else 0.0})
            length = max(len(part.get(name, [])) for name in ("raw_yields", "fitted_yields", "variances", "correction", "probabilities"))
            for bin_index in range(length):
                def at(name):
                    values = part.get(name, [])
                    return values[bin_index] if bin_index < len(values) else None
                bins.append({"candidate_key": bundle.get("key"), "seed": bundle.get("seed"),
                             "mapping_id": bundle.get("mapping_id"), "slice_index": slice_index,
                             "score_bin_index": bin_index,
                             "score_low": score_edges[bin_index] if bin_index < len(score_edges) - 1 else None,
                             "score_high": score_edges[bin_index + 1] if bin_index < len(score_edges) - 1 else None,
                             "raw_yield": at("raw_yields"), "fitted_yield": at("fitted_yields"),
                             "variance": at("variances"), "correction": at("correction"),
                             "probability": at("probabilities")})
    return summaries, slices, bins


def _template_tables(evaluation_runs):
    grids = {}
    for item in evaluation_runs:
        if item.manifest.get("status") == "complete" and item.manifest["stage"] == "templates":
            grids.setdefault(item.manifest["artifact_id"], item.read_json("templates.json"))
    rows, covariance = [], []
    for artifact_id, grid in grids.items():
        edges = grid.get("mass_edges", [])
        for key, template in grid.get("templates", {}).items():
            categories = template.get("categories", [])
            n_mass = len(edges) - 1
            for sample in template.get("samples", []):
                values = sample.get("yield", [])
                for bin_index, signed_yield in enumerate(values):
                    category_index, mass_index = divmod(bin_index, n_mass) if n_mass else (None, None)
                    def at(name):
                        data = sample.get(name, [])
                        return data[bin_index] if bin_index < len(data) else None
                    rows.append({"candidate_key": key, "candidate_id": template.get("candidate_id"),
                                 "seed": template.get("seed"), "mapping_id": template.get("mapping_id"),
                                 "process": sample.get("name"), "is_signal": sample.get("is_signal"),
                                 "category": categories[category_index] if category_index is not None and category_index < len(categories) else None,
                                 "flat_bin_index": bin_index, "mass_low": edges[mass_index] if mass_index is not None else None,
                                 "mass_high": edges[mass_index + 1] if mass_index is not None else None,
                                 "signed_yield": signed_yield, "variance": at("variance"),
                                 "sum_abs_weight": at("sum_abs_weight"), "sum_positive_weight": at("sum_positive_weight"),
                                 "sum_negative_weight": at("sum_negative_weight"), "group_count": at("group_count"),
                                 "neff_signed": at("neff_signed"), "neff_abs": at("neff_abs"), "rho": at("rho"),
                                 "bin_status": at("bin_status"), "active_bin": bin_index in template.get("active_bins", []),
                                 "template_artifact_id": artifact_id})
                matrix = sample.get("covariance", [])
                for left, matrix_row in enumerate(matrix):
                    for right, value in enumerate(matrix_row):
                        if value != 0:
                            covariance.append({"candidate_key": key, "process": sample.get("name"),
                                               "left_flat_bin": left, "right_flat_bin": right,
                                               "covariance": value, "sparse_nonzero_only": True,
                                               "template_artifact_id": artifact_id})
    return rows, covariance, grids


def _inference_tables(inference_runs):
    records, intervals, toys, coverage, diagnostics, paired, stress = {}, [], [], [], [], [], []
    procedures, bootstraps = [], []
    nominal = {}
    for item in inference_runs:
        if item.manifest.get("status") != "complete" or item.manifest["stage"] != "infer":
            continue
        scope = item.manifest.get("context", {}).get("inference_scope", {})
        if scope.get("expectation_kind") != "assessment" or scope.get("procedure", "fixed") != "fixed":
            continue
        for key, result in item.read_json("inference.json").items():
            if result.get("stress") or "toys" not in result:
                continue
            for confidence, summary in result.get("coverage", {}).items():
                diagnostic = result.get("diagnostics", {}).get(confidence, {})
                widths = [row.get("width") for toy in result["toys"].get("results", [])
                          for row in toy.get("intervals", [])
                          if str(row.get("confidence")) == str(confidence) and row.get("status") == "valid"
                          and row.get("width") is not None]
                nominal[(key, result.get("seed"), scope.get("mu"), str(confidence))] = {
                    "coverage": summary.get("coverage"),
                    "bias": diagnostic.get("bias_valid_fits"),
                    "mean_width": float(np.mean(widths)) if widths else None,
                }
    for item in inference_runs:
        if item.manifest.get("status") != "complete":
            continue
        stage = item.manifest["stage"]
        scope = item.manifest.get("context", {}).get("inference_scope", {})
        if stage == "mc-bootstrap":
            payload = item.read_json("bootstrap.json")
            for replica in payload.get("replicas", []):
                bootstraps.append({"artifact_id": item.manifest["artifact_id"], "bootstrap_id": payload.get("bootstrap_id"),
                                   "replica": replica.get("replica"), "status": replica.get("status"),
                                   "reason": replica.get("reason"),
                                   "median_relative_improvement": replica.get("median_relative_improvement"),
                                   "paired_seeds": replica.get("paired_seeds")})
            continue
        if stage != "infer":
            continue
        if "procedure.json" in item.manifest.get("files", {}):
            procedure = item.read_json("procedure.json")
            for replica in procedure.get("replicas", []):
                candidates = (replica.get("result") or {}).get("candidates", {})
                if not candidates:
                    procedures.append({"artifact_id": item.manifest["artifact_id"], "procedure": "t2",
                                       "replica": replica.get("replica"), "status": replica.get("status"),
                                       "reason": replica.get("reason") or replica.get("error"),
                                       "mapping_id": replica.get("mapping_id"),
                                       "planned_outer_replicas": procedure.get("outer_replicas"),
                                       "inner_toys": procedure.get("inner_toys")})
                for candidate_key, candidate in candidates.items():
                    for confidence, summary in candidate.get("coverage", {}).items():
                        diagnostic = candidate.get("diagnostics", {}).get(confidence, {})
                        interval_index = {"0.68": 0, "0.95": 1}.get(str(confidence))
                        widths = [] if interval_index is None else [
                            row["intervals"][interval_index].get("width")
                            for row in candidate.get("toys", {}).get("results", [])
                            if len(row.get("intervals", [])) > interval_index
                            and row["intervals"][interval_index].get("status") == "valid"
                            and row["intervals"][interval_index].get("width") is not None]
                        procedures.append({"artifact_id": item.manifest["artifact_id"], "procedure": "t2",
                                           "replica": replica.get("replica"), "status": candidate.get("status"),
                                           "reason": candidate.get("reason") or replica.get("error"),
                                           "mapping_id": replica.get("mapping_id"),
                                           "planned_outer_replicas": procedure.get("outer_replicas"),
                                           "inner_toys": procedure.get("inner_toys"),
                                           "candidate_key": candidate_key, "seed": candidate.get("seed"),
                                           "confidence_level": confidence, "coverage": summary.get("coverage"),
                                           "valid_fits": summary.get("valid_fits"), "failed_fits": summary.get("failed_fits"),
                                           "bias": diagnostic.get("bias_valid_fits"),
                                           "pull_mean": diagnostic.get("pull_mean"), "pull_std": diagnostic.get("pull_std"),
                                           "mean_width": float(np.mean(widths)) if widths else None,
                                           "median_width": float(np.median(widths)) if widths else None})
        payload = item.read_json("inference.json")
        for key, result in payload.items():
            record_key = key + "|" + digest_json({"artifact": item.manifest["artifact_id"], "scope": scope})
            records[record_key] = {"candidate_key": key, "scope": scope, "result": result,
                                   "artifact_id": item.manifest["artifact_id"]}
            asimov = result.get("asimov", {})
            for injection in asimov.get("results", []):
                for interval in injection.get("intervals", []):
                    intervals.append({"candidate_key": key, "candidate_id": asimov.get("candidate_id"),
                                      "seed": result.get("seed"), "layer": asimov.get("layer"),
                                      "expectation_kind": asimov.get("expectation_kind"), "procedure": scope.get("procedure"),
                                      "injected_mu": injection.get("mu"), "confidence_level": interval.get("confidence"),
                                      "muhat": interval.get("muhat"), "lower": interval.get("lower"),
                                      "upper": interval.get("upper"), "width": interval.get("width"),
                                      "lower_at_boundary": interval.get("lower_at_boundary"),
                                      "upper_search_bound": interval.get("upper_search_bound"), "status": interval.get("status"),
                                      "mapping_id": asimov.get("mapping_id"), "comparison_cohort_id": scope.get("comparison_cohort_id"),
                                      "artifact_id": item.manifest["artifact_id"]})
            toy_payload = result.get("toys", {})
            pairing_id = result.get("pairing_id") or toy_payload.get("pairing_id")
            for toy_index, toy in enumerate(toy_payload.get("results", [])):
                for interval in toy.get("intervals", []):
                    toys.append({"candidate_key": key, "seed": result.get("seed"), "toy_index": toy_index,
                                 "injected_mu": toy_payload.get("mu", scope.get("mu")),
                                 "confidence_level": interval.get("confidence"), "muhat": interval.get("muhat"),
                                 "lower": interval.get("lower"), "upper": interval.get("upper"),
                                 "width": interval.get("width"), "lower_at_boundary": interval.get("lower_at_boundary"),
                                 "status": interval.get("status"), "pairing_id": pairing_id,
                                 "upper_search_bound": interval.get("upper_search_bound"),
                                 "auxiliary_generation": toy_payload.get("auxiliary_generation"),
                                 "expectation_kind": toy_payload.get("expectation_kind", scope.get("expectation_kind")),
                                 "artifact_id": item.manifest["artifact_id"]})
            for confidence, summary in result.get("coverage", {}).items():
                coverage.append({"candidate_key": key, "seed": result.get("seed"), "confidence_level": confidence,
                                 "injected_mu": scope.get("mu"), "expectation_kind": scope.get("expectation_kind"),
                                 "procedure": scope.get("procedure", "fixed"), "pairing_id": pairing_id,
                                 **summary, "artifact_id": item.manifest["artifact_id"]})
            for confidence, summary in result.get("diagnostics", {}).items():
                if isinstance(summary, dict) and confidence != "signed_mu":
                    diagnostics.append({"candidate_key": key, "seed": result.get("seed"),
                                        "confidence_level": confidence, "injected_mu": scope.get("mu"),
                                        "expectation_kind": scope.get("expectation_kind"),
                                        "procedure": scope.get("procedure", "fixed"), "pairing_id": pairing_id,
                                        **summary, "artifact_id": item.manifest["artifact_id"]})
            for field, comparison in (("paired_coverage_vs_M0", "coverage_vs_M0"),
                                      ("paired_coverage_vs_M4", "M5_coverage_minus_M4")):
                for confidence, summary in result.get(field, {}).items():
                    paired.append({"candidate_key": key, "comparison": comparison, "confidence_level": confidence,
                                   **summary, "artifact_id": item.manifest["artifact_id"]})
            if result.get("stress"):
                scenario = result["stress"]
                for confidence, summary in result.get("coverage", {}).items():
                    diagnostic = result.get("diagnostics", {}).get(confidence, {})
                    interval_index = {"0.68": 0, "0.95": 1}.get(str(confidence))
                    widths = [] if interval_index is None else [
                        row["intervals"][interval_index].get("width")
                        for row in result.get("toys", {}).get("results", [])
                        if len(row.get("intervals", [])) > interval_index
                        and row["intervals"][interval_index].get("status") == "valid"
                        and row["intervals"][interval_index].get("width") is not None]
                    mean_width = float(np.mean(widths)) if widths else None
                    reference = nominal.get((key, result.get("seed"), scope.get("mu"), str(confidence)), {})
                    def delta(name, value):
                        baseline = reference.get(name)
                        return value - baseline if value is not None and baseline is not None else None
                    stress.append({"candidate_key": key, "seed": result.get("seed"), "status": result.get("status"),
                                   "kind": scenario.get("kind"), "direction": scenario.get("direction"),
                                   "mode": scenario.get("mode"), "source": scenario.get("source"),
                                   "reference_mapping_id": scenario.get("reference_mapping_id"),
                                   "injected_mu": scope.get("mu"), "confidence_level": confidence,
                                   "coverage": summary.get("coverage"), "bias": diagnostic.get("bias_valid_fits"),
                                   "pull_mean": diagnostic.get("pull_mean"), "pull_std": diagnostic.get("pull_std"),
                                   "mean_width": mean_width, "median_width": float(np.median(widths)) if widths else None,
                                   "coverage_change_vs_nominal": delta("coverage", summary.get("coverage")),
                                   "bias_change_vs_nominal": delta("bias", diagnostic.get("bias_valid_fits")),
                                   "mean_width_change_vs_nominal": delta("mean_width", mean_width),
                                   "nominal_status": "matched" if reference else "not_recorded",
                                   "artifact_id": item.manifest["artifact_id"]})
    for row in procedures:
        if not row.get("candidate_key") or row.get("confidence_level") is None:
            continue
        peers = [value for value in procedures
                 if value.get("artifact_id") == row["artifact_id"]
                 and value.get("candidate_key") == row["candidate_key"]
                 and str(value.get("confidence_level")) == str(row["confidence_level"])]
        row["successful_outer_replicas"] = sum(value.get("status") == "valid" for value in peers)
        for source, target in (("coverage", "coverage_std_across_replicas"),
                               ("bias", "bias_std_across_replicas"),
                               ("mean_width", "mean_width_std_across_replicas")):
            values = [value.get(source) for value in peers if value.get("status") == "valid"
                      and value.get(source) is not None]
            row[target] = float(np.std(values, ddof=1)) if len(values) > 1 else None
    return records, intervals, toys, coverage, diagnostics, paired, procedures, stress, bootstraps


def _feature_tables(report, models):
    by_key = {row["candidate_key"]: row for row in models}
    baselines = {row["seed"]: row for row in models if row["candidate"] == "M0c" and row["subset"] == ""}
    metrics = []
    comparisons = {row.get("seed"): row for row in report.get("feature_combination_comparisons", [])}
    for seed in range(42, 47):
        comparison = comparisons.get(seed, {})
        widths = {row["subset"]: row for row in comparison.get("nonempty_combinations", [])}
        for subset in ["".join(c) for size in range(1, 5) for c in itertools.combinations("ABCD", size)]:
            key = f"M3:{seed}:groups={subset}"
            model = by_key.get(key)
            width = widths.get(subset)
            baseline = baselines.get(seed)
            auc = model.get("validation_absolute_weight_auc") if model else None
            baseline_auc = baseline.get("validation_absolute_weight_auc") if baseline else None
            metrics.append({"candidate_key": key, "subset": subset, "seed": seed, "raw_validation_auc": auc,
                            "delta_auc_vs_m0c": auc - baseline_auc if auc is not None and baseline_auc is not None else None,
                            "width68": width.get("width68") if width else None,
                            "relative_w68_improvement_vs_m0c": width.get("relative_improvement_vs_empty") if width else None,
                            "selected_epoch": model.get("selected_epoch") if model else None,
                            "model_status": model.get("status") if model else "missing",
                            "inference_status": comparison.get("status", "missing"),
                            "comparison_cohort_id": comparison.get("comparison_cohort_id")})
    summary = []
    for subset in sorted({row["subset"] for row in metrics}, key=lambda value: (len(value), value)):
        rows = [row for row in metrics if row["subset"] == subset]
        def values(name): return [row[name] for row in rows if row[name] is not None]
        aucs, deltas, widths, improvements = (values(name) for name in ("raw_validation_auc", "delta_auc_vs_m0c", "width68", "relative_w68_improvement_vs_m0c"))
        auc_complete = len(aucs) == len(deltas) == 5
        inference_complete = len(widths) == len(improvements) == 5
        summary.append({"subset": subset, "status": "valid" if auc_complete else "incomplete",
                        "auc_status": "valid" if auc_complete else "incomplete",
                        "inference_status": "valid" if inference_complete else "incomplete",
                        "auc_complete_seed_count": min(len(aucs), len(deltas)),
                        "inference_complete_seed_count": min(len(widths), len(improvements)),
                        "median_auc": float(np.median(aucs)) if len(aucs) == 5 else None,
                        "min_auc": min(aucs) if len(aucs) == 5 else None, "max_auc": max(aucs) if len(aucs) == 5 else None,
                        "median_delta_auc_vs_m0c": float(np.median(deltas)) if len(deltas) == 5 else None,
                        "min_delta_auc_vs_m0c": min(deltas) if len(deltas) == 5 else None,
                        "max_delta_auc_vs_m0c": max(deltas) if len(deltas) == 5 else None,
                        "median_width68": float(np.median(widths)) if inference_complete else None,
                        "min_width68": min(widths) if inference_complete else None,
                        "max_width68": max(widths) if inference_complete else None,
                        "median_relative_w68_improvement": float(np.median(improvements)) if inference_complete else None,
                        "min_relative_w68_improvement": min(improvements) if inference_complete else None,
                        "max_relative_w68_improvement": max(improvements) if inference_complete else None})
    return metrics, summary


def publish_analysis_exports(run, report, *, training_runs=(), evaluation_runs=(), evidence_runs=(), result_runs=()):
    training_runs = _unique_runs(training_runs)
    evaluation_runs = _unique_runs(evaluation_runs)
    inference_runs = _unique_runs([*result_runs, *evaluation_runs])
    bound_inputs = [*training_runs, *evaluation_runs, *result_runs]
    sources = {_source_id(item) for item in bound_inputs if _source_id(item)}
    if len(sources) > 1 or (sources and any(_source_id(item) is None for item in bound_inputs)):
        raise ResearchError("analysis exports cannot mix prepared populations or unbound inputs")
    for item in evidence_runs:
        if item.manifest.get("status") != "complete":
            continue
        population = item.read_json("evidence.json").get("prepared_artifact_id")
        if population is not None and sources and population not in sources:
            raise ResearchError("evidence package belongs to another prepared population")
    models, history, mass, _ = _model_tables(training_runs)
    calibration, slices, calibration_bins = _calibration_tables(evaluation_runs)
    template_bins, covariance, grids = _template_tables(evaluation_runs)
    records, intervals, toys, coverage, diagnostics, paired, procedures, stress, bootstraps = _inference_tables(inference_runs)
    feature_metrics, feature_summary = _feature_tables(report, models)
    attribution, interactions = [], []
    for comparison in report.get("feature_combination_comparisons", []):
        shapley = comparison.get("shapley", {})
        for group, value in shapley.get("contributions", {}).items():
            attribution.append({"seed": comparison.get("seed"), "group": group, "contribution": value,
                                "family_id": shapley.get("family_id"), "value_function": shapley.get("value_function"),
                                "unit": shapley.get("unit"), "efficiency_residual": shapley.get("efficiency_residual"),
                                "status": shapley.get("status")})
        for row in shapley.get("interactions", []):
            interactions.append({"seed": comparison.get("seed"), "family_id": shapley.get("family_id"), **row})
    statuses = []
    for history_name in ("training_state_history", "candidate_state_history"):
        for key, history_rows in report.get(history_name, {}).items():
            for row in history_rows:
                statuses.append({"candidate_key": key, "stage": row.get("stage"), "status": row.get("status"),
                                 "reason": row.get("reason"), "artifact_id": row.get("artifact_id")})
    for row in report.get("terminal_runs", []):
        statuses.append({"candidate_key": row.get("candidate_key"), "stage": row.get("stage"),
                         "status": row.get("status"), "reason": row.get("reason"), "artifact_id": row.get("artifact_id")})
    recorded_terminal_ids = {row.get("artifact_id") for row in statuses}
    for item in [*training_runs, *evaluation_runs, *result_runs]:
        if item.manifest.get("status") != "complete" and item.manifest["artifact_id"] not in recorded_terminal_ids:
            statuses.append({"candidate_key": item.manifest.get("context", {}).get("candidate_key"),
                             "stage": item.manifest.get("stage"), "status": item.manifest.get("status"),
                             "reason": item.manifest.get("reason"), "artifact_id": item.manifest["artifact_id"]})
    evidence = []
    for item in evidence_runs:
        if item.manifest.get("status") == "complete":
            payload = item.read_json("evidence.json")
            evidence.append({"evidence_type": payload.get("evidence_type"), "status": payload.get("status"),
                             "scope": payload.get("scope"), "independent": payload.get("independent"),
                             "prepared_artifact_id": payload.get("prepared_artifact_id"),
                             "evidence_id": payload.get("evidence_id"),
                             "reference_id": payload.get("reference", {}).get("reference_id"),
                             "producer": payload.get("reference", {}).get("producer"),
                             "findings": payload.get("findings"), "limitations": payload.get("limitations"),
                             "artifact_id": item.manifest["artifact_id"]})
        else:
            evidence.append({"evidence_type": item.manifest.get("context", {}).get("evidence_type"),
                             "status": item.manifest.get("status"), "scope": None, "independent": None,
                             "prepared_artifact_id": item.manifest.get("context", {}).get("prepared_artifact_id"),
                             "evidence_id": None, "reference_id": None, "producer": None, "findings": [],
                             "limitations": [item.manifest.get("reason")],
                             "artifact_id": item.manifest["artifact_id"]})

    tables = {
        "models.csv": (models, ["candidate_key","candidate","subset","seed","representation","input_count","ordered_inputs","status","validation_absolute_weight_auc","selected_epoch","checkpoint_rule","target_lambda","effective_lambda","model_id","artifact_id","protocol_id","prepared_artifact_id","metric_role","weight_measure","selection_note"]),
        "training_history.csv": (history, ["candidate_key","seed","subset","epoch","loss","classification_loss","adversary_loss","effective_lambda","validation_absolute_weight_auc","absolute_weight_mass_ks","mass_bin_acceptance","is_selected_epoch","detail_status","model_id"]),
        "model_mass_diagnostics.csv": (mass, ["candidate_key","seed","subset","mass_bin_index","mass_low","mass_high","background_acceptance","absolute_weight_mass_ks","working_point","threshold","threshold_source","evaluation_source","model_id"]),
        "feature_metrics.csv": (feature_metrics, ["candidate_key","subset","seed","raw_validation_auc","delta_auc_vs_m0c","width68","relative_w68_improvement_vs_m0c","selected_epoch","model_status","inference_status","comparison_cohort_id"]),
        "feature_summary.csv": (feature_summary, ["subset","status","auc_status","inference_status","auc_complete_seed_count","inference_complete_seed_count","median_auc","min_auc","max_auc","median_delta_auc_vs_m0c","min_delta_auc_vs_m0c","max_delta_auc_vs_m0c","median_width68","min_width68","max_width68","median_relative_w68_improvement","min_relative_w68_improvement","max_relative_w68_improvement"]),
        "calibration_summary.csv": (calibration, ["candidate_key","candidate_id","seed","subset","transform","status","model_id","mapping_id","threshold_id","source_role","final_slice_count","merge_count","merge_history","min_effective_count","min_cancellation_ratio","max_correction_chi2","detail_status"]),
        "calibration_slices.csv": (slices, ["candidate_key","seed","mapping_id","slice_index","mass_low","mass_high","mass_center","effective_count","cancellation_ratio","total_yield","correction_chi2","raw_negative_bin_count","fitted_zero_bin_count","sum_absolute_correction","max_absolute_correction"]),
        "calibration_bins.csv": (calibration_bins, ["candidate_key","seed","mapping_id","slice_index","score_bin_index","score_low","score_high","raw_yield","fitted_yield","variance","correction","probability"]),
        "template_bins.csv": (template_bins, ["candidate_key","candidate_id","seed","mapping_id","process","is_signal","category","flat_bin_index","mass_low","mass_high","signed_yield","variance","sum_abs_weight","sum_positive_weight","sum_negative_weight","group_count","neff_signed","neff_abs","rho","bin_status","active_bin","template_artifact_id"]),
        "template_covariance.csv": (covariance, ["candidate_key","process","left_flat_bin","right_flat_bin","covariance","sparse_nonzero_only","template_artifact_id"]),
        "inference_intervals.csv": (intervals, ["candidate_key","candidate_id","seed","layer","expectation_kind","procedure","injected_mu","confidence_level","muhat","lower","upper","width","lower_at_boundary","upper_search_bound","status","mapping_id","comparison_cohort_id","artifact_id"]),
        "toy_fits.csv": (toys, ["candidate_key","seed","toy_index","injected_mu","confidence_level","muhat","lower","upper","width","lower_at_boundary","upper_search_bound","status","pairing_id","auxiliary_generation","expectation_kind","artifact_id"]),
        "coverage_summary.csv": (coverage, ["candidate_key","seed","confidence_level","injected_mu","expectation_kind","procedure","pairing_id","status","budget","valid_fits","failed_fits","failure_rate","covered","coverage","success_and_coverage_fraction","wilson_interval_success_and_coverage","binomial_standard_error","interpretation","artifact_id"]),
        "fit_diagnostics.csv": (diagnostics, ["candidate_key","seed","confidence_level","injected_mu","expectation_kind","procedure","pairing_id","status","budget","valid_fits","failed_fits","failure_rate","bias_valid_fits","bias_standard_error","pull_mean","pull_std","pull_definition","mean_width","median_width","width_q16","width_q84","lower_boundary_count","artifact_id"]),
        "paired_comparisons.csv": (paired, ["candidate_key","comparison","confidence_level","status","difference","standard_error","pairing_id","pairs","artifact_id"]),
        "bootstrap_replicas.csv": (bootstraps, ["artifact_id","bootstrap_id","replica","status","reason","median_relative_improvement","paired_seeds"]),
        "procedure_replicas.csv": (procedures, ["artifact_id","procedure","replica","status","reason","mapping_id","planned_outer_replicas","successful_outer_replicas","inner_toys","candidate_key","seed","confidence_level","coverage","valid_fits","failed_fits","bias","pull_mean","pull_std","mean_width","median_width","coverage_std_across_replicas","bias_std_across_replicas","mean_width_std_across_replicas"]),
        "stress_results.csv": (stress, ["candidate_key","seed","status","kind","direction","mode","source","reference_mapping_id","injected_mu","confidence_level","coverage","bias","pull_mean","pull_std","mean_width","median_width","coverage_change_vs_nominal","bias_change_vs_nominal","mean_width_change_vs_nominal","nominal_status","artifact_id"]),
        "feature_attribution.csv": (attribution, ["seed","group","contribution","family_id","value_function","unit","efficiency_residual","status"]),
        "feature_interactions.csv": (interactions, ["seed","family_id","pair","conditioning_subset","second_difference"]),
        "run_statuses.csv": (statuses, ["candidate_key","stage","status","reason","artifact_id"]),
        "evidence_status.csv": (evidence, ["evidence_type","status","scope","independent","prepared_artifact_id","evidence_id","reference_id","producer","findings","limitations","artifact_id"]),
    }
    for filename, (rows, fields) in tables.items():
        _write_csv(run, filename, rows, fields)
    jsonl_name = "analysis_records.jsonl"
    jsonl_path = run.path / jsonl_name
    with jsonl_path.open("x", encoding="utf-8", newline="\n") as stream:
        for table_name, (rows, _) in tables.items():
            for row in rows:
                stream.write(_json({"table": table_name, "row": row}) + "\n")
    run.register_file(jsonl_name)
    units = {"validation_absolute_weight_auc": "dimensionless", "raw_validation_auc": "dimensionless",
             "delta_auc_vs_m0c": "absolute AUC difference", "width68": "mu", "muhat": "mu",
             "lower": "mu", "upper": "mu", "width": "mu", "bias": "mu",
             "bias_valid_fits": "mu", "mean_width": "mu", "median_width": "mu",
             "mass_low": "GeV", "mass_high": "GeV", "mass_center": "GeV"}
    formulas = {"delta_auc_vs_m0c": "AUC(subset,seed)-AUC(M0c,seed)",
                "relative_w68_improvement_vs_m0c": "1-W68(subset,seed)/W68(M0c,seed)",
                "width": "upper-lower", "bias": "mean(muhat-injected_mu)",
                "pull_mean": "mean((muhat-injected_mu)/(interval_width/2))",
                "coverage_change_vs_nominal": "coverage(stress)-coverage(nominal_assessment)",
                "mean_width_change_vs_nominal": "mean_width(stress)-mean_width(nominal_assessment)"}
    def field_definition(field, rows):
        values = [row.get(field) for row in rows if row.get(field) is not None]
        sample = values[0] if values else None
        field_type = ("json" if isinstance(sample, (dict, list)) else "boolean" if isinstance(sample, bool)
                      else "integer" if isinstance(sample, int) else "number" if isinstance(sample, float)
                      else "string" if sample is not None else "unknown_not_recorded")
        return {"type": field_type, "unit": units.get(field, "dimensionless_or_not_applicable"),
                "formula": formulas.get(field), "evaluation_role": "derived_report_export",
                "missing_semantics": "not_recorded_or_not_applicable; inspect row status fields"}
    dictionary = {"schema_version": EXPORT_VERSION, "missing_value": "empty CSV field; consult status/detail_status",
                  "weight_semantics": {"auc": "absolute physical weight on validation role",
                                       "template_yield": "signed physical yield"},
                  "tables": {name: {"columns": fields, "rows": len(rows),
                                    "fields": {field: field_definition(field, rows) for field in fields}}
                             for name, (rows, fields) in tables.items()},
                  "notes": {"template_covariance.csv": "sparse export containing nonzero entries only",
                            "analysis_records.jsonl": "full-precision JSONL mirror of every CSV logical row",
                            "raw_validation_auc": "checkpoint selected using the same validation AUC; diagnostic, not independent evaluation"}}
    run.write_json("data_dictionary.json", dictionary)
    provenance = {"schema_version": EXPORT_VERSION, "dataset": run.manifest["dataset"],
                  "protocol_sha256": run.manifest["protocol_sha256"],
                  "prepared_artifact_id": report.get("prepared_artifact_id"),
                  "primary_comparison_cohort_id": report.get("primary_comparison_cohort_id"),
                  "evaluation_plan": report.get("evaluation_plan"),
                  "training_artifact_ids": [item.manifest["artifact_id"] for item in training_runs],
                  "evaluation_artifact_ids": [item.manifest["artifact_id"] for item in evaluation_runs],
                  "result_artifact_ids": [item.manifest["artifact_id"] for item in result_runs],
                  "evidence_artifact_ids": [item.manifest["artifact_id"] for item in evidence_runs],
                  "template_grids": {key: value.get("mass_edges") for key, value in grids.items()},
                  "environment": run.manifest.get("software"),
                  "upstreams": run.manifest.get("upstreams", []),
                  "export_file_receipts": {name: run.manifest.get("files", {}).get(name)
                                           for name in [*tables, jsonl_name]},
                  "export_id": None}
    provenance["export_id"] = digest_json({key: value for key, value in provenance.items() if key != "export_id"})
    run.write_json("provenance.json", provenance)
    return {"schema_version": EXPORT_VERSION, "tables": {name: len(rows) for name, (rows, _) in tables.items()},
            "provenance_id": provenance["export_id"], "result_records": records,
            "feature_auc_summary": feature_summary}
