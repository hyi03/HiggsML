from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

import src.full_training_evaluation as evaluation
from src.full_training_evaluation import (
    build_working_points,
    evaluate_full_training,
    weighted_pearson,
    weighted_retention_threshold,
)
from src.full_training_policy import load_training_policy


def test_weighted_retention_threshold_uses_background_absolute_weight():
    """A change to ascending selection would retain the wrong half of ZZ weight."""
    scores = np.array([0.1, 0.4, 0.8, 0.9])
    weights = np.array([1.0, 1.0, 1.0, 1.0])

    assert weighted_retention_threshold(scores, weights, 0.50) == pytest.approx(0.8)


def test_working_points_are_ordered_and_report_achieved_efficiency():
    """A threshold computed from signal or unordered targets must not define a point."""
    oof_frame = pd.DataFrame(
        {
            "label": [0, 0, 0, 0, 1, 1],
            "score": [0.1, 0.4, 0.8, 0.9, 0.7, 0.95],
            "physical_weight": [1.0, -1.0, 1.0, 1.0, 2.0, -1.0],
        }
    )

    points = build_working_points(
        oof_frame, {"loose": 0.5, "medium": 0.2, "tight": 0.1}
    )

    assert points["loose"]["threshold"] <= points["medium"]["threshold"]
    assert points["medium"]["threshold"] <= points["tight"]["threshold"]
    assert points["medium"]["target_background_efficiency"] == pytest.approx(0.2)


def test_weighted_retention_threshold_selects_every_score_tie():
    """A row-level cut through a tie would understate the retained ZZ efficiency."""
    scores = np.array([0.9, 0.8, 0.8, 0.1])
    weights = np.array([1.0, 2.0, 1.0, 6.0])

    threshold = weighted_retention_threshold(scores, weights, 0.30)

    assert threshold == pytest.approx(0.8)
    assert np.abs(weights[scores >= threshold]).sum() / np.abs(weights).sum() == pytest.approx(
        0.4
    )


@pytest.mark.parametrize(
    ("scores", "weights", "target", "message"),
    [
        ([], [], 0.5, "non-empty"),
        ([0.1], [1.0, 1.0], 0.5, "matching"),
        ([np.nan], [1.0], 0.5, "finite"),
        ([0.1], [0.0], 0.5, "positive"),
        ([0.1], [1.0], 1.0, "between"),
    ],
)
def test_weighted_retention_threshold_rejects_invalid_inputs(
    scores, weights, target, message
):
    """A missing finite/positive check would make a frozen cut undefined."""
    with pytest.raises(ValueError, match=message):
        weighted_retention_threshold(scores, weights, target)


def test_build_working_points_rejects_missing_zz_and_nonmonotonic_thresholds():
    """A working point cannot be frozen without OOF ZZ or ordered cuts."""
    signal_only = pd.DataFrame(
        {"label": [1], "score": [0.9], "physical_weight": [1.0]}
    )
    frame = pd.DataFrame(
        {
            "label": [0, 0, 0, 0, 1, 1],
            "score": [0.1, 0.4, 0.8, 0.9, 0.7, 0.95],
            "physical_weight": [1.0, -1.0, 1.0, 1.0, 2.0, -1.0],
        }
    )

    with pytest.raises(ValueError, match="ZZ"):
        build_working_points(signal_only, {"loose": 0.5})
    with pytest.raises(ValueError, match="monotonic"):
        build_working_points(frame, {"loose": 0.1, "medium": 0.5, "tight": 0.1})


def _scored_frame(scores: list[float], weights: list[float]) -> pd.DataFrame:
    labels = [0, 0, 0, 0, 1, 1, 1, 1]
    return pd.DataFrame(
        {
            "label": labels,
            "score": scores,
            "physical_weight": weights,
            "m4l": [106.0, 114.0, 132.0, 148.0, 118.0, 126.0, 138.0, 156.0],
        }
    )


@pytest.fixture
def policy():
    return load_training_policy("config/full_training.yaml")


