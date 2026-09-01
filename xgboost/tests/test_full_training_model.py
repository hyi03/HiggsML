from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.features import FEATURES
from src.full_training_model import (
    CandidateResult,
    FoldMetric,
    ModelSelectionResult,
    choose_candidate,
    cross_validate_candidates,
    effective_parameters,
    final_tree_count,
    fit_final_model,
)
from src.full_training_policy import CandidateSpec, load_training_policy


def _candidate(depth: int, child: float) -> CandidateSpec:
    return CandidateSpec(f"depth{depth}_child{int(child)}", depth, child)


def _result(
    candidate: CandidateSpec,
    mean: float,
    standard_error: float,
    *,
    fold_overrides: dict[int, FoldMetric] | None = None,
) -> CandidateResult:
    folds = tuple(
        (fold_overrides or {}).get(fold, FoldMetric(fold, mean, mean, 4))
        for fold in range(5)
    )
    return CandidateResult(candidate, folds, mean, standard_error)


def _six_results() -> list[CandidateResult]:
    return [
        _result(_candidate(depth, child), 0.80, 0.01)
        for depth in (2, 3, 4)
        for child in (20, 5)
    ]


def test_choose_candidate_uses_best_standard_error_band_then_simplicity():
    results = _six_results()
    results[0] = _result(_candidate(2, 20), 0.900, 0.001)
    results[1] = _result(_candidate(2, 5), 0.899, 0.001)
    results[2] = _result(_candidate(3, 20), 0.905, 0.010)

    selected = choose_candidate(results)

    assert selected.candidate == _candidate(2, 20)


@pytest.mark.parametrize("bad_auc", [np.nan, np.inf, -np.inf])
def test_choose_candidate_rejects_nonfinite_fold_auc(bad_auc):
    results = _six_results()
    results[0] = _result(
        _candidate(2, 20),
        0.80,
        0.01,
        fold_overrides={0: FoldMetric(0, bad_auc, 0.80, 4)},
    )

    with pytest.raises(ValueError, match="AUC"):
        choose_candidate(results)


@pytest.mark.parametrize(
    ("folds", "message"),
    [
        (
            tuple(FoldMetric(fold, 0.80, 0.80, 4) for fold in range(4)),
            "five folds",
        ),
        (
            (
                FoldMetric(0, 0.80, 0.80, 4),
                FoldMetric(0, 0.80, 0.80, 4),
                FoldMetric(2, 0.80, 0.80, 4),
                FoldMetric(3, 0.80, 0.80, 4),
                FoldMetric(4, 0.80, 0.80, 4),
            ),
            "unique",
        ),
        (
            tuple(
                FoldMetric(fold, 0.80, 0.80, -1 if fold == 0 else 4)
                for fold in range(5)
            ),
            "best_iteration",
        ),
    ],
)
def test_choose_candidate_rejects_invalid_fold_metrics(folds, message):
    results = _six_results()
    first = results[0]
    results[0] = CandidateResult(
        first.candidate,
        folds,
        first.mean_weighted_auc,
        first.standard_error_weighted_auc,
    )

    with pytest.raises(ValueError, match=message):
        choose_candidate(results)


def test_choose_candidate_requires_exactly_six_candidates():
    with pytest.raises(ValueError, match="six"):
        choose_candidate(_six_results()[:-1])


def test_final_tree_count_rounds_median_zero_based_iteration_to_tree_count():
    result = _result(
        _candidate(2, 20),
        0.8,
        0.01,
        fold_overrides={
            0: FoldMetric(0, 0.8, 0.8, 0),
            1: FoldMetric(1, 0.8, 0.8, 1),
            2: FoldMetric(2, 0.8, 0.8, 3),
            3: FoldMetric(3, 0.8, 0.8, 4),
            4: FoldMetric(4, 0.8, 0.8, 5),
        },
    )

    assert final_tree_count(result) == 4


def _development_frame() -> pd.DataFrame:
    rows = []
    found = {0: set(), 1: set()}
    event_number = 1
    while any(len(folds) < 5 for folds in found.values()):
        channel_number = 345060 if event_number % 2 else 700600
        digest = hashlib.blake2b(
            f"task4b-fold:{channel_number}:{event_number}".encode(), digest_size=8
        ).digest()
        fold = int.from_bytes(digest, "big") % 5
        label = event_number % 2
        if fold not in found[label]:
            found[label].add(fold)
            rows.append(
                {
                    **{
                        feature: float(label) + 0.2
                        for feature in FEATURES
                    },
                    "m4l": 125.0,
                    "eventNumber": event_number,
                    "channelNumber": channel_number,
                    "split": "train" if event_number % 3 else "validation",
                    "label": label,
                    "physical_weight": -2.0 if label else 1.0,
                }
            )
        event_number += 1
    for label in (0, 1):
        rows.append(
            {
                **{feature: float(label) + 0.2 for feature in FEATURES},
                "m4l": 125.0,
                "eventNumber": event_number,
                "channelNumber": 345060,
                "split": "test",
                "label": label,
                "physical_weight": 1.0,
            }
        )
        event_number += 1
    return pd.DataFrame(rows)


