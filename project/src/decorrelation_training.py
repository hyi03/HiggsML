from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
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

ModelFactory = Callable[..., Any]
_WORKING_POINT_NAMES = ("loose", "medium", "tight")
_MASS_BINS_GEV = (105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160)


@dataclass(frozen=True)
class _MetricPolicy:
    working_points: Mapping[str, float]
    mass_bins_gev: tuple[int, ...] = _MASS_BINS_GEV


@dataclass(frozen=True)
class FlatnessCandidateResult:
    coefficient: float
    weighted_auc: float
    background_score_mass_correlation: float
    working_points: Mapping[str, Mapping[str, object]]
    achieved_background_efficiencies: Mapping[str, float]
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
    ) -> FlatnessCandidateResult:
        coefficient_value = _finite_number(coefficient, "coefficient")
        if coefficient_value not in config.coefficients:
            raise ValueError("coefficient must match an approved flatness value")
        auc_value = _unit_interval(weighted_auc, "weighted AUC")
        correlation_value = _finite_number(
            background_score_mass_correlation,
            "background score-mass correlation",
        )
        if not -1.0 <= correlation_value <= 1.0:
            raise ValueError("background score-mass correlation must be between -1 and 1")
        points = _validated_working_points(working_points, config)
        distances = _validated_efficiency_mapping(
            zz_ks_distances, "ZZ mass KS distances"
        )
        audit = _validated_oof_audit(oof_scores, coefficient_value)
        achieved = {
            name: _unit_interval(
                points[name]["achieved_background_efficiency"],
                f"{name} achieved background efficiency",
            )
            for name in _WORKING_POINT_NAMES
        }
        signal = {
            name: _unit_interval(
                points[name]["signal_efficiency"],
                f"{name} signal efficiency",
            )
            for name in _WORKING_POINT_NAMES
        }
        targets = {
            name: _unit_interval(
                points[name]["target_background_efficiency"],
                f"{name} target background efficiency",
            )
            for name in _WORKING_POINT_NAMES
        }
        reasons: list[str] = []
        if auc_value < float(config.auc_floor):
            reasons.append("weighted_auc_below_floor")
        for name in _WORKING_POINT_NAMES:
            if distances[name] > float(config.ks_limit):
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
            background_score_mass_correlation=correlation_value,
            working_points=_freeze_value(points),
            achieved_background_efficiencies=_freeze_value(achieved),
            signal_efficiencies=_freeze_value(signal),
            target_background_efficiencies=_freeze_value(targets),
            zz_ks_distances=_freeze_value(distances),
            eligibility_reasons=tuple(reasons),
            oof_scores=audit.copy(deep=True),
        )


@dataclass(frozen=True)
class FlatnessSelection:
    results: tuple[FlatnessCandidateResult, ...]
    selected: FlatnessCandidateResult | None

    def __post_init__(self) -> None:
        results = tuple(self.results)
        if any(not isinstance(result, FlatnessCandidateResult) for result in results):
            raise ValueError("flatness selection results must be candidate results")
        coefficients = tuple(result.coefficient for result in results)
        if len(coefficients) != len(set(coefficients)):
            raise ValueError("flatness selection coefficients must be unique")
        selected_index = None
        if self.selected is not None:
            if self.selected.eligibility_reasons:
                raise ValueError("selected flatness candidate must be eligible")
            selected_index = next(
                (
                    index
                    for index, result in enumerate(results)
                    if result is self.selected
                ),
                None,
            )
            if selected_index is None:
                raise ValueError("selected flatness candidate must be one of the results")
        snapshots = tuple(_snapshot_candidate(result) for result in results)
        object.__setattr__(self, "results", snapshots)
        object.__setattr__(
            self,
            "selected",
            None if selected_index is None else snapshots[selected_index],
        )


