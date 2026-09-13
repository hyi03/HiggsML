"""Paired fixed-network MC bootstrap for the registered M5/M4 endpoint."""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd

from higgsml.artifacts import digest_json
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference.likelihood import build_model, run_asimov
from higgsml.inference.templates import build_templates
from higgsml.modeling.calibration import apply_calibration, assign_categories, fit_calibration, fit_thresholds
from higgsml.modeling.discriminants import predict_discriminant


def _resample_groups(frame, rng, label):
    groups = np.asarray(sorted(frame.event_group_id.astype(str).unique()))
    if not len(groups):
        raise ResearchError("bootstrap role has no physical event groups")
    counts = rng.multinomial(len(groups), np.full(len(groups), 1 / len(groups)))
    parts = []
    by_group = {str(key): value for key, value in frame.groupby(frame.event_group_id.astype(str), sort=False)}
    for group, count in zip(groups, counts):
        source = by_group[group]
        for copy_index in range(int(count)):
            part = source.copy()
            part["event_group_id"] = f"{label}:{group}:{copy_index}"
            parts.append(part)
    if not parts:
        raise ResearchStateError("bootstrap draw is empty", status="insufficient_statistics")
    return pd.concat(parts, ignore_index=True), {str(group): int(count) for group, count in zip(groups, counts)}


def primary_mc_bootstrap(grid, bundles, calibration, template, protocol, *, replicas, seed, t1_validation):
    if type(replicas) is not int or replicas < 1 or type(seed) is not int:
        raise ResearchError("MC bootstrap requires explicit positive replicas and integer seed")
    expected = {f"M{candidate}:{network_seed}" for candidate in (4, 5) for network_seed in range(42, 47)}
    if not expected <= set(bundles) or not expected <= set(grid.get("templates", {})):
        raise ResearchError("MC bootstrap requires all five paired M4/M5 models")
    if set(calibration.role) != {"calibration"} or set(template.role) != {"template"}:
        raise ResearchError("MC bootstrap roles are not isolated")
    if set(calibration.event_group_id) & set(template.event_group_id):
        raise ResearchError("calibration and template bootstrap groups overlap")
    rng = np.random.default_rng(seed)
    output = []
    for replica in range(replicas):
        try:
            calibration_draw, calibration_counts = _resample_groups(calibration, rng, f"c{replica}")
            template_draw, template_counts = _resample_groups(template, rng, f"t{replica}")
            widths = {}
            mappings = {}
            for key in sorted(expected):
                original = bundles[key]
                if original.get("transform") != "physical" or original.get("model") is None:
                    raise ResearchError("M4/M5 bootstrap requires physical-CDF neural bundles")
                bundle = deepcopy(original)
                raw_calibration_scores = predict_discriminant(bundle["model"], calibration_draw)
                mapping = fit_calibration(calibration_draw, raw_calibration_scores, protocol,
                                          target="physical", model_id=bundle["model_id"])
                calibrated = apply_calibration(mapping, calibration_draw.m4l.to_numpy(),
                                               raw_calibration_scores, model_id=bundle["model_id"])
                thresholds = fit_thresholds(calibration_draw, calibrated, protocol,
                                            model_id=bundle["model_id"], mapping_id=mapping["mapping_id"])
                raw_template_scores = predict_discriminant(bundle["model"], template_draw)
                template_scores = apply_calibration(mapping, template_draw.m4l.to_numpy(),
                                                    raw_template_scores, model_id=bundle["model_id"])
                categorized = template_draw.assign(category=assign_categories(
                    thresholds, template_scores, model_id=bundle["model_id"], mapping_id=mapping["mapping_id"]))
                built = build_templates(categorized, mass_edges=grid["mass_edges"],
                                        mapping_id=mapping["mapping_id"], candidate_id=key.split(":", 1)[0],
                                        thresholds=protocol["templates"], categories=(0, 1))
                if built["status"] != "valid":
                    raise ResearchStateError("bootstrap template fails frozen support", status="insufficient_statistics")
                built["seed"] = int(key.rsplit(":", 1)[1])
                built_model = build_model(built, layer="T1", t1_validation=t1_validation,
                                          mu_max=protocol["inference"]["mu_bounds"][1])
                asimov = run_asimov(built, protocol=protocol, layer="T1", t1_validation=t1_validation,
                                    injections=[1.0], _built_model=built_model)
                interval = asimov["results"][0]["intervals"][0]
                if interval.get("status") != "valid" or interval.get("width", 0) <= 0:
                    raise ResearchStateError("bootstrap interval is unavailable", status="fit_failed")
                widths[key] = float(interval["width"])
                mappings[key] = mapping["mapping_id"]
            paired = []
            for network_seed in range(42, 47):
                left, right = widths[f"M4:{network_seed}"], widths[f"M5:{network_seed}"]
                paired.append({"seed": network_seed, "M4_width68": left, "M5_width68": right,
                               "relative_improvement": 1 - right / left})
            output.append({"replica": replica, "status": "valid", "paired_seeds": paired,
                           "median_relative_improvement": float(np.median([row["relative_improvement"] for row in paired])),
                           "mapping_ids": mappings, "calibration_group_multiplicities": calibration_counts,
                           "template_group_multiplicities": template_counts})
        except ResearchStateError as error:
            output.append({"replica": replica, "status": error.status, "reason": str(error)})
    valid = [row for row in output if row["status"] == "valid"]
    values = np.asarray([row["median_relative_improvement"] for row in valid], float)
    complete = len(valid) == replicas
    summary = {"status": "valid" if complete else "bootstrap_incomplete", "planned_replicas": replicas,
               "valid_replicas": len(valid), "failed_replicas": replicas - len(valid),
               "interval_definition": "percentile_fixed_network_calibration_and_template_group_bootstrap",
               "median": float(np.median(values)) if len(values) else None,
               "interval68": np.quantile(values, [.16, .84]).tolist() if complete else None,
               "interval95": np.quantile(values, [.025, .975]).tolist() if complete else None}
    result = {"schema_version": "h4l-primary-mc-bootstrap-v1", "status": summary["status"],
              "seed": seed, "fixed": "trained_networks_train_and_validation_roles",
              "randomized": "paired_calibration_and_template_physical_event_groups",
              "mass_grid": list(grid["mass_edges"]), "replicas": output, "summary": summary}
    result["bootstrap_id"] = digest_json(result)
    return result