class RecordingClassifier:
    def __init__(self, records: list[dict], **parameters: object) -> None:
        self.records = records
        self.parameters = parameters
        self.best_iteration = 3

    def fit(
        self,
        x: pd.DataFrame,
        y: pd.Series,
        *,
        sample_weight: np.ndarray,
        eval_set: list[tuple[pd.DataFrame, pd.Series]] | None = None,
        sample_weight_eval_set: list[np.ndarray] | None = None,
        verbose: bool | None = None,
    ) -> "RecordingClassifier":
        self.records.append(
            {
                "parameters": self.parameters,
                "fit_indices": x.index.copy(),
                "fit_columns": tuple(x.columns),
                "labels": y.copy(),
                "sample_weight": np.asarray(sample_weight),
                "eval_indices": None if eval_set is None else eval_set[0][0].index.copy(),
                "eval_weights": None
                if sample_weight_eval_set is None
                else np.asarray(sample_weight_eval_set[0]),
                "predict_indices": [],
            }
        )
        self._record = self.records[-1]
        return self

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        self._record["predict_indices"].append(x.index.copy())
        self._record.setdefault("predict_columns", []).append(tuple(x.columns))
        signal_probability = (
            x.iloc[:, 0].to_numpy(dtype=float) / 1.4
            + 0.01 * float(self.parameters["max_depth"])
        )
        return np.column_stack([1.0 - signal_probability, signal_probability])


@pytest.fixture
def policy():
    return load_training_policy(Path("config/full_training.yaml"))


def test_cross_validate_candidates_isolated_weighted_and_returns_selected_oof(policy):
    frame = _development_frame()
    records: list[dict] = []

    selection = cross_validate_candidates(
        frame,
        policy,
        model_factory=lambda **parameters: RecordingClassifier(records, **parameters),
    )

    development = frame.index[frame["split"] != "test"]
    test = frame.index[frame["split"] == "test"]
    assert len(records) == 30
    assert len(selection.candidates) == 6
    assert tuple(item.candidate for item in selection.candidates) == policy.candidates
    assert selection.selected.candidate == policy.candidates[0]
    assert set(selection.oof_scores.index) == set(development)
    assert not set(selection.oof_scores.index) & set(test)
    assert selection.oof_scores.name == "oof_score"
    assert selection.oof_scores.to_numpy() == pytest.approx(
        frame.loc[development, "lep1_pt"].to_numpy(dtype=float) / 1.4 + 0.02
    )

    predicted_by_candidate: defaultdict[str, list[int]] = defaultdict(list)
    for record in records:
        assert not set(record["fit_indices"]) & set(test)
        assert not set(record["eval_indices"]) & set(test)
        assert set(record["fit_columns"]) == set(FEATURES)
        assert record["fit_columns"] == tuple(FEATURES)
        assert record["parameters"]["random_state"] == 42
        assert record["parameters"]["n_jobs"] == 4
        for name, value in policy.common_parameters.items():
            assert record["parameters"][name] == value
        assert record["parameters"]["max_depth"] in (2, 3, 4)
        assert record["parameters"]["min_child_weight"] in (5.0, 20.0)
        labels = record["labels"].to_numpy(dtype=int)
        weights = record["sample_weight"]
        assert weights[labels == 0].sum() == pytest.approx(len(weights) / 2)
        assert weights[labels == 1].sum() == pytest.approx(len(weights) / 2)
        assert weights.mean() == pytest.approx(1.0)
        eval_rows = frame.loc[record["eval_indices"]]
        assert record["eval_weights"] == pytest.approx(
            np.abs(eval_rows["physical_weight"].to_numpy(dtype=float))
        )
        predicted_by_candidate[record["parameters"]["max_depth"], record["parameters"]["min_child_weight"]].extend(
            record["predict_indices"][0].tolist()
        )

    assert all(
        sorted(indices) == sorted(development.tolist())
        for indices in predicted_by_candidate.values()
    )