@dataclass(frozen=True)
class SelectedFlatnessEvidence:
    candidate: FlatnessCandidateResult
    model: Any
    test_scores: pd.DataFrame
    test_weighted_auc: float
    test_background_score_mass_correlation: float
    working_points: Mapping[str, Mapping[str, object]]
    test_working_points: Mapping[str, Mapping[str, object]]
    test_background_efficiencies: Mapping[str, float]
    test_signal_efficiencies: Mapping[str, float]
    test_zz_ks_distances: Mapping[str, float | None]
    test_zz_diagnostics: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate", _snapshot_candidate(self.candidate))
        object.__setattr__(self, "test_scores", self.test_scores.copy(deep=True))
        for name in (
            "working_points",
            "test_working_points",
            "test_background_efficiencies",
            "test_signal_efficiencies",
            "test_zz_ks_distances",
            "test_zz_diagnostics",
        ):
            object.__setattr__(self, name, _freeze_value(getattr(self, name)))


@dataclass(frozen=True)
class FlatnessOutcome:
    selection: FlatnessSelection
    evidence: SelectedFlatnessEvidence | None


class OneShotTestGate:
    def __init__(self, loader: Callable[[], pd.DataFrame]):
        if not callable(loader):
            raise ValueError("test loader must be callable")
        self._loader = loader
        self._opened = False

    def open(self) -> pd.DataFrame:
        if self._opened:
            raise RuntimeError("held-out test has already opened")
        self._opened = True
        frame = self._loader()
        if not isinstance(frame, pd.DataFrame):
            raise ValueError("held-out test loader must return a DataFrame")
        return frame.copy(deep=True)


def _default_model_factory(**kwargs):
    try:
        from hep_ml.gradientboosting import UGradientBoostingClassifier
    except ImportError as exc:
        raise RuntimeError("install requirements.txt before training") from exc
    return UGradientBoostingClassifier(**kwargs)


def build_flatness_model(
    config: DecorrelationConfig,
    coefficient: float,
    model_factory: ModelFactory | None = None,
) -> Any:
    if coefficient not in config.coefficients:
        raise ValueError("coefficient must match an approved flatness value")
    if config.features != DROP_TOP4_FEATURES:
        raise ValueError("decorrelation config must retain the approved DropTop4 features")
    try:
        from hep_ml.losses import KnnFlatnessLossFunction
    except ImportError as exc:
        raise RuntimeError("install requirements.txt before training") from exc
    loss = KnnFlatnessLossFunction(
        uniform_features=[str(config.flatness["uniform_feature"])],
        uniform_label=[int(config.flatness["uniform_label"])],
        n_neighbours=int(config.flatness["n_neighbours"]),
        max_groups=int(config.flatness["max_groups"]),
        power=float(config.flatness["power"]),
        fl_coefficient=float(coefficient),
        allow_wrong_signs=bool(config.flatness["allow_wrong_signs"]),
    )
    factory = _default_model_factory if model_factory is None else model_factory
    return factory(
        loss=loss,
        n_estimators=300,
        learning_rate=0.05,
        max_depth=3,
        min_samples_leaf=50,
        subsample=0.8,
        train_features=list(DROP_TOP4_FEATURES),
        random_state=42,
    )


