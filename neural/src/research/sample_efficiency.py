"""Deterministic paired aggregation and reporting for verified M4 batches."""
from __future__ import annotations

from dataclasses import dataclass
import csv
from io import StringIO
import math
import os
from pathlib import Path

import numpy as np

from .artifacts import LoadedRun, ResearchRun, digest_json, read_run
from .data import load_research_data
from .errors import ResearchError
from .protocol import canonical
from .sample_efficiency_training import (load_bound_prepared_role, predict_subset_discriminant,
                                           read_subset_discriminant_run)
from .sample_efficiency_workflow import INFERENCE_STAGE, read_learning_curve_batch
from .training_subsets import load_training_subset, read_training_subsets


REPORT_STAGE = "sample-efficiency-report"
CONTRACT_SCHEMA = "h4l-sample-efficiency-report-contract-v1"
RECORD_SCHEMA = "h4l-sample-efficiency-record-v1"
SUMMARY_SCHEMA = "h4l-sample-efficiency-summary-v1"
BASELINE = "engineered19"
METRICS = ("w68", "validation_absolute_weight_auc", "delta_w68", "relative_w68")
CSV_FIELDS = ("curve_row_id", "representation_id", "sample_fraction_target",
              "actual_train_group_count", "planned_count", "complete_count",
              "terminal_count", "failure_rate", "pair_eligible_count", "paired_count",
              "baseline_missing_count", "target_missing_count", "pair_completeness",
              "mean_w68", "mean_auc", "mean_delta_w68", "mean_relative_w68",
              "network_w68_status", "network_w68_std_mean", "subset_w68_status",
              "subset_w68_std", "network_auc_status", "network_auc_std_mean",
              "network_delta_status", "network_delta_std_mean", "network_relative_status",
              "network_relative_std_mean", "subset_auc_status", "subset_auc_std",
              "subset_delta_status", "subset_delta_std", "subset_relative_status",
              "subset_relative_std", "evaluation_auc_status", "evaluation_auc_requested",
              "evaluation_auc_valid", "evaluation_resample_plan_id", "evaluation_auc_mean",
              "evaluation_auc_std", "evaluation_auc_q16", "evaluation_auc_q84",
              "calibration_status", "template_finite_mc_status")


def _fail(message, status="training_subset_binding_mismatch"):
    raise ResearchError(message, status=status)


def _keys(value, expected, name):
    if type(value) is not dict or set(value) != set(expected):
        _fail(f"invalid {name} schema")


