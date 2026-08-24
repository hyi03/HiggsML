"""Development-only KNN-flatness training primitives."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from .decorrelation_training_run import DecorrelationConfig
from .full_training_evaluation import (
    build_working_points,
    weighted_pearson,
    zz_mass_diagnostics,
)
from .full_training_policy import (
    assign_development_folds,
    class_balanced_training_weights,
    validate_development_frame,
    validate_mc_frame,
)


DROP_TOP4_FEATURES = (
    "lep1_pt",
    "lep2_pt",
    "lep1_eta",
    "lep2_eta",
    "lep3_eta",
    "lep4_eta",
    "pt4l",
    "deltaR_Z1",
    "deltaR_Z2",
    "deltaPhi_ZZ",
)
_WORKING_POINT_NAMES = ("loose", "medium", "tight")


@dataclass(frozen=True)
class FlatnessCandidateResult:
    coefficient: float
    weighted_auc: float
    background_score_mass_correlation: float
    working_points: Mapping[str, Mapping[str, object]]
    signal_efficiencies: Mapping[str, float]
    target_background_efficiencies: Mapping[str, float]
    zz_ks_distances: Mapping[str, float]
    eligibility_reasons: tuple[str, ...]
    oof_scores: pd.DataFrame

    @classmethod
    def from_metrics(
        cls,
        *,
        coefficient: float,
        weighted_auc: float,
        background_score_mass_correlation: float,
        working_points: Mapping[str, Mapping[str, object]],
        zz_ks_distances: Mapping[str, float],
        config: DecorrelationConfig,
        oof_scores: pd.DataFrame,
    ) -> "FlatnessCandidateResult":
        coefficient_value = float(coefficient)
        if coefficient_value not in config.coefficients:
            raise ValueError("flatness coefficient is not a frozen candidate")
        if set(working_points) != set(_WORKING_POINT_NAMES):
            raise ValueError("working points must be exactly loose, medium, and tight")
        if set(zz_ks_distances) != set(_WORKING_POINT_NAMES):
            raise ValueError("ZZ KS values must be exactly loose, medium, and tight")
        auc_value = _finite_float(weighted_auc, "weighted AUC")
        correlation = _finite_float(
            background_score_mass_correlation, "score-mass correlation"
        )
        points = _freeze_value(working_points)
        targets = {
            name: _finite_float(
                working_points[name]["target_background_efficiency"],
                f"{name} target background efficiency",
            )
            for name in _WORKING_POINT_NAMES
        }
        signal = {
            name: _finite_float(
                working_points[name]["signal_efficiency"],
                f"{name} signal efficiency",
            )
            for name in _WORKING_POINT_NAMES
        }
        distances = {
            name: _finite_float(zz_ks_distances[name], f"{name} ZZ mass KS")
            for name in _WORKING_POINT_NAMES
        }
        reasons: list[str] = []
        if auc_value < config.auc_floor:
            reasons.append("weighted_auc_below_floor")
        for name in _WORKING_POINT_NAMES:
            if distances[name] > config.ks_limit:
                reasons.append(f"{name}_zz_mass_ks_exceeds_limit")
        if config.require_signal_efficiency_above_background:
            for name in _WORKING_POINT_NAMES:
                if signal[name] <= targets[name]:
                    reasons.append(
                        f"{name}_signal_efficiency_not_above_background"
                    )
        return cls(
            coefficient=coefficient_value,
            weighted_auc=auc_value,
            background_score_mass_correlation=correlation,
            working_points=points,
            signal_efficiencies=MappingProxyType(signal),
            target_background_efficiencies=MappingProxyType(targets),
            zz_ks_distances=MappingProxyType(distances),
            eligibility_reasons=tuple(reasons),
            oof_scores=oof_scores.copy(deep=True),
        )


@dataclass(frozen=True)
class FlatnessSelection:
    results: tuple[FlatnessCandidateResult, ...]
    selected: FlatnessCandidateResult | None


@dataclass(frozen=True)
class SelectedFlatnessEvidence:
    coefficient: float
    model: Any
    oof_scores: pd.DataFrame
    test_scores: pd.DataFrame
    test_metrics: Mapping[str, object]
    working_points: Mapping[str, Mapping[str, object]]


@dataclass(frozen=True)
class FlatnessOutcome:
    selection: FlatnessSelection
    evidence: SelectedFlatnessEvidence | None


class OneShotTestGate:
    def __init__(self, loader: Callable[[], pd.DataFrame]):
        if not callable(loader):
            raise TypeError("test loader must be callable")
        self._loader = loader
        self._opened = False

    def open(self) -> pd.DataFrame:
        if self._opened:
            raise RuntimeError("held-out test was already opened")
        self._opened = True
        result = self._loader()
        if not isinstance(result, pd.DataFrame):
            raise TypeError("test loader must return a DataFrame")
        return result.copy(deep=True)


def _default_model_factory(**kwargs):
    from hep_ml.gradientboosting import UGradientBoostingClassifier

    return UGradientBoostingClassifier(**kwargs)


def _score_column(coefficient: float) -> str:
    return f"score_lambda_{coefficient:.1f}".replace(".", "p")


def build_flatness_model(
    config: DecorrelationConfig,
    coefficient: float,
    model_factory: Callable[..., Any] | None = None,
):
    from hep_ml.losses import KnnFlatnessLossFunction

    normalized = float(coefficient)
    if normalized not in config.coefficients:
        raise ValueError("flatness coefficient is not a frozen candidate")
    if tuple(config.features) != DROP_TOP4_FEATURES:
        raise ValueError("decorrelation features do not match DropTop4")

    loss = KnnFlatnessLossFunction(
        uniform_features=[config.flatness["uniform_feature"]],
        uniform_label=[config.flatness["uniform_label"]],
        n_neighbours=config.flatness["n_neighbours"],
        max_groups=config.flatness["max_groups"],
        power=config.flatness["power"],
        fl_coefficient=normalized,
        allow_wrong_signs=config.flatness["allow_wrong_signs"],
        random_state=config.model["random_seed"],
    )
    factory = model_factory or _default_model_factory
    return factory(
        loss=loss,
        n_estimators=config.model["n_estimators"],
        learning_rate=config.model["learning_rate"],
        max_depth=config.model["max_depth"],
        min_samples_leaf=config.model["min_samples_leaf"],
        subsample=config.model["subsample"],
        train_features=list(DROP_TOP4_FEATURES),
        random_state=config.model["random_seed"],
    )


def generate_flatness_oof(
    development: pd.DataFrame,
    config: DecorrelationConfig,
    coefficient: float,
    model_factory: Callable[..., Any] | None = None,
) -> pd.DataFrame:
    validate_development_frame(development)
    folds = assign_development_folds(development, folds=config.folds)
    score_column = _score_column(float(coefficient))
    scores = pd.Series(np.nan, index=development.index, dtype=float)
    model_columns = [*DROP_TOP4_FEATURES, "m4l"]

    for fold in range(config.folds):
        fit_mask = folds != fold
        evaluation_mask = folds == fold
        fitting = development.loc[fit_mask]
        evaluation = development.loc[evaluation_mask]
        weights = class_balanced_training_weights(fitting)
        model = build_flatness_model(
            config, coefficient, model_factory=model_factory
        )
        model.fit(
            fitting.loc[:, model_columns],
            fitting["label"],
            sample_weight=weights,
        )
        probabilities = np.asarray(
            model.predict_proba(evaluation.loc[:, model_columns]), dtype=float
        )
        if probabilities.shape != (len(evaluation), 2):
            raise ValueError("flatness model probabilities have an invalid shape")
        fold_scores = probabilities[:, 1]
        if not np.isfinite(fold_scores).all():
            raise ValueError("flatness model produced non-finite OOF scores")
        scores.loc[evaluation.index] = fold_scores

    if scores.isna().any() or not np.isfinite(scores.to_numpy()).all():
        raise RuntimeError("every development row must receive one finite OOF score")

    audit_columns = [
        "eventNumber",
        "channelNumber",
        "label",
        "split",
        "physical_weight",
        "m4l",
    ]
    output = development.loc[:, audit_columns].copy()
    output["development_fold"] = folds
    output[score_column] = scores
    return output.loc[development.index]


def evaluate_flatness_candidate(
    oof_scores: pd.DataFrame,
    config: DecorrelationConfig,
    *,
    coefficient: float,
) -> FlatnessCandidateResult:
    score_column = _score_column(float(coefficient))
    if score_column not in oof_scores:
        raise ValueError(f"OOF frame is missing {score_column}")
    scored = oof_scores.rename(columns={score_column: "oof_score"}).copy()
    points = build_working_points(scored, config.working_points)
    diagnostics = zz_mass_diagnostics(scored, "oof_score", points, config)
    background = scored.loc[scored["label"] == 0]
    distances = {
        name: values["inclusive_to_selected_ks_distance"]
        for name, values in diagnostics["working_points"].items()
    }
    if any(value is None for value in distances.values()):
        raise ValueError("every working point must select at least one ZZ event")
    weights = np.abs(scored["physical_weight"].to_numpy(dtype=float))
    return FlatnessCandidateResult.from_metrics(
        coefficient=coefficient,
        weighted_auc=float(
            roc_auc_score(
                scored["label"], scored["oof_score"], sample_weight=weights
            )
        ),
        background_score_mass_correlation=weighted_pearson(
            background["oof_score"],
            background["m4l"],
            background["physical_weight"],
        ),
        working_points=points,
        zz_ks_distances=distances,
        config=config,
        oof_scores=oof_scores,
    )


def select_flatness_candidate(
    results: Sequence[FlatnessCandidateResult],
) -> FlatnessSelection:
    normalized = tuple(results)
    if any(not isinstance(result, FlatnessCandidateResult) for result in normalized):
        raise TypeError("flatness results must contain candidate results")
    coefficients = [result.coefficient for result in normalized]
    if len(coefficients) != len(set(coefficients)):
        raise ValueError("flatness candidate coefficients must be unique")
    eligible = [result for result in normalized if not result.eligibility_reasons]
    selected = None
    if eligible:
        selected = min(
            eligible,
            key=lambda result: (
                -result.weighted_auc,
                max(result.zz_ks_distances.values()),
                result.coefficient,
            ),
        )
    return FlatnessSelection(results=normalized, selected=selected)


def run_development_study(
    development: pd.DataFrame,
    config: DecorrelationConfig,
    *,
    model_factory: Callable[..., Any] | None = None,
) -> FlatnessSelection:
    validate_development_frame(development)
    results = []
    for coefficient in config.coefficients:
        oof = generate_flatness_oof(
            development,
            config,
            coefficient,
            model_factory=model_factory,
        )
        results.append(
            evaluate_flatness_candidate(oof, config, coefficient=coefficient)
        )
    return select_flatness_candidate(results)


def fit_selected_and_score_test(
    development: pd.DataFrame,
    test_gate: OneShotTestGate,
    config: DecorrelationConfig,
    selection: FlatnessSelection,
) -> FlatnessOutcome:
    if not isinstance(selection, FlatnessSelection):
        raise TypeError("selection must be a FlatnessSelection")
    if selection.selected is None:
        return FlatnessOutcome(selection=selection, evidence=None)

    validate_development_frame(development)
    selected = selection.selected
    model_columns = [*DROP_TOP4_FEATURES, "m4l"]
    weights = class_balanced_training_weights(development)
    model = build_flatness_model(config, selected.coefficient)
    model.fit(
        development.loc[:, model_columns],
        development["label"],
        sample_weight=weights,
    )

    test = test_gate.open()
    if set(test.get("split", ())) != {"test"}:
        raise ValueError("held-out frame must contain only test rows")
    validate_mc_frame(pd.concat([development, test], axis=0, ignore_index=True))
    probabilities = np.asarray(
        model.predict_proba(test.loc[:, model_columns]), dtype=float
    )
    if probabilities.shape != (len(test), 2) or not np.isfinite(probabilities).all():
        raise ValueError("flatness model returned invalid test probabilities")
    test_scores = test.loc[
        :, [
            "eventNumber",
            "channelNumber",
            "label",
            "physical_weight",
            "m4l",
        ]
    ].copy()
    test_scores["score"] = probabilities[:, 1]
    diagnostics = zz_mass_diagnostics(
        test_scores, "score", selected.working_points, config
    )
    background = test_scores.loc[test_scores["label"] == 0]
    test_metrics = MappingProxyType(
        {
            "weighted_auc": float(
                roc_auc_score(
                    test_scores["label"],
                    test_scores["score"],
                    sample_weight=np.abs(test_scores["physical_weight"]),
                )
            ),
            "background_score_mass_correlation": weighted_pearson(
                background["score"],
                background["m4l"],
                background["physical_weight"],
            ),
            "zz_mass_diagnostics": _freeze_value(diagnostics),
        }
    )
    evidence = SelectedFlatnessEvidence(
        coefficient=selected.coefficient,
        model=model,
        oof_scores=selected.oof_scores.copy(deep=True),
        test_scores=test_scores.copy(deep=True),
        test_metrics=test_metrics,
        working_points=_freeze_value(selected.working_points),
    )
    return FlatnessOutcome(selection=selection, evidence=evidence)


def _finite_float(value: object, name: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be finite") from error
    if not np.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _freeze_value(value):
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_value(nested) for key, nested in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_value(nested) for nested in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(nested) for nested in value)
    return value
