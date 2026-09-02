from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

from src.config import InputBindingError
from src.training.config import TrainingProtocol
from src.training.dataset import ValidatedDevelopment


OOF_COLUMNS = (
    "target_lambda", "source_sample", "source_entry", "fold_index", "label", "m4l",
    "physical_weight", "train_weight", "score",
)


def validate_candidate_oof(
    frame: pd.DataFrame,
    development: ValidatedDevelopment,
    folds: np.ndarray,
    *,
    target_lambda: float,
) -> None:
    if tuple(frame.columns) != OOF_COLUMNS or len(frame) != len(development.frame):
        raise InputBindingError("candidate OOF schema or row count changed")
    expected = development.frame
    if not np.array_equal(frame["target_lambda"].to_numpy(), np.full(len(frame), target_lambda)):
        raise InputBindingError("candidate OOF lambda binding changed")
    if not np.array_equal(frame["fold_index"].to_numpy(), folds):
        raise InputBindingError("candidate OOF fold binding changed")
    for column in ("source_sample", "source_entry", "label", "m4l", "physical_weight", "train_weight"):
        if not np.array_equal(frame[column].to_numpy(), expected[column].to_numpy()):
            raise InputBindingError(f"candidate OOF field changed: {column}")
    identities = tuple(zip(frame["source_sample"], frame["source_entry"], strict=True))
    if len(set(identities)) != len(identities):
        raise InputBindingError("candidate OOF identity is not unique")
    scores = frame["score"].to_numpy(dtype=np.float64)
    if not np.isfinite(scores).all() or np.any(scores < 0.0) or np.any(scores > 1.0):
        raise InputBindingError("candidate OOF score must be finite in [0, 1]")


def weighted_auc(labels: Iterable[int], scores: Iterable[float], weights: Iterable[float]) -> float:
    label_values = np.asarray(labels)
    score_values = np.asarray(scores, dtype=np.float64)
    weight_values = np.asarray(weights, dtype=np.float64)
    if (
        label_values.ndim != 1
        or score_values.shape != label_values.shape
        or weight_values.shape != label_values.shape
        or set(label_values.tolist()) != {0, 1}
        or not np.isfinite(score_values).all()
        or not np.isfinite(weight_values).all()
        or np.any(weight_values < 0)
        or weight_values[label_values == 0].sum() <= 0
        or weight_values[label_values == 1].sum() <= 0
    ):
        raise InputBindingError("weighted AUC inputs are invalid")
    result = float(roc_auc_score(label_values, score_values, sample_weight=weight_values))
    if not np.isfinite(result) or not 0.0 <= result <= 1.0:
        raise RuntimeError("weighted AUC returned an invalid metric")
    return result


