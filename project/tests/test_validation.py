import importlib
import json

import pandas as pd
import pytest


def validation_module():
    return importlib.import_module("src.validation")


def scored_frame(split_scores):
    rows = []
    event_number = 0
    for split, scores_by_label in split_scores.items():
        for label, scores in scores_by_label.items():
            for score in scores:
                rows.append(
                    {
                        "eventNumber": event_number,
                        "split": split,
                        "label": label,
                        "xgb_score": score,
                        "physical_weight": 1.0,
                    }
                )
                event_number += 1
    return pd.DataFrame(rows)


def test_weighted_ks_distance_is_zero_for_identical_and_one_for_disjoint_samples():
    module = validation_module()

    assert module.weighted_ks_distance([0.0, 1.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert module.weighted_ks_distance([0.0, 0.0], [1.0, 1.0]) == pytest.approx(1.0)


def test_threshold_is_selected_on_validation_and_frozen_for_test_evaluation():
    module = validation_module()
    frame = scored_frame(
        {
            "train": {0: [0.2, 0.1], 1: [0.95, 0.85]},
            "validation": {0: [0.7, 0.1], 1: [0.9, 0.8]},
            "test": {0: [0.9, 0.5], 1: [0.6, 0.55]},
        }
    )

    report = module.evaluate_scored_events(
        frame, threshold_grid=[0.1, 0.7, 0.8, 0.9]
    )

    assert report["threshold_selection_split"] == "validation"
    assert report["best_threshold"] == pytest.approx(0.7)
    assert report["validation_expected_signal"] == pytest.approx(2.0)
    assert report["validation_expected_background"] == pytest.approx(1.0)
    assert report["expected_signal"] == pytest.approx(0.0)
    assert report["expected_background"] == pytest.approx(1.0)
    assert report["test_auc"] == pytest.approx(0.5)


def test_matching_train_and_test_shapes_do_not_trigger_overfitting_warning():
    module = validation_module()
    frame = scored_frame(
        {
            "train": {0: [0.1, 0.2], 1: [0.8, 0.9]},
            "validation": {0: [0.1, 0.2], 1: [0.8, 0.9]},
            "test": {0: [0.1, 0.2], 1: [0.8, 0.9]},
        }
    )

    report = module.evaluate_scored_events(frame)

    assert report["train_test_auc_gap"] == pytest.approx(0.0)
    assert report["signal_ks_distance"] == pytest.approx(0.0)
    assert report["background_ks_distance"] == pytest.approx(0.0)
    assert report["overfitting_warning"] is False


def test_shifted_score_shapes_trigger_overfitting_warning_even_when_auc_matches():
    module = validation_module()
    frame = scored_frame(
        {
            "train": {0: [0.1, 0.2], 1: [0.8, 0.9]},
            "validation": {0: [0.1, 0.2], 1: [0.8, 0.9]},
            "test": {0: [0.3, 0.4], 1: [0.5, 0.6]},
        }
    )

    report = module.evaluate_scored_events(frame)

    assert report["train_auc"] == pytest.approx(1.0)
    assert report["test_auc"] == pytest.approx(1.0)
    assert report["signal_ks_distance"] == pytest.approx(1.0)
    assert report["background_ks_distance"] == pytest.approx(1.0)
    assert report["overfitting_warning"] is True


def test_validation_reports_persist_threshold_provenance_and_overfitting_fields(
    tmp_path,
):
    validation = validation_module()
    training = importlib.import_module("src.train")
    frame = scored_frame(
        {
            "train": {0: [0.1, 0.2], 1: [0.8, 0.9]},
            "validation": {0: [0.1, 0.2], 1: [0.8, 0.9]},
            "test": {0: [0.1, 0.2], 1: [0.8, 0.9]},
        }
    )
    report = validation.evaluate_scored_events(frame)
    report.update(
        {
            "features": ["mZ1", "mZ2"],
            "train_events": 4,
            "validation_events": 4,
            "test_events": 4,
        }
    )

    training.persist_validation_reports(report, tmp_path)

    metrics = json.loads((tmp_path / "metrics.json").read_text())
    overfitting = json.loads((tmp_path / "overfitting_check.json").read_text())
    assert metrics["threshold_selection_split"] == "validation"
    assert metrics["features"] == ["mZ1", "mZ2"]
    assert overfitting == {
        "train_auc": 1.0,
        "validation_auc": 1.0,
        "test_auc": 1.0,
        "train_test_auc_gap": 0.0,
        "validation_test_auc_gap": 0.0,
        "signal_ks_distance": 0.0,
        "background_ks_distance": 0.0,
        "auc_gap_limit": 0.05,
        "ks_distance_limit": 0.1,
        "overfitting_warning": False,
        "overfitting_warning_reasons": [],
    }
