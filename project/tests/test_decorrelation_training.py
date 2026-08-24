from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

import src.decorrelation_training as decorrelation_training
from src.features import FEATURES
from src.full_training_policy import assign_development_folds, development_fold
from src.decorrelation_training_run import load_decorrelation_config
from src.decorrelation_training import (
    DROP_TOP4_FEATURES,
    FlatnessCandidateResult,
    FlatnessOutcome,
    FlatnessSelection,
    OneShotTestGate,
    build_flatness_model,
    evaluate_flatness_candidate,
    fit_selected_and_score_test,
    generate_flatness_oof,
    run_development_study,
    select_flatness_candidate,
)
from src.full_training_evaluation import (
    build_working_points,
    weighted_pearson,
    zz_mass_diagnostics,
)


@pytest.fixture
def production_config():
    return load_decorrelation_config(
        Path("config/decorrelation_training_drop_top4.yaml")
    )


@pytest.fixture
def development_frame():
    rows: list[dict[str, object]] = []
    event = 1
    counts = {(fold, label): 0 for fold in range(5) for label in (0, 1)}
    while min(counts.values()) < 3:
        for label in (0, 1):
            channel = 363490 if label == 0 else 345060
            event_number = event * 2 + label
            fold = development_fold(channel, event_number, folds=5)
            if counts[(fold, label)] >= 3:
                continue
            row = {name: float(event + offset) for offset, name in enumerate(FEATURES)}
            row.update(
                {
                    "m4l": 105.0 + event % 55,
                    "eventNumber": event_number,
                    "channelNumber": channel,
                    "split": "train" if event % 2 else "validation",
                    "label": label,
                    "physical_weight": (-1.0 if event % 7 == 0 else 1.0)
                    * (1.0 + label),
                }
            )
            rows.append(row)
            counts[(fold, label)] += 1
        event += 1
    frame = pd.DataFrame(rows)
    for split in ("train", "validation"):
        for label in (0, 1):
            if not ((frame["split"] == split) & (frame["label"] == label)).any():
                index = frame.index[frame["label"] == label][0]
                frame.loc[index, "split"] = split
    assigned = assign_development_folds(frame)
    per_label_folds = assigned.groupby(frame.loc[assigned.index, "label"]).nunique()
    assert per_label_folds.to_dict() == {0: 5, 1: 5}
    return frame


@pytest.fixture
def oof_audit(development_frame):
    output = development_frame.loc[
        :,
        [
            "eventNumber",
            "channelNumber",
            "split",
            "label",
            "physical_weight",
            "m4l",
        ],
    ].copy(deep=True)
    output["development_fold"] = assign_development_folds(development_frame)
    output["score_lambda_1p0"] = np.linspace(0.05, 0.95, len(output))
    return output


@pytest.fixture
def candidate_result(production_config, oof_audit):
    def factory(
        *,
        coefficient,
        auc,
        ks=None,
        signal=None,
        maximum_ks=None,
    ):
        if ks is None:
            if maximum_ks is None:
                ks = {"loose": 0.05, "medium": 0.05, "tight": 0.05}
            else:
                ks = {
                    "loose": maximum_ks / 2.0,
                    "medium": maximum_ks / 2.0,
                    "tight": maximum_ks,
                }
        if signal is None:
            signal = {"loose": 0.75, "medium": 0.45, "tight": 0.25}
        backgrounds = {"loose": 0.50, "medium": 0.20, "tight": 0.10}
        thresholds = {"loose": 0.25, "medium": 0.50, "tight": 0.75}
        working_points = {
            name: {
                "threshold": thresholds[name],
                "target_background_efficiency": backgrounds[name],
                "achieved_background_efficiency": backgrounds[name],
                "signal_efficiency": signal[name],
            }
            for name in ("loose", "medium", "tight")
        }
        audit = oof_audit.rename(
            columns={"score_lambda_1p0": f"score_lambda_{str(float(coefficient)).replace('.', 'p')}"}
        )
        return FlatnessCandidateResult.from_metrics(
            coefficient=coefficient,
            weighted_auc=auc,
            background_score_mass_correlation=0.0,
            working_points=working_points,
            zz_ks_distances=ks,
            config=production_config,
            oof_scores=audit.copy(deep=True),
        )

    return factory


