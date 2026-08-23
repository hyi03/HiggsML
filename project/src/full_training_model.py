from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from .features import FEATURES
from .full_training_policy import (
    CandidateSpec,
    TrainingPolicy,
    _validated_training_weight_multipliers,
    assign_development_folds,
    class_balanced_training_weights,
    validate_mc_frame,
)


@dataclass(frozen=True)
class FoldMetric:
    fold: int
    weighted_auc: float
    unweighted_auc: float
    best_iteration: int


@dataclass(frozen=True)
class CandidateResult:
    candidate: CandidateSpec
    folds: tuple[FoldMetric, ...]
    mean_weighted_auc: float
    standard_error_weighted_auc: float


@dataclass(frozen=True)
class ModelSelectionResult:
    selected: CandidateResult
    candidates: tuple[CandidateResult, ...]
    oof_scores: pd.Series
    development_folds: pd.Series


ModelFactory = Callable[..., Any]


def choose_candidate(results: Sequence[CandidateResult]) -> CandidateResult:
    """Choose the simplest candidate in the best candidate's one-SE band."""
    normalized = tuple(results)
    _validate_candidate_results(normalized)
    best = max(normalized, key=lambda item: item.mean_weighted_auc)
    floor = best.mean_weighted_auc - best.standard_error_weighted_auc
    eligible = [item for item in normalized if item.mean_weighted_auc >= floor]
    return min(
        eligible,
        key=lambda item: (
            item.candidate.max_depth,
            -item.candidate.min_child_weight,
            item.candidate.name,
        ),
    )


def final_tree_count(result: CandidateResult) -> int:
    """Convert zero-based fold best iterations to one final tree count."""
    _validate_candidate_result(result)
    counts = np.asarray([metric.best_iteration + 1 for metric in result.folds])
    return max(1, int(np.rint(np.median(counts))))


def effective_parameters(
    selection: CandidateResult | ModelSelectionResult,
    policy: TrainingPolicy,
    *,
    final: bool = True,
) -> dict[str, object]:
    """Return the frozen classifier parameters for a candidate or selection."""
    candidate = selection.selected if isinstance(selection, ModelSelectionResult) else selection
    _validate_policy(policy)
    _validate_candidate_spec(candidate.candidate)
    parameters = dict(policy.common_parameters)
    parameters.update(
        {
            "max_depth": candidate.candidate.max_depth,
            "min_child_weight": candidate.candidate.min_child_weight,
            "random_state": policy.random_seed,
            "n_jobs": policy.n_jobs,
        }
    )
    if final:
        parameters["n_estimators"] = final_tree_count(candidate)
        parameters.pop("early_stopping_rounds", None)
    return parameters


