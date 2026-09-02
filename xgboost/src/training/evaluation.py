"""Frozen OOF working-point, efficiency, AUC, and ZZ mass-KS semantics."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from ..validation import weighted_ks_distance


OOF_COLUMNS = (
    "channelNumber", "eventNumber", "split", "label", "physical_weight", "m4l",
    "development_fold", "oof_score",
)


def validate_oof_frame(frame: pd.DataFrame, *, require_both_labels: bool = True) -> None:
    if tuple(frame.columns) != OOF_COLUMNS:
        raise ValueError("OOF frame must match the frozen eight-column schema")
    if frame.empty or not frame.index.is_unique:
        raise ValueError("OOF frame must be non-empty with a unique index")
    if frame.duplicated(["channelNumber", "eventNumber"]).any():
        raise ValueError("each development event must appear exactly once in OOF")
    labels = set(frame["label"])
    if set(frame["split"]) != {"train", "validation"} or (
        labels != {0, 1} if require_both_labels else not labels.issubset({0, 1})
    ):
        raise ValueError("OOF frame has invalid split or label values")
    numeric = frame.loc[:, [name for name in OOF_COLUMNS if name != "split"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("OOF frame contains NaN or infinity")


def weighted_oof_auc(frame: pd.DataFrame) -> float:
    validate_oof_frame(frame)
    return float(
        roc_auc_score(
            frame["label"], frame["oof_score"],
            sample_weight=np.abs(frame["physical_weight"].to_numpy(dtype=float)),
        )
    )


def weighted_retention_threshold(scores, weights, target: float) -> float:
    score_values = np.asarray(scores, dtype=float)
    weight_values = np.asarray(weights, dtype=float)
    if score_values.ndim != 1 or weight_values.ndim != 1 or score_values.size == 0:
        raise ValueError("scores and weights must be non-empty one-dimensional arrays")
    if score_values.shape != weight_values.shape:
        raise ValueError("scores and weights must have matching shapes")
    if not np.isfinite(score_values).all() or not np.isfinite(weight_values).all():
        raise ValueError("scores and weights must be finite")
    if isinstance(target, bool) or not isinstance(target, (int, float, np.number)):
        raise ValueError("target must be between zero and one")
    target_value = float(target)
    if not 0.0 < target_value < 1.0:
        raise ValueError("target must be between zero and one")
    absolute = np.abs(weight_values)
    total = float(absolute.sum())
    if total <= 0.0:
        raise ValueError("weights must have positive total absolute weight")
    order = np.argsort(-score_values, kind="stable")
    cumulative = np.cumsum(absolute[order], dtype=float)
    index = int(np.searchsorted(cumulative, target_value * total, side="left"))
    return float(score_values[order[index]])


def _class_yields(mask: np.ndarray, selected: np.ndarray, physical: np.ndarray) -> dict[str, object]:
    weights = physical[mask]
    selected_weights = physical[mask & selected]
    total_absolute = float(np.abs(weights).sum())
    selected_absolute = float(np.abs(selected_weights).sum())
    return {
        "raw_count": int(mask.sum()),
        "selected_raw_count": int((mask & selected).sum()),
        "signed_yield": float(weights.sum()),
        "selected_signed_yield": float(selected_weights.sum()),
        "absolute_yield": total_absolute,
        "selected_absolute_yield": selected_absolute,
        "efficiency": selected_absolute / total_absolute if total_absolute > 0.0 else 0.0,
    }


def _working_point_metrics(frame: pd.DataFrame, threshold: float, target: float) -> dict[str, object]:
    selected = frame["oof_score"].to_numpy(dtype=float) >= threshold
    labels = frame["label"].to_numpy(dtype=int)
    physical = frame["physical_weight"].to_numpy(dtype=float)
    background = _class_yields(labels == 0, selected, physical)
    signal = _class_yields(labels == 1, selected, physical)
    return {
        "threshold": float(threshold),
        "target_background_efficiency": float(target),
        "achieved_background_efficiency": background["efficiency"],
        "signal_efficiency": signal["efficiency"],
        "background": background,
        "signal": signal,
    }


def build_working_points(
    oof_frame: pd.DataFrame, targets: Mapping[str, float]
) -> dict[str, dict[str, object]]:
    validate_oof_frame(oof_frame, require_both_labels=False)
    if tuple(targets) != ("loose", "medium", "tight"):
        raise ValueError("working points must be ordered loose, medium, tight")
    background = oof_frame.loc[oof_frame["label"] == 0]
    if background.empty:
        raise ValueError("OOF frame must contain ZZ label-0 rows")
    points: dict[str, dict[str, object]] = {}
    for name, target in targets.items():
        threshold = weighted_retention_threshold(
            background["oof_score"], background["physical_weight"], target
        )
        points[name] = _working_point_metrics(oof_frame, threshold, target)
    thresholds = [float(points[name]["threshold"]) for name in points]
    if not thresholds[0] <= thresholds[1] <= thresholds[2]:
        raise ValueError("working-point thresholds must be ordered loose <= medium <= tight")
    return points


def background_mass_ks(
    frame: pd.DataFrame, points: Mapping[str, Mapping[str, object]]
) -> dict[str, float | None]:
    validate_oof_frame(frame)
    background = frame.loc[frame["label"] == 0]
    output: dict[str, float | None] = {}
    for name, point in points.items():
        selected = background.loc[background["oof_score"] >= float(point["threshold"])]
        output[name] = (
            None
            if selected.empty
            else weighted_ks_distance(
                background["m4l"], selected["m4l"],
                background["physical_weight"], selected["physical_weight"],
            )
        )
    return output
