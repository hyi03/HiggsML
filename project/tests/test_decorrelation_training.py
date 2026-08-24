from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from src.decorrelation_training import (
    DROP_TOP4_FEATURES,
    FlatnessCandidateResult,
    FlatnessSelection,
    OneShotTestGate,
    build_flatness_model,
    evaluate_flatness_candidate,
    fit_selected_and_score_test,
    generate_flatness_oof,
    select_flatness_candidate,
)
from src.decorrelation_training_run import load_decorrelation_config
from src.features import FEATURES
from src.full_training_evaluation import (
    build_working_points,
    weighted_pearson,
    zz_mass_diagnostics,
)
from src.full_training_policy import assign_development_folds, development_fold


@pytest.fixture
def production_config():
    return load_decorrelation_config(
        Path("config/decorrelation_training_drop_top4.yaml")
    )


@pytest.fixture
def development_frame():
    rows = []
    event = 1
    counts = {(fold, label): 0 for fold in range(5) for label in (0, 1)}
    while min(counts.values()) < 3:
        for label in (0, 1):
            channel = 363490 if label == 0 else 345060
            event_number = event * 2 + label
            fold = development_fold(channel, event_number, folds=5)
            if counts[(fold, label)] >= 3:
                continue
            row = {
                name: float(event + offset)
                for offset, name in enumerate(FEATURES)
            }
            row.update(
                {
                    "m4l": 105.0 + event % 55,
                    "eventNumber": event_number,
                    "channelNumber": channel,
                    "split": "train" if event % 2 else "validation",
                    "label": label,
                    "physical_weight": (
                        (-1.0 if event % 7 == 0 else 1.0) * (1.0 + label)
                    ),
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

    assigned = assign_development_folds(frame, folds=5)
    assert assigned.groupby(frame["label"]).nunique().to_dict() == {0: 5, 1: 5}
    return frame


def test_model_exposes_mass_to_loss_but_not_to_trees(production_config):
    captured = {}

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
    fitted_indices = []

    class FakeModel:
        def fit(self, X, y, sample_weight):
            assert list(X.columns) == [*DROP_TOP4_FEATURES, "m4l"]
            fitted_indices.append(tuple(X.index))
            labels = y.to_numpy(dtype=int)
            totals = [sample_weight[labels == label].sum() for label in (0, 1)]
            assert np.isclose(totals[0], totals[1])
            return self

        def predict_proba(self, X):
            score = np.linspace(0.1, 0.9, len(X))
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


@pytest.fixture
def candidate_result(production_config, development_frame):
    def build(
        *, coefficient, auc, ks=None, signal=None, maximum_ks=None
    ):
        names = ("loose", "medium", "tight")
        targets = {"loose": 0.50, "medium": 0.20, "tight": 0.10}
        if ks is None:
            assert maximum_ks is not None
            ks = {
                "loose": maximum_ks / 2,
                "medium": maximum_ks / 2,
                "tight": maximum_ks,
            }
        if signal is None:
            signal = {"loose": 0.75, "medium": 0.45, "tight": 0.25}
        points = {
            name: {
                "threshold": 0.2 + index * 0.2,
                "target_background_efficiency": targets[name],
                "achieved_background_efficiency": targets[name],
                "signal_efficiency": signal[name],
            }
            for index, name in enumerate(names)
        }
        audit = development_frame.loc[
            :, [
                "eventNumber", "channelNumber", "label", "split",
                "physical_weight", "m4l",
            ]
        ].copy()
        audit["development_fold"] = assign_development_folds(
            development_frame, folds=5
        )
        audit[f"score_lambda_{coefficient:.1f}".replace(".", "p")] = np.linspace(
            0.05, 0.95, len(audit)
        )
        return FlatnessCandidateResult.from_metrics(
            coefficient=coefficient,
            weighted_auc=auc,
            background_score_mass_correlation=0.0,
            working_points=points,
            zz_ks_distances=ks,
            config=production_config,
            oof_scores=audit,
        )

    return build


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
    frame = development_frame.copy(deep=True)
    frame["split"] = "test"
    frame["eventNumber"] = np.arange(1_000_000, 1_000_000 + len(frame))
    return frame


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


def test_selection_uses_auc_then_maximum_ks_then_lower_coefficient(
    candidate_result,
):
    results = [
        candidate_result(coefficient=2.0, auc=0.82, maximum_ks=0.08),
        candidate_result(coefficient=1.0, auc=0.82, maximum_ks=0.07),
        candidate_result(coefficient=0.5, auc=0.82, maximum_ks=0.07),
    ]
    assert select_flatness_candidate(results).selected.coefficient == 0.5


def test_no_eligible_candidate_never_opens_test(
    development_frame, production_config
):
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
    with pytest.raises(RuntimeError, match="already opened"):
        gate.open()


def test_evaluate_candidate_matches_validated_metric_helpers(production_config):
    frame = pd.DataFrame(
        {
            "label": [0] * 6 + [1] * 6,
            "physical_weight": [1.0, -2.0, 1.5, 0.5, 2.5, 1.0] * 2,
            "m4l": [106, 112, 118, 126, 138, 154] * 2,
            "score_lambda_1p0": [
                0.05, 0.20, 0.35, 0.55, 0.75, 0.95,
                0.15, 0.40, 0.60, 0.72, 0.85, 0.98,
            ],
        }
    )
    result = evaluate_flatness_candidate(frame, production_config, coefficient=1.0)
    scored = frame.rename(columns={"score_lambda_1p0": "oof_score"})
    points = build_working_points(scored, production_config.working_points)
    diagnostics = zz_mass_diagnostics(
        scored, "oof_score", points, production_config
    )
    background = scored.loc[scored["label"] == 0]

    assert result.weighted_auc == roc_auc_score(
        scored["label"],
        scored["oof_score"],
        sample_weight=np.abs(scored["physical_weight"]),
    )
    assert result.background_score_mass_correlation == weighted_pearson(
        background["oof_score"],
        background["m4l"],
        background["physical_weight"],
    )
    assert result.zz_ks_distances == {
        name: values["inclusive_to_selected_ks_distance"]
        for name, values in diagnostics["working_points"].items()
    }