def test_evaluation_uses_absolute_auc_signed_yields_and_sealed_oof_thresholds(policy):
    """Replacing an OOF threshold from final/test scores must change this report."""
    oof = _scored_frame(
        [0.10, 0.40, 0.80, 0.90, 0.20, 0.60, 0.70, 0.95],
        [1.0, -1.0, 1.0, 1.0, 1.0, -2.0, 1.0, 1.0],
    )
    final_development = _scored_frame(
        [0.60, 0.70, 0.79, 0.90, 0.20, 0.75, 0.85, 0.99],
        [1.0, -1.0, 1.0, 1.0, 1.0, -2.0, 1.0, 1.0],
    )
    test = _scored_frame(
        [0.95, 0.96, 0.97, 0.98, 0.01, 0.02, 0.03, 0.04],
        [1.0, -2.0, 1.0, -2.0, 1.0, -2.0, 1.0, 1.0],
    )
    points = build_working_points(oof, policy.working_points)

    report = evaluate_full_training(
        oof,
        final_development,
        test,
        points,
        policy,
        selection={"candidate": "depth2_child20", "final_tree_count": 4},
    )

    assert report["selection"] == {"candidate": "depth2_child20", "final_tree_count": 4}
    assert report["development_oof"]["weighted_auc"] == pytest.approx(0.55)
    assert report["working_points"]["loose"]["threshold"] == pytest.approx(
        points["loose"]["threshold"]
    )
    assert report["working_points"]["loose"]["final_development"][
        "achieved_background_efficiency"
    ] != pytest.approx(points["loose"]["achieved_background_efficiency"])
    assert report["working_points"]["loose"]["test"]["background"][
        "selected_signed_yield"
    ] == pytest.approx(-2.0)
    assert report["overfitting"]["warning_reasons"] == [
        "development_test_auc_gap",
        "signal_ks_distance",
        "background_ks_distance",
    ]
    assert report["overfitting"]["warning"] is True
    json.dumps(report, allow_nan=False)

    changed_test = test.assign(score=[0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08])
    changed_report = evaluate_full_training(
        oof,
        final_development,
        changed_test,
        points,
        policy,
        selection={"candidate": "depth2_child20", "final_tree_count": 4},
    )
    assert {
        name: point["threshold"] for name, point in changed_report["working_points"].items()
    } == {name: point["threshold"] for name, point in points.items()}


def test_weighted_pearson_uses_absolute_weights_and_handles_zero_variance():
    """Using signed weights would make the correlation denominator invalid."""
    assert weighted_pearson([0.0, 1.0], [0.0, 1.0], [1.0, -3.0]) == pytest.approx(1.0)
    assert weighted_pearson([1.0, 1.0], [0.0, 1.0], [1.0, 1.0]) == pytest.approx(0.0)


def test_evaluation_reports_finite_mc_mass_sculpting_diagnostics(policy):
    """Dropping a fixed-bin diagnostic would leave score–mass sculpting unchecked."""
    oof = _scored_frame(
        [0.10, 0.40, 0.80, 0.90, 0.20, 0.60, 0.70, 0.95],
        [1.0, -1.0, 1.0, 1.0, 1.0, -2.0, 1.0, 1.0],
    )
    test = _scored_frame(
        [0.05, 0.20, 0.85, 0.95, 0.80, 0.85, 0.90, 0.96],
        [1.0, -2.0, 1.0, -2.0, 1.0, -2.0, 1.0, 1.0],
    )
    points = build_working_points(oof, policy.working_points)

    report = evaluate_full_training(oof, oof, test, points, policy)

    assert report["selection"] == {"candidate": None, "final_tree_count": None}
    assert report["mass_sculpting"]["warning"] is True
    assert report["mass_sculpting"]["oof_zz"]["weighted_score_mass_correlation"] == pytest.approx(
        0.9593677930575893
    )
    loose = report["mass_sculpting"]["test_zz"]["working_points"]["loose"]
    assert loose["inclusive_to_selected_ks_distance"] == pytest.approx(0.5)
    assert "test_zz.loose.ks_distance" in report["mass_sculpting"]["warning_reasons"]
    assert len(loose["mass_bins"]) == len(policy.mass_bins_gev) - 1