def cross_validate_candidates(
    frame: pd.DataFrame,
    policy: TrainingPolicy,
    model_factory: ModelFactory | None = None,
    *,
    training_weight_multipliers: pd.Series | None = None,
    features: Sequence[object] = FEATURES,
) -> ModelSelectionResult:
    """Fit every frozen candidate on deterministic development folds only."""
    _validate_policy(policy)
    validated_features = validate_model_features(features)
    if not frame.index.is_unique:
        raise ValueError("cross-validation requires a unique DataFrame index")
    validated_multipliers = _validated_training_weight_multipliers(
        frame, training_weight_multipliers
    )
    development_folds = assign_development_folds(frame, folds=policy.folds)
    development_index = development_folds.index
    development = frame.loc[development_index]
    factory = _default_model_factory if model_factory is None else model_factory
    candidate_results: list[CandidateResult] = []
    oof_by_candidate: dict[str, pd.Series] = {}

    for candidate in policy.candidates:
        fold_metrics: list[FoldMetric] = []
        oof_scores = pd.Series(np.nan, index=development_index, dtype=float)
        for fold in range(policy.folds):
            fitting = development.loc[development_folds != fold]
            evaluation = development.loc[development_folds == fold]
            if fitting.empty or evaluation.empty:
                raise ValueError(f"development fold {fold} has no fitting or evaluation rows")
            fitting_multipliers = (
                None
                if validated_multipliers is None
                else validated_multipliers.loc[fitting.index]
            )
            fitting_weights = class_balanced_training_weights(
                fitting, multipliers=fitting_multipliers
            )
            evaluation_weights = np.abs(
                evaluation["physical_weight"].to_numpy(dtype=float)
            )
            parameters = effective_parameters(
                _candidate_placeholder(candidate), policy, final=False
            )
            classifier = factory(**parameters)
            classifier.fit(
                fitting.loc[:, validated_features],
                fitting["label"],
                sample_weight=fitting_weights,
                eval_set=[(evaluation.loc[:, validated_features], evaluation["label"])],
                sample_weight_eval_set=[evaluation_weights],
                verbose=False,
            )
            scores = score_model(classifier, evaluation, features=validated_features)
            if len(scores) != len(evaluation):
                raise ValueError("classifier returned the wrong number of evaluation scores")
            if not np.isfinite(scores).all():
                raise ValueError("classifier returned non-finite evaluation scores")
            if oof_scores.loc[evaluation.index].notna().any():
                raise ValueError("out-of-fold predictions overlap")
            oof_scores.loc[evaluation.index] = scores
            fold_metrics.append(
                FoldMetric(
                    fold=fold,
                    weighted_auc=float(
                        roc_auc_score(
                            evaluation["label"], scores, sample_weight=evaluation_weights
                        )
                    ),
                    unweighted_auc=float(roc_auc_score(evaluation["label"], scores)),
                    best_iteration=_best_iteration(classifier),
                )
            )
        if oof_scores.isna().any() or not oof_scores.index.equals(development_index):
            raise ValueError("out-of-fold predictions must cover every development event exactly once")
        weighted_aucs = np.asarray(
            [metric.weighted_auc for metric in fold_metrics], dtype=float
        )
        result = CandidateResult(
            candidate=candidate,
            folds=tuple(fold_metrics),
            mean_weighted_auc=float(weighted_aucs.mean()),
            standard_error_weighted_auc=float(
                weighted_aucs.std(ddof=1) / np.sqrt(policy.folds)
            ),
        )
        _validate_candidate_result(result)
        candidate_results.append(result)
        oof_by_candidate[candidate.name] = oof_scores

    candidates = tuple(candidate_results)
    selected = choose_candidate(candidates)
    selected_oof = oof_by_candidate[selected.candidate.name].copy()
    selected_oof.name = "oof_score"
    return ModelSelectionResult(
        selected=selected,
        candidates=candidates,
        oof_scores=selected_oof,
        development_folds=development_folds.copy(),
    )


def fit_final_model(
    frame: pd.DataFrame,
    selection: ModelSelectionResult,
    policy: TrainingPolicy,
    model_factory: ModelFactory | None = None,
    *,
    training_weight_multipliers: pd.Series | None = None,
    features: Sequence[object] = FEATURES,
) -> Any:
    """Fit the selected fixed-size model on all development rows, never test rows."""
    _validate_policy(policy)
    validated_features = validate_model_features(features)
    validate_mc_frame(frame)
    _validate_candidate_result(selection.selected)
    validated_multipliers = _validated_training_weight_multipliers(
        frame, training_weight_multipliers
    )
    development = frame.loc[frame["split"] != "test"]
    development_multipliers = (
        None
        if validated_multipliers is None
        else validated_multipliers.loc[development.index]
    )
    weights = class_balanced_training_weights(
        development, multipliers=development_multipliers
    )
    factory = _default_model_factory if model_factory is None else model_factory
    classifier = factory(**effective_parameters(selection, policy, final=True))
    classifier.fit(
        development.loc[:, validated_features],
        development["label"],
        sample_weight=weights,
        verbose=False,
    )
    return classifier


def score_model(
    model: Any, frame: pd.DataFrame, *, features: Sequence[object] = FEATURES
) -> np.ndarray:
    """Score a frame with the validated ordered model-feature tuple."""
    validated_features = validate_model_features(features)
    scores = _positive_class_scores(
        model.predict_proba(frame.loc[:, validated_features])
    )
    if len(scores) != len(frame):
        raise ValueError("classifier returned the wrong number of scores")
    if not np.isfinite(scores).all():
        raise ValueError("classifier returned non-finite scores")
    return scores


def validate_model_features(features: Sequence[object]) -> tuple[str, ...]:
    """Validate an ordered, non-empty subset of the frozen model features."""
    try:
        selected = tuple(features)
    except TypeError as error:
        raise ValueError("model features must be an iterable") from error
    if not selected:
        raise ValueError("model features must be non-empty")
    if any(not isinstance(feature, str) for feature in selected):
        raise ValueError("model features must be strings")
    if len(set(selected)) != len(selected):
        raise ValueError("model features must be unique")
    if any(feature not in FEATURES for feature in selected):
        raise ValueError("model features must be an ordered subset of FEATURES")
    return selected


