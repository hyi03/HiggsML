from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config import InputBindingError
from src.training.config import load_training_protocol
from src.training.dataset import validate_development_frame
from src.training.folds import assign_folds
from src.training.qualification import (
    OOF_COLUMNS,
    frozen_working_point_metrics,
    qualification_reasons,
    select_candidate,
    validate_candidate_oof,
    weighted_auc,
    weighted_ks_distance,
    working_point_metrics,
)
from tests.training_fixtures import synthetic_development_frame


PROJECT = Path(__file__).resolve().parents[2]


def _protocol():
    return load_training_protocol(PROJECT / "config/adversarial_mlp_protocol_normal.yaml")


def test_weighted_auc_and_ks_match_small_hand_cases() -> None:
    assert weighted_auc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8], [1, 1, 1, 1]) == pytest.approx(0.75)
    assert weighted_ks_distance([1, 2], [1, 2], [1, 2], [1, 2]) == 0.0
    assert weighted_ks_distance([1, 2], [3, 4], [1, 1], [1, 1]) == 1.0


def test_working_point_preserves_full_score_tie() -> None:
    frame = pd.DataFrame(
        {
            "label": [0, 0, 0, 0, 1, 1],
            "score": [0.9, 0.8, 0.8, 0.2, 0.95, 0.1],
            "physical_weight": [1.0, 1.0, 2.0, 6.0, 1.0, 1.0],
            "m4l": [110.0, 120.0, 130.0, 140.0, 120.0, 130.0],
        }
    )
    point = working_point_metrics(frame, target=0.20)
    assert point["threshold"] == 0.8
    assert point["achieved_background_efficiency"] == 0.4
    assert point["signal_efficiency"] == 0.5


def test_working_point_uses_absolute_weights_at_exact_cumulative_boundary() -> None:
    positive = pd.DataFrame(
        {
            "label": [0, 0, 0, 1, 1],
            "score": [0.9, 0.8, 0.2, 0.95, 0.1],
            "physical_weight": [1.0, 1.0, 3.0, 1.0, 1.0],
            "m4l": [110.0, 120.0, 130.0, 120.0, 130.0],
        }
    )
    signed = positive.copy()
    signed.loc[1, "physical_weight"] = -1.0
    assert working_point_metrics(signed, target=0.40) == working_point_metrics(
        positive, target=0.40
    )
    point = working_point_metrics(signed, target=0.40)
    assert point["threshold"] == 0.8
    assert point["achieved_background_efficiency"] == 0.4


def test_working_point_all_background_scores_tied_selects_full_tie() -> None:
    frame = pd.DataFrame(
        {
            "label": [0, 0, 0, 1],
            "score": [0.5, 0.5, 0.5, 0.9],
            "physical_weight": [1.0, 2.0, 3.0, 1.0],
            "m4l": [110.0, 120.0, 130.0, 125.0],
        }
    )
    point = working_point_metrics(frame, target=0.20)
    assert point["threshold"] == 0.5
    assert point["achieved_background_efficiency"] == 1.0


def test_frozen_working_point_uses_exact_threshold_and_handles_empty_background() -> None:
    frame = pd.DataFrame(
        {
            "label": [0, 0, 1, 1],
            "score": [0.2, 0.3, 0.8, 0.9],
            "physical_weight": [-1.0, 3.0, -2.0, 2.0],
            "m4l": [110.0, 130.0, 120.0, 140.0],
        }
    )
    point = frozen_working_point_metrics(frame, target=0.20, threshold=0.5)
    assert point == {
        "threshold": 0.5,
        "target_background_efficiency": 0.2,
        "achieved_background_efficiency": 0.0,
        "signal_efficiency": 1.0,
        "ks": 1.0,
        "empty_selected_background": True,
    }


def test_qualification_boundaries_and_best_auc_relative_tie_break() -> None:
    protocol = _protocol()
    passing_points = {
        name: {
            "threshold": 0.5,
            "target_background_efficiency": target,
            "achieved_background_efficiency": 0.2,
            "signal_efficiency": 0.2000001,
            "ks": 0.10,
        }
        for name, target in protocol.working_points
    }
    assert qualification_reasons(0.80, passing_points, protocol) == []
    equal_efficiency = {name: dict(point) for name, point in passing_points.items()}
    equal_efficiency["loose"]["signal_efficiency"] = 0.2
    assert qualification_reasons(0.80, equal_efficiency, protocol) == [
        "loose_signal_efficiency_not_greater"
    ]

    candidates = []
    for target_lambda, auc in zip(protocol.target_lambdas, [0.9000000, 0.9000007, 0.9000011, 0.7, 0.6], strict=True):
        candidates.append({"target_lambda": target_lambda, "weighted_oof_auc": auc, "eligible": target_lambda < 0.2})
    assert select_candidate(candidates, protocol)["target_lambda"] == 0.05

    missing = {name: dict(point) for name, point in passing_points.items()}
    missing["loose"].pop("threshold")
    with pytest.raises(InputBindingError, match="qualification inputs changed"):
        qualification_reasons(0.80, missing, protocol)
    extra = {name: dict(point) for name, point in passing_points.items()}
    extra["loose"]["extra"] = 1.0
    with pytest.raises(InputBindingError, match="qualification inputs changed"):
        qualification_reasons(0.80, extra, protocol)


def test_oof_contract_rejects_missing_duplicate_nonfinite_and_wrong_fold() -> None:
    protocol = _protocol()
    source = synthetic_development_frame()
    development = validate_development_frame(source, protocol_sha256=protocol.sha256)
    folds = assign_folds(development)
    frame = pd.DataFrame(
        {
            "target_lambda": np.zeros(len(source)),
            "source_sample": source["source_sample"],
            "source_entry": source["source_entry"],
            "fold_index": folds,
            "label": source["label"],
            "m4l": source["m4l"],
            "physical_weight": source["physical_weight"],
            "train_weight": source["train_weight"],
            "score": np.linspace(0.1, 0.9, len(source)),
        },
        columns=OOF_COLUMNS,
    )
    validate_candidate_oof(frame, development, folds, target_lambda=0.0)
    mutations = []
    mutations.append(frame.iloc[:-1].copy())
    duplicate = frame.copy(); duplicate.loc[1, ["source_sample", "source_entry"]] = duplicate.loc[0, ["source_sample", "source_entry"]].to_numpy(); mutations.append(duplicate)
    nonfinite = frame.copy(); nonfinite.loc[0, "score"] = np.nan; mutations.append(nonfinite)
    wrong_fold = frame.copy(); wrong_fold.loc[0, "fold_index"] = (int(folds[0]) + 1) % 5; mutations.append(wrong_fold)
    mutations.append(pd.concat([frame, frame.iloc[[0]]], ignore_index=True))
    out_of_range = frame.copy(); out_of_range.loc[0, "score"] = 1.01; mutations.append(out_of_range)
    wrong_label = frame.copy(); wrong_label.loc[0, "label"] = 1 - int(frame.loc[0, "label"]); mutations.append(wrong_label)
    wrong_mass = frame.copy(); wrong_mass.loc[0, "m4l"] += 1.0; mutations.append(wrong_mass)
    wrong_weight = frame.copy(); wrong_weight.loc[0, "train_weight"] += 1.0; mutations.append(wrong_weight)
    test_identity = frame.copy(); test_identity.loc[0, "source_sample"] = "test_only"; mutations.append(test_identity)
    reordered = frame.iloc[::-1].reset_index(drop=True); mutations.append(reordered)
    for changed in mutations:
        with pytest.raises(InputBindingError):
            validate_candidate_oof(changed, development, folds, target_lambda=0.0)