def _finite_json(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            _fail("nonfinite report payload")
        return
    if type(value) is list:
        for item in value:
            _finite_json(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _finite_json(item)
        return
    _fail("invalid report payload type")


def _finite(value):
    return value is None or (type(value) in (int, float) and math.isfinite(value))


def _mean(values):
    if any(not _finite(value) for value in values):
        _fail("nonfinite value in report statistic")
    result = float(np.mean(values)) if values else None
    if not _finite(result):
        _fail("nonfinite report mean")
    return result


def _stats(values, *, requested=None, partial=False):
    if any(not _finite(value) for value in values):
        _fail("nonfinite value in report statistic")
    values = [float(value) for value in values]
    count = len(values)
    if count == 0:
        status = "not_estimated"
        mean = std = q16 = q84 = None
    else:
        status = ("estimated" if count >= 2 and not partial
                  and (requested is None or count == requested) else "partially_estimated")
        mean = float(np.mean(values))
        std = float(np.std(values, ddof=1)) if count >= 2 else None
        q16, q84 = (float(value) for value in np.quantile(values, (0.16, 0.84), method="linear"))
    if any(not _finite(value) for value in (mean, std, q16, q84)):
        _fail("nonfinite report statistic")
    return {"status": status, "used_count": count, "mean": mean, "std": std,
            "quantile_16": q16, "quantile_84": q84}


def weighted_auc(labels, scores, weights):
    """Versioned weighted Mann-Whitney AUC with half credit for score ties."""
    labels = np.asarray(labels)
    scores = np.asarray(scores, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if (labels.ndim != 1 or scores.shape != labels.shape or weights.shape != labels.shape
            or not np.isfinite(scores).all() or not np.isfinite(weights).all()
            or (weights < 0).any() or not set(np.unique(labels)).issubset({0, 1})):
        _fail("invalid weighted AUC inputs")
    with np.errstate(over="ignore", invalid="ignore"):
        positive = float(weights[labels == 1].sum())
        negative = float(weights[labels == 0].sum())
    if not math.isfinite(positive) or not math.isfinite(negative):
        _fail("nonfinite weighted AUC totals")
    if positive <= 0 or negative <= 0:
        return None
    order = np.argsort(scores, kind="mergesort")
    labels, scores, weights = labels[order], scores[order], weights[order]
    numerator = 0.0
    negative_before = 0.0
    start = 0
    while start < len(scores):
        stop = start + 1
        while stop < len(scores) and scores[stop] == scores[start]:
            stop += 1
        tied_positive = float(weights[start:stop][labels[start:stop] == 1].sum())
        tied_negative = float(weights[start:stop][labels[start:stop] == 0].sum())
        numerator += tied_positive * (negative_before + 0.5 * tied_negative)
        if not math.isfinite(numerator):
            _fail("nonfinite weighted AUC accumulation")
        negative_before += tied_negative
        start = stop
    denominator = positive * negative
    result = numerator / denominator if math.isfinite(denominator) and denominator > 0 else None
    if result is None or not math.isfinite(result):
        _fail("nonfinite weighted AUC result")
    return float(result)


def _resample_plan(validation, overlay):
    groups = sorted(set(validation.event_group_id), key=lambda value: canonical(value))
    if not groups:
        _fail("validation role has no event groups")
    config = overlay["evaluation_uncertainty"]
    generator = np.random.Generator(np.random.PCG64(config["seed"]))
    multiplicities = []
    for _ in range(config["replicates"]):
        counts = np.bincount(generator.integers(0, len(groups), size=len(groups), endpoint=False),
                             minlength=len(groups)).tolist()
        multiplicities.append(counts)
    payload = {"algorithm": "canonical-groups-pcg64-integers-v1",
               "group_digest": digest_json(groups), "group_count": len(groups),
               "seed": config["seed"], "replicates": config["replicates"],
               "multiplicities": multiplicities}
    return groups, payload, digest_json(payload)


def _bootstrap(validation, scores, groups, plan, plan_id):
    group_index = {group: index for index, group in enumerate(groups)}
    row_groups = np.asarray([group_index[group] for group in validation.event_group_id], dtype=int)
    base_weights = np.abs(validation.physical_weight.to_numpy(dtype=float))
    labels = validation.label.to_numpy(dtype=int)
    replicate_values = []
    for counts in plan["multiplicities"]:
        value = weighted_auc(labels, scores, base_weights * np.asarray(counts)[row_groups])
        replicate_values.append(value)
    values = [value for value in replicate_values if value is not None]
    result = _stats(values, requested=plan["replicates"], partial=len(values) != plan["replicates"])
    result.pop("used_count")
    return {"method": "paired_event_group_bootstrap_v1",
            "unit": "event_group_id", "seed": plan["seed"],
            "requested_replicates": plan["replicates"], "valid_replicates": len(values),
            "resample_plan_id": plan_id, **result}, replicate_values


def _w68(result):
    try:
        intervals = result["results"][0]["intervals"]
        matches = [row for row in intervals if row["confidence"] == 0.68]
        value = matches[0]["width"] if len(matches) == 1 else None
    except (KeyError, IndexError, TypeError):
        value = None
    if not _finite(value) or value is None:
        _fail("invalid M4 W68 pointer")
    return float(value)


def _uncertainty(records, metric, *, layer, full=False):
    by_draw = {}
    for record in records:
        value = record.get(metric)
        if record["cell_status"] == "complete" and value is not None:
            by_draw.setdefault(record["sample_draw_seed_or_full"], {})[record["network_seed"]] = value
    if layer == "network":
        deviations = [float(np.std(list(seed_values.values()), ddof=1))
                      for seed_values in by_draw.values() if len(seed_values) >= 2]
        return {"status": "estimated" if deviations else "not_estimated",
                "eligible_draw_count": len(by_draw), "used_draw_count": len(deviations),
                "std_mean": _mean(deviations)}
    if full or len(by_draw) < 2:
        return {"status": "not_estimated", "eligible_draw_count": len(by_draw),
                "common_seed_count": 0, "std_across_draw_means": None}
    common = set.intersection(*(set(values) for values in by_draw.values()))
    if len(common) < 2:
        return {"status": "not_estimated", "eligible_draw_count": len(by_draw),
                "common_seed_count": len(common), "std_across_draw_means": None}
    draw_means = [float(np.mean([values[seed] for seed in sorted(common)]))
                  for values in by_draw.values()]
    value = float(np.std(draw_means, ddof=1))
    return {"status": "estimated", "eligible_draw_count": len(by_draw),
            "common_seed_count": len(common), "std_across_draw_means": value}


def _build_summary(records, bootstrap_values, contract, overlay):
    grouped = {}
    for record in records:
        key = (record["representation_id"], record["sample_fraction_target"],
               record["actual_train_group_count"])
        grouped.setdefault(key, []).append(record)
    rows = []
    for key in sorted(grouped, key=canonical):
        representation, fraction, actual = key
        members = grouped[key]
        complete = [row for row in members if row["cell_status"] == "complete"]
        paired = [row for row in members if row["pair_status"] == "paired"]
        baseline_missing = sum(row["pair_status"] == "paired_cell_missing"
                               and row["cell_status"] == "complete" for row in members)
        target_missing = sum(row["cell_status"] != "complete" for row in members)
        counts = {"planned_count": len(members), "complete_count": len(complete),
                  "terminal_count": len(members) - len(complete),
                  "pair_eligible_count": len(members), "paired_count": len(paired),
                  "baseline_missing_count": baseline_missing,
                  "target_missing_count": target_missing}
        means = {metric: _mean([row[metric] for row in (paired if metric in {"delta_w68", "relative_w68"} else complete)
                                if row[metric] is not None]) for metric in METRICS}
        network = {metric: _uncertainty(members, metric, layer="network") for metric in METRICS}
        subset = {metric: _uncertainty(members, metric, layer="subset", full=fraction == 1.0)
                  for metric in METRICS}
        replicate_rows = [bootstrap_values[row["experiment_cell_id"]] for row in complete]
        aggregate = []
        if replicate_rows:
            for index in range(contract["evaluation_resample_plan"]["replicates"]):
                values = [row[index] for row in replicate_rows
                          if index < len(row) and row[index] is not None]
                if len(values) == len(replicate_rows):
                    aggregate.append(float(np.mean(values)))
        requested = contract["evaluation_resample_plan"]["replicates"]
        aggregate_stats = _stats(aggregate, requested=requested, partial=len(aggregate) != requested)
        aggregate_stats.pop("used_count")
        evaluation = {"w68": {"status": "not_estimated", "requested_replicates": requested,
                      "valid_replicates": 0, "resample_plan_id": contract["evaluation_resample_plan"]["resample_plan_id"],
                      "mean": None, "std": None, "quantile_16": None, "quantile_84": None},
                      "validation_absolute_weight_auc": {"requested_replicates": requested,
                      "valid_replicates": len(aggregate),
                      "resample_plan_id": contract["evaluation_resample_plan"]["resample_plan_id"],
                      **aggregate_stats}}
        calibration = {"status": "not_estimated", "method": "not_estimated"}
        template_mc = {"status": "propagated", "method": "propagated_by_shapesys_T1"}
        row = {"representation_id": representation, "sample_fraction_target": fraction,
               "actual_train_group_count": actual, "counts": counts, "means": means,
               "network_uncertainty": network, "subset_uncertainty": subset,
               "evaluation_uncertainty": evaluation,
               "calibration_uncertainty": calibration, "template_finite_mc": template_mc}
        row["curve_row_id"] = digest_json(row)
        rows.append(row)
    targets = _quality_targets(rows, overlay)
    panels = []
    for metric, label in (("w68", "W68 (model-self Asimov, mu=1)"),
                          ("relative_w68", "W68 / engineered19 W68")):
        series = []
        for representation in sorted({row["representation_id"] for row in rows}):
            selected = sorted((row for row in rows if row["representation_id"] == representation),
                              key=lambda row: row["actual_train_group_count"])
            series.append({"representation_id": representation,
                "points": [{"curve_row_id": row["curve_row_id"],
                            "x": row["actual_train_group_count"], "y": row["means"][metric],
                            "network_error": row["network_uncertainty"][metric]["std_mean"],
                            "network_status": row["network_uncertainty"][metric]["status"]}
                           for row in selected]})
        panels.append({"metric": metric, "x": "actual_train_group_count", "y_label": label,
                       "missing_values": "break_line", "error_layer": "network_seed_std_mean",
                       "series": series})
    plot_spec = {"schema_version": "h4l-sample-efficiency-plot-spec-v1",
                 "panels": panels, "x_label": "Actual train event-group count",
                 "claim_scope": "MC-only educational/technical demo"}
    plot_spec["plot_spec_id"] = digest_json(plot_spec)
    summary = {"schema_version": SUMMARY_SCHEMA,
               "report_contract_id": contract["report_contract_id"],
               "resample_plan_id": contract["evaluation_resample_plan"]["resample_plan_id"],
               "record_count": len(records), "curve_rows": rows,
               "quality_targets": targets, "plot_spec": plot_spec}
    summary["summary_id"] = digest_json(summary)
    return summary


def _validate_outputs(contract, records, summary):
    _keys(contract, {"schema_version", "batch_artifact_id", "scientific_batch_id",
        "execution_plan_id", "base_research_protocol_sha256",
        "sample_efficiency_protocol_sha256", "primary_metric", "pairing_keys",
        "evaluation_uncertainty", "calibration_uncertainty", "quality_target",
        "algorithms", "schemas", "evaluation_resample_plan", "report_contract_id"},
        "report contract")
    _keys(contract["evaluation_resample_plan"], {"algorithm", "group_digest", "group_count",
        "seed", "replicates", "resample_plan_id"}, "evaluation resample plan")
    if (contract["schema_version"] != CONTRACT_SCHEMA
            or contract["report_contract_id"] != digest_json({key: value for key, value in contract.items()
                                                                if key != "report_contract_id"})):
        _fail("report contract identity mismatch")
    record_keys = {"schema_version", "plan_index", "experiment_cell_id", "pairing_id",
        "representation_id", "sample_fraction_target", "sample_draw_seed_or_full",
        "network_seed", "architecture_variant", "training_subset_id",
        "actual_train_group_count", "cell_status", "terminal_stage", "status", "reason",
        "stage_artifact_ids", "w68", "validation_absolute_weight_auc",
        "evaluation_auc_bootstrap", "baseline_experiment_cell_id", "pair_status",
        "delta_w68", "relative_w68", "record_id"}
    bootstrap_keys = {"method", "unit", "seed", "requested_replicates", "valid_replicates",
        "resample_plan_id", "status", "mean", "std", "quantile_16", "quantile_84"}
    for index, record in enumerate(records):
        _keys(record, record_keys, "report record")
        if (record["schema_version"] != RECORD_SCHEMA or record["plan_index"] != index
                or record["record_id"] != digest_json({key: value for key, value in record.items()
                                                        if key != "record_id"})
                or record["pair_status"] not in {"paired", "paired_cell_missing"}):
            _fail("report record identity mismatch")
        if record["cell_status"] == "complete":
            _keys(record["evaluation_auc_bootstrap"], bootstrap_keys, "cell bootstrap")
        elif any(record[key] is not None for key in ("w68", "validation_absolute_weight_auc",
                                                      "evaluation_auc_bootstrap", "delta_w68", "relative_w68")):
            _fail("terminal report record publishes metrics")
    _keys(summary, {"schema_version", "report_contract_id", "resample_plan_id", "record_count",
                    "curve_rows", "quality_targets", "plot_spec", "summary_id"}, "report summary")
    if (summary["schema_version"] != SUMMARY_SCHEMA or summary["record_count"] != len(records)
            or summary["summary_id"] != digest_json({key: value for key, value in summary.items()
                                                      if key != "summary_id"})):
        _fail("report summary identity mismatch")
    curve_keys = {"representation_id", "sample_fraction_target", "actual_train_group_count",
        "counts", "means", "network_uncertainty", "subset_uncertainty",
        "evaluation_uncertainty", "calibration_uncertainty", "template_finite_mc",
        "curve_row_id"}
    for row in summary["curve_rows"]:
        _keys(row, curve_keys, "curve row")
        _keys(row["counts"], {"planned_count", "complete_count", "terminal_count",
            "pair_eligible_count", "paired_count", "baseline_missing_count",
            "target_missing_count"}, "curve counts")
        _keys(row["means"], METRICS, "curve means")
        for value in row["network_uncertainty"].values():
            _keys(value, {"status", "eligible_draw_count", "used_draw_count", "std_mean"},
                  "network uncertainty")
        for value in row["subset_uncertainty"].values():
            _keys(value, {"status", "eligible_draw_count", "common_seed_count",
                          "std_across_draw_means"}, "subset uncertainty")
        _keys(row["evaluation_uncertainty"], {"w68", "validation_absolute_weight_auc"},
              "evaluation uncertainty")
        for value in row["evaluation_uncertainty"].values():
            _keys(value, {"requested_replicates", "valid_replicates", "resample_plan_id",
                          "status", "mean", "std", "quantile_16", "quantile_84"},
                  "evaluation metric uncertainty")
        if row["curve_row_id"] != digest_json({key: value for key, value in row.items()
                                                if key != "curve_row_id"}):
            _fail("curve row identity mismatch")
    for target in summary["quality_targets"]:
        _keys(target, {"representation_id", "status", "target_w68", "estimated_group_count",
                       "left_curve_row_id", "right_curve_row_id"}, "quality target")
    plot = summary["plot_spec"]
    _keys(plot, {"schema_version", "panels", "x_label", "claim_scope", "plot_spec_id"},
          "plot spec")
    if plot["plot_spec_id"] != digest_json({key: value for key, value in plot.items()
                                             if key != "plot_spec_id"}):
        _fail("plot spec identity mismatch")
    for panel in plot["panels"]:
        _keys(panel, {"metric", "x", "y_label", "missing_values", "error_layer", "series"},
              "plot panel")
        for series in panel["series"]:
            _keys(series, {"representation_id", "points"}, "plot series")
            for point in series["points"]:
                _keys(point, {"curve_row_id", "x", "y", "network_error", "network_status"},
                      "plot point")
    _finite_json(contract); _finite_json(records); _finite_json(summary)


def _quality_targets(rows, overlay):
    target = overlay["quality_target"]
    results = []
    for representation in overlay["representations"]:
        selected = [row for row in rows if row["representation_id"] == representation]
        result = {"representation_id": representation,
                  "status": "disabled" if not target["enabled"] else None,
                  "target_w68": target["w68"], "estimated_group_count": None,
                  "left_curve_row_id": None, "right_curve_row_id": None}
        if not target["enabled"]:
            results.append(result); continue
        if any(row["counts"]["complete_count"] != row["counts"]["planned_count"] for row in selected):
            result["status"] = "not_estimated_incomplete"; results.append(result); continue
        counts = [row["actual_train_group_count"] for row in selected]
        if len(counts) != len(set(counts)):
            result["status"] = "ambiguous_duplicate_actual_count"; results.append(result); continue
        selected.sort(key=lambda row: row["actual_train_group_count"])
        exact = [row for row in selected if row["means"]["w68"] == target["w68"]]
        if exact:
            result.update(status="reached_exact", estimated_group_count=float(exact[0]["actual_train_group_count"]),
                          left_curve_row_id=exact[0]["curve_row_id"], right_curve_row_id=exact[0]["curve_row_id"])
        else:
            crossings = [(left, right) for left, right in zip(selected, selected[1:])
                         if left["means"]["w68"] > target["w68"] > right["means"]["w68"]]
            if crossings:
                left, right = crossings[0]
                n0, n1 = left["actual_train_group_count"], right["actual_train_group_count"]
                w0, w1 = left["means"]["w68"], right["means"]["w68"]
                estimate = n0 + (target["w68"] - w0) * (n1 - n0) / (w1 - w0)
                result.update(status="reached_interpolated", estimated_group_count=float(estimate),
                              left_curve_row_id=left["curve_row_id"], right_curve_row_id=right["curve_row_id"])
            else:
                result["status"] = "not_reached_within_study_range"
        results.append(result)
    return results


def _csv_bytes(summary):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in summary["curve_rows"]:
        counts, means = row["counts"], row["means"]
        network, subset = row["network_uncertainty"], row["subset_uncertainty"]
        evaluation = row["evaluation_uncertainty"]["validation_absolute_weight_auc"]
        writer.writerow({"curve_row_id": row["curve_row_id"], "representation_id": row["representation_id"],
            "sample_fraction_target": row["sample_fraction_target"],
            "actual_train_group_count": row["actual_train_group_count"], **counts,
            "failure_rate": counts["terminal_count"] / counts["planned_count"],
            "pair_completeness": counts["paired_count"] / counts["pair_eligible_count"],
            "mean_w68": means["w68"], "mean_auc": means["validation_absolute_weight_auc"],
            "mean_delta_w68": means["delta_w68"], "mean_relative_w68": means["relative_w68"],
            "network_w68_status": network["w68"]["status"],
            "network_w68_std_mean": network["w68"]["std_mean"],
            "subset_w68_status": subset["w68"]["status"],
            "subset_w68_std": subset["w68"]["std_across_draw_means"],
            "network_auc_status": network["validation_absolute_weight_auc"]["status"],
            "network_auc_std_mean": network["validation_absolute_weight_auc"]["std_mean"],
            "network_delta_status": network["delta_w68"]["status"],
            "network_delta_std_mean": network["delta_w68"]["std_mean"],
            "network_relative_status": network["relative_w68"]["status"],
            "network_relative_std_mean": network["relative_w68"]["std_mean"],
            "subset_auc_status": subset["validation_absolute_weight_auc"]["status"],
            "subset_auc_std": subset["validation_absolute_weight_auc"]["std_across_draw_means"],
            "subset_delta_status": subset["delta_w68"]["status"],
            "subset_delta_std": subset["delta_w68"]["std_across_draw_means"],
            "subset_relative_status": subset["relative_w68"]["status"],
            "subset_relative_std": subset["relative_w68"]["std_across_draw_means"],
            "evaluation_auc_status": evaluation["status"],
            "evaluation_auc_requested": evaluation["requested_replicates"],
            "evaluation_auc_valid": evaluation["valid_replicates"],
            "evaluation_resample_plan_id": evaluation["resample_plan_id"],
            "evaluation_auc_mean": evaluation["mean"], "evaluation_auc_std": evaluation["std"],
            "evaluation_auc_q16": evaluation["quantile_16"], "evaluation_auc_q84": evaluation["quantile_84"],
            "calibration_status": row["calibration_uncertainty"]["status"],
            "template_finite_mc_status": row["template_finite_mc"]["status"]})
    return stream.getvalue().encode("utf-8")


def _markdown_bytes(contract, summary, records):
    planned = len(records)
    complete = sum(record["cell_status"] == "complete" for record in records)
    failures = {}
    for record in records:
        if record["cell_status"] != "complete":
            key = (record["terminal_stage"], record["status"])
            failures[key] = failures.get(key, 0) + 1
    lines = ["# H4l sample-efficiency report", "",
             "Claim scope: MC-only educational/technical demo.", "",
             f"Report contract: `{contract['report_contract_id']}`", "",
             "## Completeness", "", f"- Planned: {planned}", f"- Complete: {complete}",
             f"- Scientific terminal: {planned - complete}", "", "## Failure table", ""]
    lines += ([f"- {stage} / {status}: {count}" for (stage, status), count in sorted(failures.items())]
              or ["- None"])
    lines += ["",
             "## Quality targets", ""]
    for item in summary["quality_targets"]:
        lines.append(f"- {item['representation_id']}: {item['status']}; estimate={item['estimated_group_count']}; "
                     f"left={item['left_curve_row_id']}; right={item['right_curve_row_id']}")
    lines += ["", "## Uncertainty layers", "",
              "Network-seed, training-subset, evaluation-event and template finite-MC layers are reported separately."]
    for row in summary["curve_rows"]:
        lines.append(f"- {row['curve_row_id']}: network={row['network_uncertainty']['w68']['status']}; "
                     f"subset={row['subset_uncertainty']['w68']['status']}; "
                     f"evaluation_auc={row['evaluation_uncertainty']['validation_absolute_weight_auc']['status']}; "
                     f"calibration={row['calibration_uncertainty']['status']}; "
                     f"template={row['template_finite_mc']['status']}")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def _plot(path, summary):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    figure = Figure(figsize=(9, 4))
    FigureCanvasAgg(figure)
    axes = figure.subplots(1, 2)
    for axis, panel in zip(axes, summary["plot_spec"]["panels"]):
        for series in panel["series"]:
            x = [point["x"] for point in series["points"]]
            y = [np.nan if point["y"] is None else point["y"] for point in series["points"]]
            error = [0.0 if point["network_error"] is None else point["network_error"]
                     for point in series["points"]]
            axis.errorbar(x, y, yerr=error, marker="o", label=series["representation_id"])
        axis.set_xlabel(summary["plot_spec"]["x_label"]); axis.set_ylabel(panel["y_label"]); axis.grid(alpha=0.25)
    axes[0].legend(fontsize=7)
    figure.tight_layout()
    figure.savefig(path, dpi=130, metadata={"Software": "HiggsML neural educational demo",
                                            "Description": summary["plot_spec"]["plot_spec_id"]})


def _build(batch_path, *, prepared, freeze_run, subset_run, gate_run, t1_validation, base, overlay):
    batch = read_learning_curve_batch(batch_path, prepared=prepared, freeze_run=freeze_run,
        subset_run=subset_run, gate_run=gate_run, t1_validation=t1_validation, base=base, overlay=overlay)
    plan = batch.plan
    m2_plan, _, _ = read_training_subsets(subset_run, prepared=prepared, freeze_run=freeze_run,
                                          base=base, overlay=overlay)
    subset_entries = {entry["subset_id"]: entry for entry in m2_plan["subsets"]}
    contract = {"schema_version": CONTRACT_SCHEMA,
        "batch_artifact_id": batch.run.manifest["artifact_id"],
        "scientific_batch_id": plan["scientific_batch_id"],
        "execution_plan_id": plan["execution_plan_id"],
        "base_research_protocol_sha256": base.digest,
        "sample_efficiency_protocol_sha256": overlay.digest,
        "primary_metric": overlay["primary_metric"], "pairing_keys": overlay["pairing_keys"],
        "evaluation_uncertainty": overlay["evaluation_uncertainty"],
        "calibration_uncertainty": overlay["calibration_uncertainty"],
        "quality_target": overlay["quality_target"],
        "algorithms": {"weighted_auc": "weighted-mann-whitney-half-ties-v1",
                       "rng": "numpy-pcg64-integers-v1", "std": "sample-ddof-1",
                       "quantile": "linear", "q_star": "observed-monotone-linear-no-extrapolation-v1"},
        "schemas": {"record": RECORD_SCHEMA, "summary": SUMMARY_SCHEMA,
                    "jsonl": "canonical-json-lines-no-header-v1",
                    "csv": "utf8-lf-rfc4180-python-roundtrip-v1"}}
    # Read complete model handles before validation, then use the public role loader.
    handles, w68_values = {}, {}
    selections = {}
    for cell, outcome in zip(plan["cells"], batch.ledger["cells"]):
        draw = overlay["sample_draw_seeds"][0] if cell["sample_draw_seed"] is None else cell["sample_draw_seed"]
        if (cell["training_subset_id"] not in subset_entries
                or subset_entries[cell["training_subset_id"]]["summary_total"]["group_count"] < 0):
            _fail("M2 subset summary is unavailable")
        if (outcome["stage_artifact_ids"]["model"] is not None
                and cell["training_subset_id"] not in selections):
            selections[cell["training_subset_id"]] = load_training_subset(subset_run, prepared=prepared,
                freeze_run=freeze_run, base=base, overlay=overlay,
                fraction=cell["sample_fraction_target"], draw=draw)
        if outcome["stage_artifact_ids"]["model"] is not None:
            handle = read_subset_discriminant_run(batch.path / cell["relative_paths"]["model"],
                prepared=prepared, freeze_run=freeze_run, subset_run=subset_run, base=base, overlay=overlay,
                fraction=cell["sample_fraction_target"], draw=draw,
                representation_id=cell["representation_id"], network_seed=cell["network_seed"])
            if handle.run.manifest["artifact_id"] != outcome["stage_artifact_ids"]["model"]:
                _fail("M4 ledger model changed before report use")
            handles[cell["experiment_cell_id"]] = handle
        if outcome["cell_status"] == "complete":
            inference = read_run(batch.path / cell["relative_paths"]["inference"],
                dataset=base["dataset"], protocol=base.to_dict(), stages=(INFERENCE_STAGE,))
            if inference.manifest["artifact_id"] != outcome["stage_artifact_ids"]["inference"]:
                _fail("M4 ledger inference changed before report use")
            w68_values[cell["experiment_cell_id"]] = _w68(inference.read_json("inference.json")["result"])
    complete_handles = [handles[cell["experiment_cell_id"]] for cell, outcome in zip(plan["cells"], batch.ledger["cells"])
                        if outcome["cell_status"] == "complete"]
    if complete_handles:
        validation = load_bound_prepared_role(prepared, complete_handles[0], base, "validation")
    else:
        verified_prepared = read_run(prepared.path if isinstance(prepared, LoadedRun) else prepared,
            dataset=base["dataset"], protocol=base.to_dict(), stages=("prepare",))
        validation = load_research_data(verified_prepared.file("events.jsonl"), base["dataset"], base)
        if validation.attrs.get("population_id") != plan["population_id"]:
            _fail("prepared population differs from batch")
        validation = validation.loc[validation.role == "validation"].copy()
        if validation.empty or set(validation.role) != {"validation"}:
            _fail("prepared run has no verified validation role")
    groups, resample_plan, resample_id = _resample_plan(validation, overlay)
    contract["evaluation_resample_plan"] = {key: value for key, value in resample_plan.items()
                                             if key != "multiplicities"}
    contract["evaluation_resample_plan"]["resample_plan_id"] = resample_id
    contract["report_contract_id"] = digest_json(contract)
    records, bootstrap_values = [], {}
    baseline_cells = {cell["pairing_id"]: (cell, outcome) for cell, outcome in zip(plan["cells"], batch.ledger["cells"])
                      if cell["representation_id"] == BASELINE}
    for cell, outcome in zip(plan["cells"], batch.ledger["cells"]):
        entry = subset_entries[cell["training_subset_id"]]
        actual = entry["summary_total"]["group_count"]
        w68 = auc = bootstrap = None
        if outcome["cell_status"] == "complete":
            handle = handles[cell["experiment_cell_id"]]
            if handle.model["training_summary_total"]["group_count"] != actual:
                _fail("model and M2 actual group count differ")
            w68 = w68_values[cell["experiment_cell_id"]]
            auc = float(handle.model["validation_absolute_weight_auc"])
            scores = predict_subset_discriminant(handle, validation)
            bootstrap, values = _bootstrap(validation, scores, groups, resample_plan, resample_id)
            bootstrap_values[cell["experiment_cell_id"]] = values
        baseline = baseline_cells.get(cell["pairing_id"])
        if baseline is None or baseline[0]["training_subset_id"] != cell["training_subset_id"]:
            _fail("M4 pairing identity is incomplete")
        baseline_cell, baseline_outcome = baseline
        pair_status = ("paired" if outcome["cell_status"] == "complete"
                       and baseline_outcome["cell_status"] == "complete" else "paired_cell_missing")
        delta = relative = None
        if pair_status == "paired":
            baseline_handle = handles[baseline_cell["experiment_cell_id"]]
            baseline_w68 = w68_values[baseline_cell["experiment_cell_id"]]
            if baseline_w68 <= 0:
                _fail("baseline W68 must be positive")
            delta, relative = float(w68 - baseline_w68), float(w68 / baseline_w68)
        record = {"schema_version": RECORD_SCHEMA, "plan_index": cell["plan_index"],
            "experiment_cell_id": cell["experiment_cell_id"], "pairing_id": cell["pairing_id"],
            "representation_id": cell["representation_id"],
            "sample_fraction_target": cell["sample_fraction_target"],
            "sample_draw_seed_or_full": cell["sample_draw_seed_or_full"],
            "network_seed": cell["network_seed"], "architecture_variant": cell["architecture_variant"],
            "training_subset_id": cell["training_subset_id"], "actual_train_group_count": actual,
            "cell_status": outcome["cell_status"], "terminal_stage": outcome["terminal_stage"],
            "status": outcome["status"], "reason": outcome["reason"],
            "stage_artifact_ids": outcome["stage_artifact_ids"], "w68": w68,
            "validation_absolute_weight_auc": auc, "evaluation_auc_bootstrap": bootstrap,
            "baseline_experiment_cell_id": baseline_cell["experiment_cell_id"],
            "pair_status": pair_status, "delta_w68": delta, "relative_w68": relative}
        record["record_id"] = digest_json(record)
        records.append(record)
    summary = _build_summary(records, bootstrap_values, contract, overlay)
    _validate_outputs(contract, records, summary)
    return batch, contract, records, summary, _csv_bytes(summary), _markdown_bytes(contract, summary, records)


@dataclass(frozen=True)
class LoadedSampleEfficiencyReport:
    path: Path
    run: LoadedRun
    contract: dict
    records: list
    summary: dict


def publish_sample_efficiency_report(output_dir, *, allowed_root, batch_path, prepared, freeze_run,
                                     subset_run, gate_run, t1_validation, base, overlay):
    root = Path(allowed_root).resolve(strict=True)
    requested = Path(output_dir)
    if (requested.parent.resolve(strict=True) != root or os.path.lexists(requested)
            or requested.name in {"", ".", ".."}):
        _fail("report target must be a fresh direct child")
    batch, contract, records, summary, csv_bytes, markdown = _build(batch_path,
        prepared=prepared, freeze_run=freeze_run, subset_run=subset_run, gate_run=gate_run,
        t1_validation=t1_validation, base=base, overlay=overlay)
    with ResearchRun(output_dir, allowed_root=allowed_root, stage=REPORT_STAGE,
                     dataset=base["dataset"], protocol=base.to_dict(), upstreams=[batch.run],
                     context={"report_contract_id": contract["report_contract_id"]}) as run:
        run.write_json("report-contract.json", contract)
        records_path = run.path / "sample-efficiency-records.jsonl"
        records_path.write_bytes(b"".join(canonical(record) + b"\n" for record in records)); run.register_file(records_path.name)
        run.write_json("sample-efficiency-summary.json", summary)
        csv_path = run.path / "sample-efficiency-curves.csv"; csv_path.write_bytes(csv_bytes); run.register_file(csv_path.name)
        markdown_path = run.path / "sample-efficiency-report.md"; markdown_path.write_bytes(markdown); run.register_file(markdown_path.name)
        plot_path = run.path / "sample-efficiency-curves.png"; _plot(plot_path, summary); run.register_file(plot_path.name)
    return read_sample_efficiency_report(output_dir, batch_path=batch_path, prepared=prepared,
        freeze_run=freeze_run, subset_run=subset_run, gate_run=gate_run,
        t1_validation=t1_validation, base=base, overlay=overlay)


def read_sample_efficiency_report(path, *, batch_path, prepared, freeze_run, subset_run,
                                  gate_run, t1_validation, base, overlay):
    run = read_run(path, dataset=base["dataset"], protocol=base.to_dict(), stages=(REPORT_STAGE,))
    expected_files = {"protocol.json", "report-contract.json", "sample-efficiency-records.jsonl",
        "sample-efficiency-summary.json", "sample-efficiency-curves.csv",
        "sample-efficiency-curves.png", "sample-efficiency-report.md"}
    if set(run.manifest.get("files", {})) != expected_files:
        _fail("report artifact file surface mismatch")
    for filename in expected_files:
        run.file(filename)
    batch, contract, records, summary, csv_bytes, markdown = _build(batch_path,
        prepared=prepared, freeze_run=freeze_run, subset_run=subset_run, gate_run=gate_run,
        t1_validation=t1_validation, base=base, overlay=overlay)
    expected_upstream = [{"artifact_id": batch.run.manifest["artifact_id"],
                          "stage": batch.run.manifest["stage"], "path": str(batch.run.path)}]
    expected = {"report-contract.json": canonical(contract) + b"\n",
        "sample-efficiency-records.jsonl": b"".join(canonical(record) + b"\n" for record in records),
        "sample-efficiency-summary.json": canonical(summary) + b"\n",
        "sample-efficiency-curves.csv": csv_bytes, "sample-efficiency-report.md": markdown}
    if run.manifest.get("upstreams") != expected_upstream:
        _fail("report upstream differs from verified M4 batch")
    for filename, payload in expected.items():
        if run.file(filename).read_bytes() != payload:
            _fail(f"report semantic replay differs: {filename}", status="learning_curve_incomplete")
    try:
        from PIL import Image
        with Image.open(run.file("sample-efficiency-curves.png")) as plot:
            if plot.info.get("Description") != summary["plot_spec"]["plot_spec_id"]:
                _fail("PNG is not bound to the verified plot spec")
    except (OSError, ValueError) as exc:
        raise ResearchError("invalid report PNG", status="training_subset_binding_mismatch") from exc
    return LoadedSampleEfficiencyReport(Path(path).resolve(), run, contract, records, summary)