def _candidate_placeholder(candidate: CandidateSpec) -> CandidateResult:
    """Provide a candidate-shaped value for common parameter construction."""
    return CandidateResult(candidate, (), 0.0, 0.0)


def _default_model_factory(**parameters: object) -> Any:
    try:
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise RuntimeError("install requirements.txt before training") from exc
    except Exception as exc:
        if "libomp" in str(exc).lower():
            raise RuntimeError(
                "XGBoost requires the OpenMP runtime on macOS; "
                "install it with `brew install libomp`, then retry"
            ) from exc
        raise
    return XGBClassifier(**parameters)


def _positive_class_scores(predicted: object) -> np.ndarray:
    values = np.asarray(predicted, dtype=float)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("classifier predict_proba must return two class probabilities")
    return values[:, 1]


def _best_iteration(classifier: Any) -> int:
    value = getattr(classifier, "best_iteration", None)
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 0:
        raise ValueError("classifier best_iteration must be a non-negative integer")
    return int(value)


def _validate_policy(policy: TrainingPolicy) -> None:
    if policy.folds != 5:
        raise ValueError("policy must use exactly five folds")
    if len(policy.candidates) != 6:
        raise ValueError("policy must define exactly six candidates")
    names = [candidate.name for candidate in policy.candidates]
    if len(set(names)) != len(names):
        raise ValueError("policy candidates must have unique names")
    for candidate in policy.candidates:
        _validate_candidate_spec(candidate)


def _validate_candidate_results(results: tuple[CandidateResult, ...]) -> None:
    if len(results) != 6:
        raise ValueError("candidate selection requires exactly six candidates")
    names = [result.candidate.name for result in results]
    if len(set(names)) != len(names):
        raise ValueError("candidate results must have unique candidate names")
    for result in results:
        _validate_candidate_result(result)


def _validate_candidate_result(result: CandidateResult) -> None:
    _validate_candidate_spec(result.candidate)
    if len(result.folds) != 5:
        raise ValueError("candidate result must contain exactly five folds")
    fold_numbers = [metric.fold for metric in result.folds]
    if set(fold_numbers) != set(range(5)):
        if len(set(fold_numbers)) != len(fold_numbers):
            raise ValueError("candidate fold numbers must be unique")
        raise ValueError("candidate fold numbers must be 0 through 4")
    for metric in result.folds:
        _validate_fold_metric(metric)
    _validate_auc(result.mean_weighted_auc, "mean weighted AUC")
    standard_error = result.standard_error_weighted_auc
    if not isinstance(standard_error, (int, float, np.number)) or not np.isfinite(standard_error):
        raise ValueError("standard error weighted AUC must be finite")
    if standard_error < 0:
        raise ValueError("standard error weighted AUC must be non-negative")


def _validate_candidate_spec(candidate: CandidateSpec) -> None:
    if not isinstance(candidate.name, str) or not candidate.name:
        raise ValueError("candidate name must be non-empty")
    if isinstance(candidate.max_depth, bool) or not isinstance(candidate.max_depth, (int, np.integer)) or candidate.max_depth <= 0:
        raise ValueError("candidate max_depth must be a positive integer")
    child_weight = candidate.min_child_weight
    if not isinstance(child_weight, (int, float, np.number)) or not np.isfinite(child_weight) or child_weight <= 0:
        raise ValueError("candidate min_child_weight must be finite and positive")


def _validate_fold_metric(metric: FoldMetric) -> None:
    if isinstance(metric.fold, bool) or not isinstance(metric.fold, (int, np.integer)):
        raise ValueError("fold number must be an integer")
    _validate_auc(metric.weighted_auc, "weighted AUC")
    _validate_auc(metric.unweighted_auc, "unweighted AUC")
    if (
        isinstance(metric.best_iteration, bool)
        or not isinstance(metric.best_iteration, (int, np.integer))
        or metric.best_iteration < 0
    ):
        raise ValueError("best_iteration must be a non-negative integer")


def _validate_auc(value: object, name: str) -> None:
    if not isinstance(value, (int, float, np.number)) or not np.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{name} must be between zero and one")