def test_cross_validation_uses_multipliers_only_for_class_balanced_fitting_weights(policy):
    """Applying multipliers to evaluation weights or model columns must fail this test."""
    frame = _development_frame()
    multipliers = pd.Series(1.0, index=frame.index)
    background = frame.index[frame["label"].eq(0)]
    multipliers.loc[background[0]] = 2.0
    multipliers.loc[background[1]] = 0.5
    records: list[dict] = []
    features = ("lep1_pt", "lep2_eta", "deltaPhi_ZZ")

    cross_validate_candidates(
        frame,
        policy,
        model_factory=lambda **parameters: RecordingClassifier(records, **parameters),
        training_weight_multipliers=multipliers,
        features=features,
    )

    for record in records:
        fitting = frame.loc[record["fit_indices"]]
        expected = np.empty(len(fitting), dtype=float)
        for label in (0, 1):
            mask = fitting["label"].to_numpy(dtype=int) == label
            adjusted = (
                np.abs(fitting.loc[mask, "physical_weight"].to_numpy(dtype=float))
                * multipliers.loc[fitting.index[mask]].to_numpy(dtype=float)
            )
            expected[mask] = adjusted * (len(fitting) / 2) / adjusted.sum()
        np.testing.assert_allclose(record["sample_weight"], expected)

        evaluation = frame.loc[record["eval_indices"]]
        np.testing.assert_array_equal(
            record["eval_weights"],
            np.abs(evaluation["physical_weight"].to_numpy(dtype=float)),
        )
        assert record["fit_columns"] == features
        assert record["predict_columns"] == [features]


def test_cross_validation_rejects_test_multiplier_for_development_only_frame(policy):
    """Dropping exact multiplier-index validation must fail this test."""
    frame = _development_frame()
    development = frame.loc[frame["split"] != "test"]
    multipliers = pd.Series(1.0, index=frame.index)
    records: list[dict] = []

    with pytest.raises(ValueError, match="index"):
        cross_validate_candidates(
            development,
            policy,
            model_factory=lambda **parameters: RecordingClassifier(records, **parameters),
            training_weight_multipliers=multipliers,
        )

    assert records == []


def test_cross_validation_rejects_duplicate_index_before_test_row_can_leak(policy):
    frame = _development_frame()
    duplicate_index = frame.index.to_numpy(copy=True)
    duplicate_index[-1] = duplicate_index[0]
    frame.index = duplicate_index
    records: list[dict] = []

    with pytest.raises(ValueError, match="unique DataFrame index"):
        cross_validate_candidates(
            frame,
            policy,
            model_factory=lambda **parameters: RecordingClassifier(records, **parameters),
        )

    assert records == []


def test_cross_validation_retains_safe_identifier_collision_in_selected_oof(policy):
    frame = _development_frame()
    original_index = int(frame.index[0])
    duplicate_index = int(frame.index.max()) + 1
    duplicate = frame.loc[[original_index]].copy()
    duplicate.index = [duplicate_index]
    frame = pd.concat([frame, duplicate])
    records: list[dict] = []

    selection = cross_validate_candidates(
        frame,
        policy,
        model_factory=lambda **parameters: RecordingClassifier(records, **parameters),
    )

    expected_development = frame.index[frame["split"] != "test"]
    assert selection.oof_scores.index.equals(expected_development)
    assert selection.oof_scores.notna().all()
    assert len(selection.oof_scores) == len(expected_development)
    assert original_index in selection.oof_scores.index
    assert duplicate_index in selection.oof_scores.index
    assert (
        selection.development_folds.loc[original_index]
        == selection.development_folds.loc[duplicate_index]
    )


def test_final_fit_uses_development_only_with_frozen_final_parameters(policy):
    frame = _development_frame()
    selected = _result(
        policy.candidates[3],
        0.9,
        0.01,
        fold_overrides={
            0: FoldMetric(0, 0.9, 0.9, 0),
            1: FoldMetric(1, 0.9, 0.9, 1),
            2: FoldMetric(2, 0.9, 0.9, 3),
            3: FoldMetric(3, 0.9, 0.9, 4),
            4: FoldMetric(4, 0.9, 0.9, 5),
        },
    )
    selection = ModelSelectionResult(
        selected=selected,
        candidates=(selected,),
        oof_scores=pd.Series(dtype=float),
        development_folds=pd.Series(dtype=int),
    )
    records: list[dict] = []

    model = fit_final_model(
        frame,
        selection,
        policy,
        model_factory=lambda **parameters: RecordingClassifier(records, **parameters),
    )

    assert isinstance(model, RecordingClassifier)
    assert len(records) == 1
    record = records[0]
    expected_development = frame.index[frame["split"] != "test"]
    assert set(record["fit_indices"]) == set(expected_development)
    assert record["eval_indices"] is None
    assert record["eval_weights"] is None
    assert record["predict_indices"] == []
    assert record["parameters"] == effective_parameters(selection, policy, final=True)
    assert record["parameters"]["n_estimators"] == 4
    assert "early_stopping_rounds" not in record["parameters"]
    assert record["parameters"]["max_depth"] == 3
    assert record["parameters"]["min_child_weight"] == 5.0


