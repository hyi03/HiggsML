import copy

import pandas as pd
import pytest

from higgsml.errors import ResearchStateError
from higgsml.inference import bootstrap


def population(role):
    return pd.DataFrame([{"role": role, "event_group_id": f"{role}-{group}",
                          "event_id": f"{role}-{group}-{row}", "m4l": 125.0,
                          "physical_weight": (-1.0 if row else 2.0), "yield_weight": 1.0}
                         for group in range(4) for row in range(2)])


def inputs():
    keys = [f"M{candidate}:{seed}" for candidate in (4, 5) for seed in range(42, 47)]
    bundles = {key: {"transform": "physical", "model": {"key": key}, "model_id": key,
                     "mapping_id": f"old-{key}"} for key in keys}
    grid = {"mass_edges": [105.0, 140.0], "templates": {key: {} for key in keys}}
    return grid, bundles


def patch_science(monkeypatch, *, fail_once=False):
    calls = {"asimov": 0}
    monkeypatch.setattr(bootstrap, "predict_discriminant", lambda model, frame: [0.5] * len(frame))
    monkeypatch.setattr(bootstrap, "fit_calibration", lambda frame, scores, protocol, target, model_id:
                        {"mapping_id": f"map-{model_id}"})
    monkeypatch.setattr(bootstrap, "apply_calibration", lambda mapping, mass, scores, model_id: scores)
    monkeypatch.setattr(bootstrap, "fit_thresholds", lambda *args, **kwargs: {"threshold_id": "threshold"})
    monkeypatch.setattr(bootstrap, "assign_categories", lambda *args, **kwargs: [0] * len(args[1]))
    monkeypatch.setattr(bootstrap, "build_templates", lambda frame, **kwargs:
                        {"status": "valid", "candidate_id": kwargs["candidate_id"], "mapping_id": kwargs["mapping_id"]})
    monkeypatch.setattr(bootstrap, "build_model", lambda *args, **kwargs: object())

    def asimov(template, **kwargs):
        calls["asimov"] += 1
        if fail_once and calls["asimov"] == 1:
            raise ResearchStateError("synthetic failure", status="fit_failed")
        width = 2.0 if template["candidate_id"] == "M4" else 1.8
        return {"results": [{"intervals": [{"status": "valid", "width": width}]}]}
    monkeypatch.setattr(bootstrap, "run_asimov", asimov)


def test_group_bootstrap_is_deterministic_and_paired(monkeypatch):
    patch_science(monkeypatch)
    grid, bundles = inputs()
    kwargs = dict(replicas=2, seed=71, t1_validation={"status": "validated"})
    first = bootstrap.primary_mc_bootstrap(copy.deepcopy(grid), bundles, population("calibration"),
                                           population("template"), {"templates": {}, "inference": {"mu_bounds": [0, 5]}}, **kwargs)
    second = bootstrap.primary_mc_bootstrap(copy.deepcopy(grid), bundles, population("calibration"),
                                            population("template"), {"templates": {}, "inference": {"mu_bounds": [0, 5]}}, **kwargs)
    assert first == second
    assert first["summary"]["status"] == "valid"
    assert first["summary"]["interval68"] is not None
    assert first["replicas"][0]["median_relative_improvement"] == pytest.approx(.1)
    assert sum(first["replicas"][0]["calibration_group_multiplicities"].values()) == 4


def test_bootstrap_failure_keeps_denominator_and_suppresses_intervals(monkeypatch):
    patch_science(monkeypatch, fail_once=True)
    grid, bundles = inputs()
    result = bootstrap.primary_mc_bootstrap(grid, bundles, population("calibration"), population("template"),
        {"templates": {}, "inference": {"mu_bounds": [0, 5]}}, replicas=2, seed=72,
        t1_validation={"status": "validated"})
    assert result["summary"]["planned_replicas"] == 2
    assert result["summary"]["failed_replicas"] == 1
    assert result["summary"]["interval68"] is result["summary"]["interval95"] is None
