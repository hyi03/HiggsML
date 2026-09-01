"""MC-only fixed-working-point and diagnostic evaluation utilities."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from .validation import weighted_ks_distance


_REQUIRED_SCORE_COLUMNS = frozenset({"label", "physical_weight"})
_SCORE_COLUMNS = ("score", "oof_score", "xgb_score")


def weighted_retention_threshold(scores, weights, target: float) -> float:
    """Return the score cut retaining at least ``target`` absolute weight.

    Scores are processed from high to low using a stable ordering.  Selecting
    with the returned score necessarily retains the full score tie.
    """
    score_values = np.asarray(scores, dtype=float)
    weight_values = np.asarray(weights, dtype=float)
    if score_values.ndim != 1 or weight_values.ndim != 1 or score_values.size == 0:
        raise ValueError("scores and weights must be non-empty one-dimensional arrays")
    if score_values.shape != weight_values.shape:
        raise ValueError("scores and weights must have matching shapes")
    if not np.isfinite(score_values).all() or not np.isfinite(weight_values).all():
        raise ValueError("scores and weights must be finite")
    if not isinstance(target, (int, float, np.number)) or isinstance(target, bool):
        raise ValueError("target must be between zero and one")
    target_value = float(target)
    if not 0.0 < target_value < 1.0:
        raise ValueError("target must be between zero and one")

    absolute_weights = np.abs(weight_values)
    total_weight = float(absolute_weights.sum())
    if total_weight <= 0.0:
        raise ValueError("weights must have positive total absolute weight")
    order = np.argsort(-score_values, kind="stable")
    cumulative = np.cumsum(absolute_weights[order], dtype=float)
    index = int(np.searchsorted(cumulative, target_value * total_weight, side="left"))
    return float(score_values[order[index]])


def build_working_points(
    oof_frame: pd.DataFrame, targets: Mapping[str, float]
) -> dict[str, dict[str, object]]:
    """Freeze score cuts from OOF ZZ (label 0) absolute physical weights only."""
    score_column = _validate_score_frame(oof_frame, "OOF")
    if not isinstance(targets, Mapping) or not targets:
        raise ValueError("working-point targets must be a non-empty mapping")
    background = oof_frame.loc[oof_frame["label"] == 0]
    if background.empty:
        raise ValueError("OOF frame must contain ZZ label-0 rows")

    points: dict[str, dict[str, object]] = {}
    for name, target in targets.items():
        if not isinstance(name, str) or not name:
            raise ValueError("working-point names must be non-empty strings")
        threshold = weighted_retention_threshold(
            background[score_column], background["physical_weight"], target
        )
        points[name] = _working_point_metrics(oof_frame, score_column, threshold, target)
    _validate_working_point_order(points)
    return points


def _validate_score_frame(frame: pd.DataFrame, name: str) -> str:
    if not isinstance(frame, pd.DataFrame):
        raise ValueError(f"{name} scores must be a DataFrame")
    score_column = _score_column(frame)
    missing = sorted(_REQUIRED_SCORE_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{name} score frame is missing columns: {missing}")
    if frame.empty:
        raise ValueError(f"{name} score frame must be non-empty")
    labels = frame["label"].to_numpy(dtype=int)
    if not set(labels) <= {0, 1}:
        raise ValueError(f"{name} score frame labels must be 0 or 1")
    values = frame[[score_column, "physical_weight"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"{name} score frame contains NaN or infinity")
    return score_column


def _score_column(frame: pd.DataFrame) -> str:
    available = [column for column in _SCORE_COLUMNS if column in frame.columns]
    if len(available) != 1:
        raise ValueError("score frame must contain exactly one score column")
    return available[0]


def _working_point_metrics(
    frame: pd.DataFrame, score_column: str, threshold: float, target: float
) -> dict[str, object]:
    selected = frame[score_column].to_numpy(dtype=float) >= threshold
    labels = frame["label"].to_numpy(dtype=int)
    physical = frame["physical_weight"].to_numpy(dtype=float)
    class_metrics = {
        "background": _class_yields(labels == 0, selected, physical),
        "signal": _class_yields(labels == 1, selected, physical),
    }
    return {
        "threshold": float(threshold),
        "target_background_efficiency": float(target),
        "achieved_background_efficiency": class_metrics["background"]["efficiency"],
        "signal_efficiency": class_metrics["signal"]["efficiency"],
        "background": class_metrics["background"],
        "signal": class_metrics["signal"],
    }


def _class_yields(mask: np.ndarray, selected: np.ndarray, physical: np.ndarray) -> dict[str, object]:
    class_weights = physical[mask]
    selected_weights = physical[mask & selected]
    total_absolute = float(np.abs(class_weights).sum())
    return {
        "raw_count": int(mask.sum()),
        "selected_raw_count": int((mask & selected).sum()),
        "signed_yield": float(class_weights.sum()),
        "selected_signed_yield": float(selected_weights.sum()),
        "absolute_yield": total_absolute,
        "selected_absolute_yield": float(np.abs(selected_weights).sum()),
        "efficiency": (
            float(np.abs(selected_weights).sum() / total_absolute)
            if total_absolute > 0.0
            else 0.0
        ),
    }


def _validate_working_point_order(points: Mapping[str, Mapping[str, object]]) -> None:
    if not points:
        raise ValueError("working points must not be empty")
    thresholds = []
    for name, point in points.items():
        try:
            threshold = float(point["threshold"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"working point {name} must contain a finite threshold") from error
        if not np.isfinite(threshold):
            raise ValueError(f"working point {name} must contain a finite threshold")
        thresholds.append(threshold)
    if {"loose", "medium", "tight"} <= set(points):
        thresholds = [
            float(points[name]["threshold"])
            for name in ("loose", "medium", "tight")
        ]
    if any(first > second for first, second in zip(thresholds, thresholds[1:])):
        raise ValueError("working-point thresholds must be monotonic")


def weighted_pearson(x, y, weights) -> float:
    """Calculate the absolute-physical-weighted Pearson correlation."""
    first = np.asarray(x, dtype=float)
    second = np.asarray(y, dtype=float)
    raw_weights = np.asarray(weights, dtype=float)
    if (
        first.ndim != 1
        or second.ndim != 1
        or raw_weights.ndim != 1
        or first.size == 0
    ):
        raise ValueError("Pearson inputs must be non-empty one-dimensional arrays")
    if first.shape != second.shape or first.shape != raw_weights.shape:
        raise ValueError("Pearson values and weights must have matching shapes")
    if not all(np.isfinite(values).all() for values in (first, second, raw_weights)):
        raise ValueError("Pearson inputs contain NaN or infinity")
    absolute = np.abs(raw_weights)
    total = float(absolute.sum())
    if total <= 0.0:
        raise ValueError("Pearson weights must have positive total absolute weight")
    first_centered = first - np.average(first, weights=absolute)
    second_centered = second - np.average(second, weights=absolute)
    first_variance = float(np.average(first_centered**2, weights=absolute))
    second_variance = float(np.average(second_centered**2, weights=absolute))
    if first_variance == 0.0 or second_variance == 0.0:
        return 0.0
    covariance = float(np.average(first_centered * second_centered, weights=absolute))
    return float(covariance / np.sqrt(first_variance * second_variance))


def evaluate_full_training(
    oof: pd.DataFrame,
    final_development: pd.DataFrame,
    test: pd.DataFrame,
    working_points: Mapping[str, Mapping[str, object]],
    policy,
    *,
    selection: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Evaluate a frozen full-MC model without recalibrating from final or test.

    ``working_points`` is an input contract: this function only applies its
    thresholds.  It never calls threshold selection on final-development or
    test predictions.  Optional selection metadata is passed separately so
    score tables retain only prediction-audit columns.
    """
    oof_score = _validate_evaluation_frame(oof, "OOF")
    development_score = _validate_evaluation_frame(final_development, "final development")
    test_score = _validate_evaluation_frame(test, "test")
    normalized_points = _validated_working_points(working_points, policy)

    oof_auc = _auc_metrics(oof, oof_score, "OOF")
    test_auc = _auc_metrics(test, test_score, "test")
    overfitting = _overfitting_metrics(oof, oof_score, test, test_score, policy, oof_auc, test_auc)
    evaluated_points: dict[str, dict[str, object]] = {}
    calibration_drift: dict[str, dict[str, float]] = {}
    for name, point in normalized_points.items():
        threshold = float(point["threshold"])
        target = float(point["target_background_efficiency"])
        oof_point = _working_point_metrics(oof, oof_score, threshold, target)
        development_point = _working_point_metrics(
            final_development, development_score, threshold, target
        )
        test_point = _working_point_metrics(test, test_score, threshold, target)
        evaluated_points[name] = {
            **oof_point,
            "final_development": development_point,
            "test": test_point,
        }
        calibration_drift[name] = {
            "background_efficiency_delta": float(
                development_point["achieved_background_efficiency"]
                - oof_point["achieved_background_efficiency"]
            ),
            "signal_efficiency_delta": float(
                development_point["signal_efficiency"] - oof_point["signal_efficiency"]
            ),
        }

    mass_sculpting = _mass_sculpting_metrics(
        oof, oof_score, test, test_score, normalized_points, policy
    )
    return {
        "selection": _selection_metadata(selection),
        "development_oof": oof_auc,
        "test": test_auc,
        "working_points": evaluated_points,
        "calibration_drift": calibration_drift,
        "overfitting": overfitting,
        "mass_sculpting": mass_sculpting,
    }