def test_final_fit_uses_multipliers_for_development_rows_only(policy):
    """Passing test multipliers into the final fit must fail this test."""
    frame = _development_frame()
    selected = _result(policy.candidates[0], 0.9, 0.01)
    selection = ModelSelectionResult(
        selected=selected,
        candidates=(selected,),
        oof_scores=pd.Series(dtype=float),
        development_folds=pd.Series(dtype=int),
    )
    multipliers = pd.Series(1.0, index=frame.index)
    development_index = frame.index[frame["split"] != "test"]
    background = development_index[frame.loc[development_index, "label"].eq(0)]
    multipliers.loc[background[0]] = 3.0
    multipliers.loc[frame.index[frame["split"] == "test"]] = 99.0
    records: list[dict] = []

    fit_final_model(
        frame,
        selection,
        policy,
        model_factory=lambda **parameters: RecordingClassifier(records, **parameters),
        training_weight_multipliers=multipliers,
    )

    record = records[0]
    fitting = frame.loc[record["fit_indices"]]
    expected = np.empty(len(fitting), dtype=float)
    for label in (0, 1):
        mask = fitting["label"].to_numpy(dtype=int) == label
        adjusted = (
            np.abs(fitting.loc[mask, "physical_weight"].to_numpy(dtype=float))
            * multipliers.loc[fitting.index[mask]].to_numpy(dtype=float)
        )
        expected[mask] = adjusted * (len(fitting) / 2) / adjusted.sum()
    np.testing.assert_allclose(record["sample_weight"], expected)
    assert not set(record["fit_indices"]) & set(frame.index[frame["split"] == "test"])


def test_default_and_none_multiplier_paths_produce_identical_recorded_predictions(policy):
    frame = _development_frame()
    default_records: list[dict] = []
    none_records: list[dict] = []
    factory = lambda records: (
        lambda **parameters: RecordingClassifier(records, **parameters)
    )

    default_selection = cross_validate_candidates(frame, policy, factory(default_records))
    none_selection = cross_validate_candidates(
        frame,
        policy,
        factory(none_records),
        training_weight_multipliers=None,
    )

    np.testing.assert_array_equal(default_selection.oof_scores, none_selection.oof_scores)
    assert len(default_records) == len(none_records)
    for default, none in zip(default_records, none_records, strict=True):
        np.testing.assert_array_equal(default["sample_weight"], none["sample_weight"])
        np.testing.assert_array_equal(default["eval_weights"], none["eval_weights"])
        assert default["predict_columns"] == none["predict_columns"] == [tuple(FEATURES)]


def test_explicit_feature_tuple_controls_cv_fit_and_score_column_order(policy):
    """Replacing a requested feature slice with global FEATURES must fail this test."""
    import src.full_training_model as full_training_model

    frame = _development_frame()
    features = ("lep1_pt", "lep2_eta", "deltaPhi_ZZ")
    records: list[dict] = []
    factory = lambda **parameters: RecordingClassifier(records, **parameters)

    selection = cross_validate_candidates(
        frame, policy, factory, features=features
    )
    model = fit_final_model(frame, selection, policy, factory, features=features)
    test = frame.loc[frame["split"] == "test"]
    scores = full_training_model.score_model(model, test, features=features)

    assert len(scores) == len(test)
    assert [record["fit_columns"] for record in records] == [features] * 31
    assert [
        columns
        for record in records
        for columns in record["predict_columns"]
    ] == [features] * 31


@pytest.mark.parametrize(
    "features",
    [
        (),
        ("lep1_pt", "lep1_pt"),
        ("m4l",),
        ("label",),
        ("not_a_feature",),
        ("lep1_pt", 7),
    ],
)
def test_invalid_feature_tuples_reject_before_model_factory(policy, features):
    """Removing feature validation before classifier creation must fail this test."""
    records: list[dict] = []

    with pytest.raises(ValueError):
        cross_validate_candidates(
            _development_frame(),
            policy,
            lambda **parameters: RecordingClassifier(records, **parameters),
            features=features,
        )

    assert records == []