def test_mass_sculpting_ks_warning_uses_strict_configured_boundary():
    """Using >= or ignoring finite distances would misclassify the warning boundary."""
    diagnostics = {
        "oof_zz": {
            "working_points": {
                "loose": {"inclusive_to_selected_ks_distance": 0.10},
                "medium": {"inclusive_to_selected_ks_distance": 0.1001},
            }
        },
        "test_zz": {
            "working_points": {
                "loose": {"inclusive_to_selected_ks_distance": None},
            }
        },
    }

    assert evaluation._excessive_mass_ks_reasons(diagnostics, 0.10) == [
        "oof_zz.medium.ks_distance"
    ]


def test_public_zz_mass_diagnostic_matches_validated_internal_result(policy):
    """Duplicating the private ZZ diagnostic in an ablation would allow drift."""
    frame = _scored_frame(
        [0.10, 0.40, 0.80, 0.90, 0.20, 0.60, 0.70, 0.95],
        [1.0, -1.0, 1.0, 1.0, 1.0, -2.0, 1.0, 1.0],
    )
    points = build_working_points(frame, policy.working_points)

    assert evaluation.zz_mass_diagnostics(frame, "score", points, policy) == evaluation._zz_mass_diagnostics(
        frame, "score", points, policy
    )


def test_mass_sculpting_warns_when_test_zz_has_no_events_at_a_working_point(policy):
    """A missing selected ZZ sample is unavailable evidence, not a clean result."""
    oof = _scored_frame(
        [0.10, 0.40, 0.80, 0.90, 0.20, 0.60, 0.70, 0.95],
        [1.0, -1.0, 1.0, 1.0, 1.0, -2.0, 1.0, 1.0],
    )
    test = _scored_frame(
        [0.01, 0.02, 0.03, 0.04, 0.80, 0.85, 0.90, 0.96],
        [1.0, -2.0, 1.0, -2.0, 1.0, -2.0, 1.0, 1.0],
    )
    points = build_working_points(oof, policy.working_points)

    report = evaluate_full_training(oof, oof, test, points, policy)

    assert report["mass_sculpting"]["test_zz"]["working_points"]["loose"][
        "inclusive_to_selected_ks_distance"
    ] is None
    assert report["mass_sculpting"]["warning_reasons"][:3] == [
        "test_zz.loose.empty_selected_zz",
        "test_zz.medium.empty_selected_zz",
        "test_zz.tight.empty_selected_zz",
    ]
    assert report["mass_sculpting"]["warning"] is True
    json.dumps(report, allow_nan=False)


def test_mass_sculpting_warns_and_stays_json_safe_for_overflowed_bin_values(policy):
    """Overflowed fixed-bin yields must not be hidden below a list boundary."""
    oof = _scored_frame(
        [0.10, 0.40, 0.80, 0.90, 0.20, 0.60, 0.70, 0.95],
        [1.0, -1.0, 1.0, 1.0, 1.0, -2.0, 1.0, 1.0],
    )
    overflow_test = _scored_frame(
        [0.05, 0.95, 0.96, 0.97, 0.80, 0.85, 0.90, 0.96],
        [np.finfo(float).max, np.finfo(float).max, 1.0, 1.0, 1.0, -2.0, 1.0, 1.0],
    )
    points = build_working_points(oof, policy.working_points)

    with np.errstate(over="ignore", invalid="ignore"):
        diagnostics = evaluation._mass_sculpting_metrics(
            oof, "score", overflow_test, "score", points, policy
        )

    assert (
        "test_zz.working_points.loose.mass_bins[1].inclusive_absolute_yield"
        in diagnostics["warning_reasons"]
    )
    assert diagnostics["test_zz"]["working_points"]["loose"]["mass_bins"][1][
        "inclusive_absolute_yield"
    ] is None
    json.dumps(diagnostics, allow_nan=False)