def _validate_evaluation_frame(frame: pd.DataFrame, name: str) -> str:
    score_column = _validate_score_frame(frame, name)
    if set(frame["label"].to_numpy(dtype=int)) != {0, 1}:
        raise ValueError(f"{name} score frame must contain labels 0 and 1")
    for label, class_name in ((0, "background"), (1, "signal")):
        absolute = float(
            np.abs(
                frame.loc[frame["label"] == label, "physical_weight"].to_numpy(dtype=float)
            ).sum()
        )
        if absolute <= 0.0:
            raise ValueError(f"{name} {class_name} must have positive absolute weight")
    if "m4l" not in frame.columns:
        raise ValueError(f"{name} score frame is missing columns: ['m4l']")
    if not np.isfinite(frame["m4l"].to_numpy(dtype=float)).all():
        raise ValueError(f"{name} score frame mass contains NaN or infinity")
    return score_column


def _validated_working_points(
    points: Mapping[str, Mapping[str, object]], policy
) -> dict[str, dict[str, float]]:
    if not isinstance(points, Mapping) or not points:
        raise ValueError("working points must be a non-empty mapping")
    if set(points) != set(policy.working_points):
        raise ValueError("working points must match the policy working-point names")
    normalized: dict[str, dict[str, float]] = {}
    for name in policy.working_points:
        point = points[name]
        if not isinstance(point, Mapping):
            raise ValueError(f"working point {name} must be a mapping")
        try:
            threshold = float(point["threshold"])
            target = float(point["target_background_efficiency"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"working point {name} is missing threshold metadata") from error
        if not np.isfinite(threshold):
            raise ValueError(f"working point {name} threshold must be finite")
        if target != float(policy.working_points[name]):
            raise ValueError(f"working point {name} target does not match policy")
        normalized[name] = {
            "threshold": threshold,
            "target_background_efficiency": target,
        }
    _validate_working_point_order(normalized)
    return normalized


def _auc_metrics(frame: pd.DataFrame, score_column: str, name: str) -> dict[str, float]:
    labels = frame["label"].to_numpy(dtype=int)
    scores = frame[score_column].to_numpy(dtype=float)
    weights = np.abs(frame["physical_weight"].to_numpy(dtype=float))
    return {
        "weighted_auc": float(roc_auc_score(labels, scores, sample_weight=weights)),
        "unweighted_auc": float(roc_auc_score(labels, scores)),
    }


def _overfitting_metrics(
    oof: pd.DataFrame,
    oof_score: str,
    test: pd.DataFrame,
    test_score: str,
    policy,
    oof_auc: Mapping[str, float],
    test_auc: Mapping[str, float],
) -> dict[str, object]:
    distances: dict[str, float] = {}
    for label, name in ((1, "signal"), (0, "background")):
        oof_class = oof.loc[oof["label"] == label]
        test_class = test.loc[test["label"] == label]
        distances[name] = weighted_ks_distance(
            oof_class[oof_score],
            test_class[test_score],
            oof_class["physical_weight"],
            test_class["physical_weight"],
        )
    auc_gap = float(oof_auc["weighted_auc"] - test_auc["weighted_auc"])
    reasons: list[str] = []
    if auc_gap > float(policy.auc_gap_limit):
        reasons.append("development_test_auc_gap")
    for name in ("signal", "background"):
        if distances[name] > float(policy.ks_distance_limit):
            reasons.append(f"{name}_ks_distance")
    return {
        "development_test_auc_gap": auc_gap,
        "signal_ks_distance": distances["signal"],
        "background_ks_distance": distances["background"],
        "warning": bool(reasons),
        "warning_reasons": reasons,
    }


def _selection_metadata(selection: Mapping[str, object] | None) -> dict[str, object]:
    if selection is None:
        return {"candidate": None, "final_tree_count": None}
    if not isinstance(selection, Mapping):
        raise ValueError("selection must be a mapping")
    candidate = selection.get("candidate")
    count = selection.get("final_tree_count")
    if candidate is not None and not isinstance(candidate, str):
        raise ValueError("selected candidate must be a string")
    if count is not None:
        if isinstance(count, bool) or not isinstance(count, (int, np.integer)) or count <= 0:
            raise ValueError("final tree count must be a positive integer")
        count = int(count)
    return {"candidate": candidate, "final_tree_count": count}


def _mass_sculpting_metrics(
    oof: pd.DataFrame,
    oof_score: str,
    test: pd.DataFrame,
    test_score: str,
    points: Mapping[str, Mapping[str, float]],
    policy,
) -> dict[str, object]:
    diagnostics = {
        "oof_zz": _zz_mass_diagnostics(oof, oof_score, points, policy),
        "test_zz": _zz_mass_diagnostics(test, test_score, points, policy),
    }
    reasons = _empty_selected_zz_reasons(diagnostics)
    reasons.extend(_excessive_mass_ks_reasons(diagnostics, policy.ks_distance_limit))
    reasons.extend(_nonfinite_paths(diagnostics))
    return {
        **_json_safe(diagnostics),
        "warning": bool(reasons),
        "warning_reasons": reasons,
    }


def zz_mass_diagnostics(
    frame: pd.DataFrame,
    score_column: str,
    points: Mapping[str, Mapping[str, object]],
    policy,
) -> dict[str, object]:
    """Return validated MC-only ZZ mass diagnostics for one scored frame."""
    validated_score = _validate_evaluation_frame(frame, "ZZ diagnostic")
    if score_column != validated_score:
        raise ValueError("ZZ diagnostic score column does not match the frame")
    normalized_points = _validated_working_points(points, policy)
    return _json_safe(_zz_mass_diagnostics(frame, score_column, normalized_points, policy))


def _zz_mass_diagnostics(
    frame: pd.DataFrame,
    score_column: str,
    points: Mapping[str, Mapping[str, float]],
    policy,
) -> dict[str, object]:
    zz = frame.loc[frame["label"] == 0]
    scores = zz[score_column].to_numpy(dtype=float)
    mass = zz["m4l"].to_numpy(dtype=float)
    weights = zz["physical_weight"].to_numpy(dtype=float)
    output: dict[str, object] = {
        "weighted_score_mass_correlation": weighted_pearson(scores, mass, weights),
        "working_points": {},
    }
    for name, point in points.items():
        selected = scores >= float(point["threshold"])
        inclusive, selected_yields = _mass_bin_yields(mass, weights, selected, policy.mass_bins_gev)
        if not selected.any():
            distance: float | None = None
        else:
            distance = weighted_ks_distance(mass, mass[selected], weights, weights[selected])
        output["working_points"][name] = {
            "inclusive_to_selected_ks_distance": distance,
            "mass_bins": [
                {
                    "lower_edge": float(lower),
                    "upper_edge": float(upper),
                    "inclusive_absolute_yield": float(all_yield),
                    "selected_absolute_yield": float(selected_yield),
                    "efficiency": float(selected_yield / all_yield)
                    if all_yield > 0.0
                    else 0.0,
                }
                for lower, upper, all_yield, selected_yield in zip(
                    policy.mass_bins_gev[:-1],
                    policy.mass_bins_gev[1:],
                    inclusive,
                    selected_yields,
                    strict=True,
                )
            ],
        }
    return output


def _mass_bin_yields(mass, weights, selected, bins) -> tuple[np.ndarray, np.ndarray]:
    absolute = np.abs(np.asarray(weights, dtype=float))
    edges = np.asarray(bins, dtype=float)
    inclusive = np.histogram(mass, bins=edges, weights=absolute)[0]
    selected_yields = np.histogram(mass[selected], bins=edges, weights=absolute[selected])[0]
    return inclusive, selected_yields


def _nonfinite_paths(value: object, prefix: str = "") -> list[str]:
    if isinstance(value, Mapping):
        output: list[str] = []
        for name, nested in value.items():
            output.extend(_nonfinite_paths(nested, f"{prefix}.{name}" if prefix else name))
        return output
    if isinstance(value, (list, tuple)):
        output = []
        for index, nested in enumerate(value):
            output.extend(_nonfinite_paths(nested, f"{prefix}[{index}]"))
        return output
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return [prefix]
    return []


def _empty_selected_zz_reasons(diagnostics: Mapping[str, object]) -> list[str]:
    reasons: list[str] = []
    for split_name in ("oof_zz", "test_zz"):
        split = diagnostics[split_name]
        for working_point, values in split["working_points"].items():
            if values["inclusive_to_selected_ks_distance"] is None:
                reasons.append(f"{split_name}.{working_point}.empty_selected_zz")
    return reasons


def _excessive_mass_ks_reasons(
    diagnostics: Mapping[str, object], limit: float
) -> list[str]:
    reasons: list[str] = []
    for split_name in ("oof_zz", "test_zz"):
        split = diagnostics[split_name]
        for working_point, values in split["working_points"].items():
            distance = values["inclusive_to_selected_ks_distance"]
            if distance is not None and np.isfinite(distance) and distance > float(limit):
                reasons.append(f"{split_name}.{working_point}.ks_distance")
    return reasons


def _json_safe(value: object):
    if isinstance(value, Mapping):
        return {name: _json_safe(nested) for name, nested in value.items()}
    if isinstance(value, list):
        return [_json_safe(nested) for nested in value]
    if isinstance(value, tuple):
        return [_json_safe(nested) for nested in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value