def weighted_roc_points(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    required = {"label", "score", "train_weight"}
    if not required.issubset(frame.columns):
        raise InputBindingError("weighted ROC inputs are invalid")
    labels = frame["label"].to_numpy()
    scores = frame["score"].to_numpy(dtype=np.float64)
    weights = frame["train_weight"].to_numpy(dtype=np.float64)
    weighted_auc(labels, scores, weights)
    false_positive, true_positive, _ = roc_curve(labels, scores, sample_weight=weights)
    if not np.isfinite(false_positive).all() or not np.isfinite(true_positive).all():
        raise RuntimeError("weighted ROC returned invalid points")
    return false_positive, true_positive


def weighted_ks_distance(
    first_values: Iterable[float],
    second_values: Iterable[float],
    first_weights: Iterable[float],
    second_weights: Iterable[float],
) -> float:
    first = np.asarray(first_values, dtype=np.float64)
    second = np.asarray(second_values, dtype=np.float64)
    weight_a = np.abs(np.asarray(first_weights, dtype=np.float64))
    weight_b = np.abs(np.asarray(second_weights, dtype=np.float64))
    if (
        first.ndim != 1
        or second.ndim != 1
        or first.size == 0
        or second.size == 0
        or weight_a.shape != first.shape
        or weight_b.shape != second.shape
        or not all(np.isfinite(values).all() for values in (first, second, weight_a, weight_b))
        or weight_a.sum() <= 0
        or weight_b.sum() <= 0
    ):
        raise InputBindingError("weighted KS inputs are invalid")
    first_order = np.argsort(first, kind="stable")
    second_order = np.argsort(second, kind="stable")
    first_sorted = first[first_order]
    second_sorted = second[second_order]
    first_cumulative = np.concatenate(([0.0], np.cumsum(weight_a[first_order], dtype=np.float64)))
    second_cumulative = np.concatenate(([0.0], np.cumsum(weight_b[second_order], dtype=np.float64)))
    points = np.unique(np.concatenate((first_sorted, second_sorted)))
    first_cdf = first_cumulative[np.searchsorted(first_sorted, points, side="right")] / first_cumulative[-1]
    second_cdf = second_cumulative[np.searchsorted(second_sorted, points, side="right")] / second_cumulative[-1]
    return float(np.max(np.abs(first_cdf - second_cdf)))


def working_point_metrics(frame: pd.DataFrame, *, target: float) -> dict[str, float]:
    labels = frame["label"].to_numpy(dtype=np.int64)
    scores = frame["score"].to_numpy(dtype=np.float64)
    absolute = np.abs(frame["physical_weight"].to_numpy(dtype=np.float64))
    masses = frame["m4l"].to_numpy(dtype=np.float64)
    background = labels == 0
    signal = labels == 1
    if (
        type(target) is not float
        or not 0.0 < target < 1.0
        or not np.any(background)
        or not np.any(signal)
        or set(labels.tolist()) != {0, 1}
        or not np.isfinite(scores).all()
        or not np.isfinite(absolute).all()
        or not np.isfinite(masses).all()
        or absolute[background].sum() <= 0
        or absolute[signal].sum() <= 0
    ):
        raise InputBindingError("working-point inputs are invalid")
    order = np.argsort(-scores[background], kind="stable")
    background_scores = scores[background][order]
    background_weights = absolute[background][order]
    cumulative = np.cumsum(background_weights, dtype=np.float64)
    index = int(np.searchsorted(cumulative, target * cumulative[-1], side="left"))
    threshold = float(background_scores[index])
    selected = scores >= threshold
    achieved_background = float(absolute[background & selected].sum() / absolute[background].sum())
    signal_efficiency = float(absolute[signal & selected].sum() / absolute[signal].sum())
    ks = weighted_ks_distance(
        frame.loc[background, "m4l"],
        frame.loc[background & selected, "m4l"],
        frame.loc[background, "physical_weight"],
        frame.loc[background & selected, "physical_weight"],
    )
    return {
        "threshold": threshold,
        "target_background_efficiency": target,
        "achieved_background_efficiency": achieved_background,
        "signal_efficiency": signal_efficiency,
        "ks": ks,
    }


def frozen_working_point_metrics(
    frame: pd.DataFrame, *, target: float, threshold: float
) -> dict[str, float | bool]:
    if (
        type(threshold) is not float
        or not np.isfinite(threshold)
        or not 0.0 <= threshold <= 1.0
    ):
        raise InputBindingError("frozen threshold is invalid")
    labels = frame["label"].to_numpy(dtype=np.int64)
    scores = frame["score"].to_numpy(dtype=np.float64)
    absolute = np.abs(frame["physical_weight"].to_numpy(dtype=np.float64))
    masses = frame["m4l"].to_numpy(dtype=np.float64)
    background, signal = labels == 0, labels == 1
    if (
        type(target) is not float
        or not 0.0 < target < 1.0
        or set(labels.tolist()) != {0, 1}
        or not np.isfinite(scores).all()
        or np.any(scores < 0.0)
        or np.any(scores > 1.0)
        or not np.isfinite(absolute).all()
        or not np.isfinite(masses).all()
        or absolute[background].sum() <= 0
        or absolute[signal].sum() <= 0
    ):
        raise InputBindingError("frozen working-point inputs are invalid")
    selected = scores >= threshold
    achieved = float(absolute[background & selected].sum() / absolute[background].sum())
    signal_efficiency = float(absolute[signal & selected].sum() / absolute[signal].sum())
    selected_background = background & selected
    empty_selected_background = absolute[selected_background].sum() <= 0
    if empty_selected_background:
        ks = 1.0
    else:
        ks = weighted_ks_distance(
            masses[background],
            masses[selected_background],
            absolute[background],
            absolute[selected_background],
        )
    return {
        "threshold": threshold,
        "target_background_efficiency": target,
        "achieved_background_efficiency": achieved,
        "signal_efficiency": signal_efficiency,
        "ks": ks,
        "empty_selected_background": bool(empty_selected_background),
    }


def evaluate_candidate(frame: pd.DataFrame, protocol: TrainingProtocol) -> dict[str, Any]:
    candidate_lambda = float(frame["target_lambda"].iloc[0])
    auc = weighted_auc(frame["label"], frame["score"], frame["train_weight"])
    points = {
        name: working_point_metrics(frame, target=target)
        for name, target in protocol.working_points
    }
    reasons = qualification_reasons(auc, points, protocol)
    return {
        "target_lambda": candidate_lambda,
        "weighted_oof_auc": auc,
        "working_points": points,
        "eligible": not reasons,
        "rejection_reasons": reasons,
    }


def qualification_reasons(
    auc: float, points: dict[str, dict[str, float]], protocol: TrainingProtocol
) -> list[str]:
    required_fields = {
        "threshold", "target_background_efficiency", "achieved_background_efficiency",
        "signal_efficiency", "ks",
    }
    if (
        not np.isfinite(auc)
        or tuple(points) != tuple(name for name, _ in protocol.working_points)
        or any(set(point) != required_fields for point in points.values())
        or any(
            not all(np.isfinite(float(value)) for value in point.values())
            for point in points.values()
        )
    ):
        raise InputBindingError("qualification inputs changed")
    minimum_auc = float(protocol.raw["qualification"]["auc_minimum"])
    maximum_ks = float(protocol.raw["qualification"]["ks_maximum"])
    reasons: list[str] = []
    if auc < minimum_auc:
        reasons.append("auc_below_minimum")
    for name, point in points.items():
        if point["ks"] > maximum_ks:
            reasons.append(f"{name}_ks_above_maximum")
        if point["signal_efficiency"] <= point["achieved_background_efficiency"]:
            reasons.append(f"{name}_signal_efficiency_not_greater")
    return reasons


def select_candidate(candidates: list[dict[str, Any]], protocol: TrainingProtocol) -> dict[str, Any] | None:
    if [item.get("target_lambda") for item in candidates] != list(protocol.target_lambdas):
        raise InputBindingError("candidate set or order changed")
    if any(
        type(item.get("eligible")) is not bool
        or not np.isfinite(float(item.get("weighted_oof_auc", np.nan)))
        for item in candidates
    ):
        raise InputBindingError("candidate metric changed")
    eligible = [item for item in candidates if item.get("eligible") is True]
    if not eligible:
        return None
    best_auc = max(float(item["weighted_oof_auc"]) for item in eligible)
    tolerance = float(protocol.raw["qualification"]["auc_tie_atol"])
    tied = [item for item in eligible if abs(float(item["weighted_oof_auc"]) - best_auc) <= tolerance]
    return min(tied, key=lambda item: float(item["target_lambda"]))