@pytest.fixture
def eligible_selection(candidate_result):
    candidate = candidate_result(
        coefficient=1.0,
        auc=0.82,
        ks={"loose": 0.05, "medium": 0.05, "tight": 0.05},
        signal={"loose": 0.75, "medium": 0.45, "tight": 0.25},
    )
    return FlatnessSelection(results=(candidate,), selected=candidate)


@pytest.fixture
def test_frame(development_frame):
    output = development_frame.copy(deep=True)
    output["split"] = "test"
    output["eventNumber"] = np.arange(10_000_000, 10_000_000 + len(output))
    return output


def test_model_exposes_mass_to_loss_but_not_to_trees(production_config):
    captured: dict[str, object] = {}

    def factory(**kwargs):
        captured.update(kwargs)
        return object()

    build_flatness_model(production_config, 1.0, model_factory=factory)

    assert captured["train_features"] == list(DROP_TOP4_FEATURES)
    assert "m4l" not in captured["train_features"]
    loss = captured["loss"]
    assert loss.uniform_features == ["m4l"]
    assert np.array_equal(loss.uniform_label, np.array([0]))
    assert loss.fl_coefficient == 1.0


def test_oof_scores_every_development_row_once_and_rebalances_each_fold(
    development_frame, production_config
):
    fitted_indices: list[tuple[int, ...]] = []

    class FakeModel:
        def fit(self, x, y, sample_weight):
            assert list(x.columns) == [*DROP_TOP4_FEATURES, "m4l"]
            fitted_indices.append(tuple(int(index) for index in x.index))
            labels = y.to_numpy(dtype=int)
            totals = [sample_weight[labels == label].sum() for label in (0, 1)]
            assert np.isclose(totals[0], totals[1])
            return self

        def predict_proba(self, x):
            score = np.linspace(0.1, 0.9, len(x))
            return np.column_stack([1.0 - score, score])

    oof = generate_flatness_oof(
        development_frame,
        production_config,
        0.5,
        model_factory=lambda **kwargs: FakeModel(),
    )

    assert oof.index.equals(development_frame.index)
    assert oof["development_fold"].between(0, 4).all()
    assert np.isfinite(oof["score_lambda_0p5"]).all()
    assert len(fitted_indices) == 5


def test_oof_rejects_nonfinite_probability_in_any_predict_proba_column(
    development_frame, production_config
):
    class FakeModel:
        def fit(self, x, y, sample_weight):
            return self

        def predict_proba(self, x):
            scores = np.linspace(0.1, 0.9, len(x))
            probabilities = np.column_stack([1.0 - scores, scores])
            probabilities[0, 0] = np.nan
            return probabilities

    with pytest.raises(ValueError, match="non-finite evaluation scores"):
        generate_flatness_oof(
            development_frame,
            production_config,
            0.5,
            model_factory=lambda **kwargs: FakeModel(),
        )