def generate_flatness_oof(
    development: pd.DataFrame,
    config: DecorrelationConfig,
    coefficient: float,
    model_factory: ModelFactory | None = None,
) -> pd.DataFrame:
    if not development.index.is_unique:
        raise ValueError("out-of-fold scoring requires a unique DataFrame index")
    validate_development_frame(development)
    development_folds = assign_development_folds(development, folds=config.folds)
    fitting_columns = [*DROP_TOP4_FEATURES, "m4l"]
    score_column = _score_column_name(coefficient)
    scores = pd.Series(np.nan, index=development_folds.index, dtype=float, name=score_column)

    for fold in range(config.folds):
        fitting = development.loc[development_folds != fold]
        evaluation = development.loc[development_folds == fold]
        if fitting.empty or evaluation.empty:
            raise ValueError(f"development fold {fold} has no fitting or evaluation rows")
        model = build_flatness_model(
            config, coefficient, model_factory=model_factory
        )
        weights = class_balanced_training_weights(fitting)
        model.fit(
            fitting.loc[:, fitting_columns],
            fitting["label"],
            sample_weight=weights,
        )
        fold_scores = _positive_class_probabilities(model.predict_proba(evaluation.loc[:, fitting_columns]))
        if len(fold_scores) != len(evaluation):
            raise ValueError("classifier returned the wrong number of evaluation scores")
        if scores.loc[evaluation.index].notna().any():
            raise ValueError("out-of-fold predictions overlap")
        scores.loc[evaluation.index] = fold_scores

    if scores.isna().any() or not scores.index.equals(development_folds.index):
        raise ValueError(
            "out-of-fold predictions must cover every development event exactly once"
        )
    columns = [
        "eventNumber",
        "channelNumber",
        "split",
        "label",
        "physical_weight",
        "m4l",
    ]
    output = development.loc[development_folds.index, columns].copy(deep=True)
    output["development_fold"] = development_folds.loc[output.index].to_numpy(dtype=int)
    output[score_column] = scores.loc[output.index].to_numpy(dtype=float)
    return output