def test_oof_rejects_duplicate_development_index_before_fold_fitting(
    development_frame, production_config
):
    duplicated = development_frame.copy(deep=True)
    duplicated.index = pd.Index([index // 2 for index in range(len(duplicated))])

    class FakeModel:
        def fit(self, x, y, sample_weight):
            raise AssertionError("duplicate indexes must be rejected before fold fitting")

        def predict_proba(self, x):
            raise AssertionError("duplicate indexes must be rejected before scoring")

    with pytest.raises(ValueError, match="unique DataFrame index"):
        generate_flatness_oof(
            duplicated,
            production_config,
            0.5,
            model_factory=lambda **kwargs: FakeModel(),
        )


@pytest.mark.parametrize("stage", ("oof", "test"))
def test_prediction_receives_only_ten_nonmass_features(
    stage,
    development_frame,
    test_frame,
    production_config,
    eligible_selection,
    monkeypatch,
):
    class FakeModel:
        def fit(self, X, y, sample_weight):
            assert list(X.columns) == [*DROP_TOP4_FEATURES, "m4l"]
            return self

        def predict_proba(self, X):
            assert list(X.columns) == list(DROP_TOP4_FEATURES)
            score = np.linspace(0.1, 0.9, len(X))
            return np.column_stack([1.0 - score, score])

    if stage == "oof":
        generate_flatness_oof(
            development_frame,
            production_config,
            0.5,
            model_factory=lambda **kwargs: FakeModel(),
        )
    else:
        monkeypatch.setattr(
            "src.decorrelation_training.build_flatness_model",
            lambda config, coefficient: FakeModel(),
        )
        fit_selected_and_score_test(
            development_frame,
            OneShotTestGate(lambda: test_frame),
            production_config,
            eligible_selection,
        )


def test_candidate_requires_every_frozen_gate(candidate_result):
    eligible = candidate_result(
        coefficient=1.0,
        auc=0.80,
        ks={"loose": 0.10, "medium": 0.10, "tight": 0.10},
        signal={"loose": 0.51, "medium": 0.21, "tight": 0.11},
    )
    assert eligible.eligibility_reasons == ()

    failed = candidate_result(
        coefficient=2.0,
        auc=np.nextafter(0.80, 0.0),
        ks={"loose": 0.10, "medium": 0.10, "tight": 0.10},
        signal={"loose": 0.51, "medium": 0.21, "tight": 0.11},
    )
    assert failed.eligibility_reasons == ("weighted_auc_below_floor",)


def test_candidate_cannot_bypass_validated_factory(candidate_result):
    valid = candidate_result(coefficient=1.0, auc=0.82)

    with pytest.raises(TypeError):
        FlatnessCandidateResult(
            coefficient=valid.coefficient,
            weighted_auc=valid.weighted_auc,
            background_score_mass_correlation=(
                valid.background_score_mass_correlation
            ),
            working_points={
                name: dict(point) for name, point in valid.working_points.items()
            },
            achieved_background_efficiencies=dict(
                valid.achieved_background_efficiencies
            ),
            signal_efficiencies=dict(valid.signal_efficiencies),
            target_background_efficiencies=dict(
                valid.target_background_efficiencies
            ),
            zz_ks_distances=dict(valid.zz_ks_distances),
            eligibility_reasons=(),
            oof_scores=valid.oof_scores.copy(deep=True),
        )


def test_candidate_reports_failed_gates_in_frozen_order(candidate_result):
    failed = candidate_result(
        coefficient=2.0,
        auc=0.79,
        ks={"loose": 0.11, "medium": 0.12, "tight": 0.13},
        signal={"loose": 0.50, "medium": 0.20, "tight": 0.10},
    )

    assert failed.eligibility_reasons == (
        "weighted_auc_below_floor",
        "loose_zz_mass_ks_exceeds_limit",
        "medium_zz_mass_ks_exceeds_limit",
        "tight_zz_mass_ks_exceeds_limit",
        "loose_signal_efficiency_not_above_background",
        "medium_signal_efficiency_not_above_background",
        "tight_signal_efficiency_not_above_background",
    )


def test_candidate_snapshots_nested_metrics_and_oof(
    production_config, oof_audit
):
    points = {
        name: {
            "threshold": threshold,
            "target_background_efficiency": target,
            "achieved_background_efficiency": target,
            "signal_efficiency": signal,
        }
        for name, threshold, target, signal in (
            ("loose", 0.2, 0.5, 0.7),
            ("medium", 0.5, 0.2, 0.4),
            ("tight", 0.8, 0.1, 0.2),
        )
    }
    result = FlatnessCandidateResult.from_metrics(
        coefficient=1.0,
        weighted_auc=0.82,
        background_score_mass_correlation=0.0,
        working_points=points,
        zz_ks_distances={"loose": 0.05, "medium": 0.05, "tight": 0.05},
        config=production_config,
        oof_scores=oof_audit,
    )

    points["loose"]["threshold"] = 0.99
    oof_audit.loc[oof_audit.index[0], "m4l"] = -1.0

    assert result.working_points["loose"]["threshold"] == 0.2
    assert result.oof_scores.iloc[0]["m4l"] != -1.0
    with pytest.raises(TypeError):
        result.working_points["loose"]["threshold"] = 0.4


def test_candidate_rejects_nonfinite_oof_audit(production_config, oof_audit):
    invalid = oof_audit.copy(deep=True)
    invalid.loc[invalid.index[0], "score_lambda_1p0"] = np.nan
    points = {
        name: {
            "threshold": threshold,
            "target_background_efficiency": target,
            "achieved_background_efficiency": target,
            "signal_efficiency": signal,
        }
        for name, threshold, target, signal in (
            ("loose", 0.2, 0.5, 0.7),
            ("medium", 0.5, 0.2, 0.4),
            ("tight", 0.8, 0.1, 0.2),
        )
    }

    with pytest.raises(ValueError, match="OOF audit contains NaN or infinity"):
        FlatnessCandidateResult.from_metrics(
            coefficient=1.0,
            weighted_auc=0.82,
            background_score_mass_correlation=0.0,
            working_points=points,
            zz_ks_distances={"loose": 0.05, "medium": 0.05, "tight": 0.05},
            config=production_config,
            oof_scores=invalid,
        )


def test_selection_uses_auc_then_maximum_ks_then_lower_coefficient(
    candidate_result,
):
    results = [
        candidate_result(coefficient=2.0, auc=0.82, maximum_ks=0.08),
        candidate_result(coefficient=1.0, auc=0.82, maximum_ks=0.07),
        candidate_result(coefficient=0.5, auc=0.82, maximum_ks=0.07),
    ]
    assert select_flatness_candidate(results).selected.coefficient == 0.5


def test_evaluate_candidate_matches_validated_metric_helpers(production_config):
    frame = pd.DataFrame(
        {
            "label": [0] * 6 + [1] * 6,
            "physical_weight": [1.0, -2.0, 3.0, -4.0, 5.0, 6.0,
                                -1.5, 2.5, -3.5, 4.5, -5.5, 6.5],
            "m4l": [106.0, 112.0, 118.0, 124.0, 136.0, 154.0,
                    108.0, 114.0, 121.0, 129.0, 143.0, 158.0],
            "score_lambda_1p0": [0.05, 0.15, 0.25, 0.35, 0.45, 0.55,
                                  0.40, 0.50, 0.60, 0.70, 0.80, 0.90],
        }
    )
    normalized = frame.rename(columns={"score_lambda_1p0": "oof_score"})
    points = build_working_points(normalized, production_config.working_points)
    metric_policy = SimpleNamespace(
        working_points=production_config.working_points,
        mass_bins_gev=(105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160),
    )
    diagnostics = zz_mass_diagnostics(
        normalized, "oof_score", points, metric_policy
    )
    background = normalized.loc[normalized["label"] == 0]
    expected_auc = roc_auc_score(
        normalized["label"],
        normalized["oof_score"],
        sample_weight=np.abs(normalized["physical_weight"]),
    )
    expected_correlation = weighted_pearson(
        background["oof_score"], background["m4l"], background["physical_weight"]
    )
    expected_ks = {
        name: values["inclusive_to_selected_ks_distance"]
        for name, values in diagnostics["working_points"].items()
    }

    result = evaluate_flatness_candidate(frame, production_config, coefficient=1.0)

    assert result.weighted_auc == expected_auc
    assert result.background_score_mass_correlation == expected_correlation
    assert dict(result.zz_ks_distances) == expected_ks


def test_metric_policy_rejects_alternate_mass_bins(production_config):
    with pytest.raises(TypeError):
        decorrelation_training._MetricPolicy(
            production_config.working_points,
            mass_bins_gev=(100, 125, 160),
        )


def test_development_study_evaluates_every_frozen_coefficient(
    development_frame, production_config, monkeypatch
):
    class FakeModel:
        def fit(self, X, y, sample_weight):
            return self

        def predict_proba(self, X):
            score = np.linspace(0.1, 0.9, len(X))
            return np.column_stack([1.0 - score, score])

    monkeypatch.setattr(
        "src.decorrelation_training.build_flatness_model",
        lambda config, coefficient, model_factory=None: FakeModel(),
    )

    selection = run_development_study(development_frame, production_config)

    assert tuple(result.coefficient for result in selection.results) == (
        production_config.coefficients
    )


def test_no_eligible_candidate_never_opens_test(development_frame, production_config):
    calls = []
    gate = OneShotTestGate(lambda: calls.append("opened") or pd.DataFrame())
    selection = FlatnessSelection(results=(), selected=None)
    outcome = fit_selected_and_score_test(
        development_frame, gate, production_config, selection
    )
    assert outcome.evidence is None
    assert calls == []


def test_selected_candidate_opens_test_exactly_once(
    development_frame,
    test_frame,
    production_config,
    eligible_selection,
    monkeypatch,
):
    class FakeModel:
        def fit(self, X, y, sample_weight):
            assert list(X.columns) == [*DROP_TOP4_FEATURES, "m4l"]
            labels = y.to_numpy(dtype=int)
            assert np.isclose(sample_weight[labels == 0].sum(), sample_weight[labels == 1].sum())
            return self

        def predict_proba(self, X):
            score = np.linspace(0.1, 0.9, len(X))
            return np.column_stack([1.0 - score, score])

    monkeypatch.setattr(
        "src.decorrelation_training.build_flatness_model",
        lambda config, coefficient: FakeModel(),
    )
    calls = []

    def test_loader():
        calls.append("opened")
        return test_frame.copy(deep=True)

    gate = OneShotTestGate(test_loader)
    evidence = fit_selected_and_score_test(
        development_frame, gate, production_config, eligible_selection
    ).evidence
    assert evidence is not None
    assert calls == ["opened"]
    assert evidence.test_working_points["loose"]["threshold"] == (
        eligible_selection.selected.working_points["loose"]["threshold"]
    )
    with pytest.raises(RuntimeError, match="already opened"):
        gate.open()


def test_empty_test_working_point_is_reported_without_reselection(
    development_frame,
    test_frame,
    production_config,
    eligible_selection,
    monkeypatch,
):
    class FakeModel:
        def fit(self, X, y, sample_weight):
            return self

        def predict_proba(self, X):
            score = np.linspace(0.1, 0.7, len(X))
            return np.column_stack([1.0 - score, score])

    monkeypatch.setattr(
        "src.decorrelation_training.build_flatness_model",
        lambda config, coefficient: FakeModel(),
    )

    evidence = fit_selected_and_score_test(
        development_frame,
        OneShotTestGate(lambda: test_frame),
        production_config,
        eligible_selection,
    ).evidence

    assert evidence is not None
    assert evidence.test_working_points["tight"]["threshold"] == 0.75
    assert evidence.test_zz_ks_distances["tight"] is None


def test_outcome_snapshots_selection_before_return(
    development_frame,
    test_frame,
    production_config,
    eligible_selection,
    monkeypatch,
):
    class FakeModel:
        def fit(self, X, y, sample_weight):
            return self

        def predict_proba(self, X):
            score = np.linspace(0.1, 0.9, len(X))
            return np.column_stack([1.0 - score, score])

    monkeypatch.setattr(
        "src.decorrelation_training.build_flatness_model",
        lambda config, coefficient: FakeModel(),
    )
    outcome = fit_selected_and_score_test(
        development_frame,
        OneShotTestGate(lambda: test_frame),
        production_config,
        eligible_selection,
    )
    row = eligible_selection.selected.oof_scores.index[0]
    original_mass = float(eligible_selection.selected.oof_scores.loc[row, "m4l"])

    eligible_selection.selected.oof_scores.loc[row, "m4l"] = -1.0

    assert outcome.selection.selected.oof_scores.loc[row, "m4l"] == original_mass
    assert outcome.evidence.candidate.oof_scores.loc[row, "m4l"] == original_mass


def test_outcome_rejects_evidence_from_different_same_coefficient_candidate(
    development_frame,
    test_frame,
    production_config,
    candidate_result,
    monkeypatch,
):
    class FakeModel:
        def fit(self, X, y, sample_weight):
            return self

        def predict_proba(self, X):
            score = np.linspace(0.1, 0.9, len(X))
            return np.column_stack([1.0 - score, score])

    candidate_a = candidate_result(coefficient=1.0, auc=0.82, maximum_ks=0.06)
    selection_a = FlatnessSelection(results=(candidate_a,), selected=candidate_a)
    candidate_b = candidate_result(coefficient=1.0, auc=0.84, maximum_ks=0.04)
    selection_b = FlatnessSelection(results=(candidate_b,), selected=candidate_b)
    monkeypatch.setattr(
        "src.decorrelation_training.build_flatness_model",
        lambda config, coefficient: FakeModel(),
    )
    evidence_a = fit_selected_and_score_test(
        development_frame,
        OneShotTestGate(lambda: test_frame),
        production_config,
        selection_a,
    ).evidence

    with pytest.raises(ValueError, match="exact selected candidate"):
        FlatnessOutcome(selection=selection_b, evidence=evidence_a)