def evaluate_flatness_candidate(
    scored_oof: pd.DataFrame,
    config: DecorrelationConfig,
    *,
    coefficient: float,
) -> FlatnessCandidateResult:
    """Evaluate one coefficient using absolute-physical-weighted OOF metrics."""
    coefficient_value = _finite_number(coefficient, "coefficient")
    score_column = _score_column_name(coefficient_value)
    if not isinstance(scored_oof, pd.DataFrame) or score_column not in scored_oof:
        raise ValueError(f"OOF audit must contain {score_column}")
    normalized = scored_oof.rename(columns={score_column: "oof_score"}).copy(deep=True)
    points = build_working_points(normalized, config.working_points)
    policy = _MetricPolicy(config.working_points)
    diagnostics = zz_mass_diagnostics(normalized, "oof_score", points, policy)
    background = normalized.loc[normalized["label"] == 0]
    distances = {
        name: values["inclusive_to_selected_ks_distance"]
        for name, values in diagnostics["working_points"].items()
    }
    return FlatnessCandidateResult.from_metrics(
        coefficient=coefficient_value,
        weighted_auc=float(
            roc_auc_score(
                normalized["label"],
                normalized["oof_score"],
                sample_weight=np.abs(
                    normalized["physical_weight"].to_numpy(dtype=float)
                ),
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
        oof_scores=scored_oof,
    )


def select_flatness_candidate(
    results: Iterable[FlatnessCandidateResult],
) -> FlatnessSelection:
    normalized = tuple(results)
    if any(not isinstance(result, FlatnessCandidateResult) for result in normalized):
        raise ValueError("flatness results must contain candidate results")
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
) -> FlatnessSelection:
    """Run the five frozen candidates using development rows only."""
    validate_development_frame(development)
    results = tuple(
        evaluate_flatness_candidate(
            generate_flatness_oof(development, config, coefficient),
            config,
            coefficient=coefficient,
        )
        for coefficient in config.coefficients
    )
    return select_flatness_candidate(results)


def fit_selected_and_score_test(
    development: pd.DataFrame,
    test_gate: OneShotTestGate,
    config: DecorrelationConfig,
    selection: FlatnessSelection,
) -> FlatnessOutcome:
    """Fit and test the selected candidate once, without any reselection."""
    if not isinstance(selection, FlatnessSelection):
        raise ValueError("selection must be a FlatnessSelection")
    if selection.selected is None:
        return FlatnessOutcome(selection=selection, evidence=None)

    validate_development_frame(development)
    candidate = selection.selected
    model = build_flatness_model(config, candidate.coefficient)
    fitting_columns = [*DROP_TOP4_FEATURES, "m4l"]
    model.fit(
        development.loc[:, fitting_columns],
        development["label"],
        sample_weight=class_balanced_training_weights(development),
    )

    test = test_gate.open()
    if test.empty or "split" not in test or set(test["split"]) != {"test"}:
        raise ValueError("held-out test frame must contain only test rows")
    validate_mc_frame(pd.concat([development, test], ignore_index=True))
    scores = _positive_class_probabilities(
        model.predict_proba(test.loc[:, fitting_columns])
    )
    test_scores = test.loc[
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
    test_scores["score"] = scores
    test_points = _apply_frozen_working_points(
        test_scores, "score", candidate.working_points, config
    )
    diagnostics = zz_mass_diagnostics(
        test_scores,
        "score",
        candidate.working_points,
        _MetricPolicy(config.working_points),
    )
    background = test_scores.loc[test_scores["label"] == 0]
    evidence = SelectedFlatnessEvidence(
        candidate=candidate,
        model=model,
        test_scores=test_scores,
        test_weighted_auc=float(
            roc_auc_score(
                test_scores["label"],
                test_scores["score"],
                sample_weight=np.abs(
                    test_scores["physical_weight"].to_numpy(dtype=float)
                ),
            )
        ),
        test_background_score_mass_correlation=weighted_pearson(
            background["score"],
            background["m4l"],
            background["physical_weight"],
        ),
        working_points=candidate.working_points,
        test_working_points=test_points,
        test_background_efficiencies={
            name: float(point["achieved_background_efficiency"])
            for name, point in test_points.items()
        },
        test_signal_efficiencies={
            name: float(point["signal_efficiency"])
            for name, point in test_points.items()
        },
        test_zz_ks_distances={
            name: (
                None
                if values["inclusive_to_selected_ks_distance"] is None
                else float(values["inclusive_to_selected_ks_distance"])
            )
            for name, values in diagnostics["working_points"].items()
        },
        test_zz_diagnostics=diagnostics,
    )
    return FlatnessOutcome(selection=selection, evidence=evidence)


def _validated_working_points(
    points: Mapping[str, Mapping[str, object]],
    config: DecorrelationConfig,
) -> dict[str, dict[str, object]]:
    if not isinstance(points, Mapping) or set(points) != set(_WORKING_POINT_NAMES):
        raise ValueError("working points must be exactly loose, medium, and tight")
    normalized: dict[str, dict[str, object]] = {}
    for name in _WORKING_POINT_NAMES:
        point = points[name]
        if not isinstance(point, Mapping):
            raise ValueError(f"working point {name} must be a mapping")
        required = {
            "threshold",
            "target_background_efficiency",
            "achieved_background_efficiency",
            "signal_efficiency",
        }
        if not required <= set(point):
            raise ValueError(f"working point {name} is missing efficiency metadata")
        threshold = _finite_number(point["threshold"], f"{name} threshold")
        target = _unit_interval(
            point["target_background_efficiency"],
            f"{name} target background efficiency",
        )
        if target != float(config.working_points[name]):
            raise ValueError(f"working point {name} target does not match config")
        normalized[name] = dict(point)
        normalized[name]["threshold"] = threshold
        normalized[name]["target_background_efficiency"] = target
    thresholds = [float(normalized[name]["threshold"]) for name in _WORKING_POINT_NAMES]
    if any(first > second for first, second in zip(thresholds, thresholds[1:])):
        raise ValueError("working-point thresholds must be monotonic")
    return normalized


def _validated_efficiency_mapping(
    values: Mapping[str, object], name: str
) -> dict[str, float]:
    if not isinstance(values, Mapping) or set(values) != set(_WORKING_POINT_NAMES):
        raise ValueError(f"{name} must be exactly loose, medium, and tight")
    return {
        point_name: _unit_interval(values[point_name], f"{point_name} {name}")
        for point_name in _WORKING_POINT_NAMES
    }


def _validated_oof_audit(
    frame: pd.DataFrame, coefficient: float
) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("OOF audit must be a non-empty DataFrame")
    required = {
        "label",
        "physical_weight",
        "m4l",
        _score_column_name(coefficient),
    }
    missing = sorted(required - set(frame))
    if missing:
        raise ValueError(f"OOF audit is missing columns: {missing}")
    if not frame.index.is_unique:
        raise ValueError("OOF audit requires a unique DataFrame index")
    try:
        values = frame[
            ["label", "physical_weight", "m4l", _score_column_name(coefficient)]
        ].to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("OOF audit metric columns must be numeric") from error
    if not np.isfinite(values).all():
        raise ValueError("OOF audit contains NaN or infinity")
    return frame.copy(deep=True)


def _apply_frozen_working_points(
    frame: pd.DataFrame,
    score_column: str,
    frozen_points: Mapping[str, Mapping[str, object]],
    config: DecorrelationConfig,
) -> dict[str, dict[str, object]]:
    points = _validated_working_points(frozen_points, config)
    labels = frame["label"].to_numpy(dtype=int)
    physical = frame["physical_weight"].to_numpy(dtype=float)
    scores = frame[score_column].to_numpy(dtype=float)
    output: dict[str, dict[str, object]] = {}
    for name in _WORKING_POINT_NAMES:
        threshold = float(points[name]["threshold"])
        selected = scores >= threshold
        background = _class_efficiency_metrics(labels == 0, selected, physical)
        signal = _class_efficiency_metrics(labels == 1, selected, physical)
        output[name] = {
            "threshold": threshold,
            "target_background_efficiency": float(config.working_points[name]),
            "achieved_background_efficiency": background["efficiency"],
            "signal_efficiency": signal["efficiency"],
            "background": background,
            "signal": signal,
        }
    return output


def _class_efficiency_metrics(
    mask: np.ndarray, selected: np.ndarray, physical: np.ndarray
) -> dict[str, object]:
    class_weights = physical[mask]
    selected_weights = physical[mask & selected]
    total = float(np.abs(class_weights).sum())
    if total <= 0.0:
        raise ValueError("each test class must have positive absolute weight")
    selected_total = float(np.abs(selected_weights).sum())
    return {
        "raw_count": int(mask.sum()),
        "selected_raw_count": int((mask & selected).sum()),
        "signed_yield": float(class_weights.sum()),
        "selected_signed_yield": float(selected_weights.sum()),
        "absolute_yield": total,
        "selected_absolute_yield": selected_total,
        "efficiency": float(selected_total / total),
    }


def _snapshot_candidate(result: FlatnessCandidateResult) -> FlatnessCandidateResult:
    return replace(
        result,
        working_points=_freeze_value(result.working_points),
        achieved_background_efficiencies=_freeze_value(
            result.achieved_background_efficiencies
        ),
        signal_efficiencies=_freeze_value(result.signal_efficiencies),
        target_background_efficiencies=_freeze_value(
            result.target_background_efficiencies
        ),
        zz_ks_distances=_freeze_value(result.zz_ks_distances),
        oof_scores=result.oof_scores.copy(deep=True),
    )


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


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name} must be finite")
    normalized = float(value)
    if not np.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _unit_interval(value: object, name: str) -> float:
    normalized = _finite_number(value, name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{name} must be between zero and one")
    return normalized


def _positive_class_probabilities(predicted: object) -> np.ndarray:
    values = np.asarray(predicted, dtype=float)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("classifier predict_proba must return two class probabilities")
    if not np.isfinite(values).all():
        raise ValueError("classifier returned non-finite evaluation scores")
    scores = values[:, 1]
    return scores


def _score_column_name(coefficient: float) -> str:
    return f"score_lambda_{str(float(coefficient)).replace('.', 'p')}"
