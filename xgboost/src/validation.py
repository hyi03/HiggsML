from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def asimov_significance(signal: float, background: float) -> float:
    if signal <= 0 or background <= 0:
        return 0.0
    return float(
        np.sqrt(2 * ((signal + background) * np.log1p(signal / background) - signal))
    )


def weighted_ks_distance(
    values_a,
    values_b,
    weights_a=None,
    weights_b=None,
) -> float:
    """Maximum distance between two weighted empirical CDFs.

    Absolute weights are used because a signed-weight cumulative sum is not a
    probability distribution and therefore cannot define a KS distance.
    """

    first = np.asarray(values_a, dtype=float)
    second = np.asarray(values_b, dtype=float)
    if first.ndim != 1 or second.ndim != 1 or first.size == 0 or second.size == 0:
        raise ValueError("KS samples must be non-empty one-dimensional arrays")

    first_weights = (
        np.ones(first.size, dtype=float)
        if weights_a is None
        else np.abs(np.asarray(weights_a, dtype=float))
    )
    second_weights = (
        np.ones(second.size, dtype=float)
        if weights_b is None
        else np.abs(np.asarray(weights_b, dtype=float))
    )
    if first_weights.shape != first.shape or second_weights.shape != second.shape:
        raise ValueError("KS values and weights must have matching shapes")
    if not all(
        np.isfinite(values).all()
        for values in (first, second, first_weights, second_weights)
    ):
        raise ValueError("KS inputs contain NaN or infinity")
    if first_weights.sum() <= 0 or second_weights.sum() <= 0:
        raise ValueError("KS samples must have positive total absolute weight")

    first_order = np.argsort(first, kind="stable")
    second_order = np.argsort(second, kind="stable")
    first_sorted = first[first_order]
    second_sorted = second[second_order]
    first_cumulative = np.concatenate(
        ([0.0], np.cumsum(first_weights[first_order], dtype=float))
    )
    second_cumulative = np.concatenate(
        ([0.0], np.cumsum(second_weights[second_order], dtype=float))
    )
    points = np.unique(np.concatenate((first_sorted, second_sorted)))
    first_indices = np.searchsorted(first_sorted, points, side="right")
    second_indices = np.searchsorted(second_sorted, points, side="right")
    first_cdf = first_cumulative[first_indices] / first_cumulative[-1]
    second_cdf = second_cumulative[second_indices] / second_cumulative[-1]
    return float(np.max(np.abs(first_cdf - second_cdf)))


def optimize_threshold(
    labels,
    scores,
    physical_weights,
    threshold_grid: Iterable[float] | None = None,
) -> dict[str, object]:
    labels = np.asarray(labels, dtype=int)
    scores = np.asarray(scores, dtype=float)
    weights = np.asarray(physical_weights, dtype=float)
    if labels.shape != scores.shape or labels.shape != weights.shape:
        raise ValueError("labels, scores, and physical weights must have matching shapes")
    if not np.isfinite(scores).all() or not np.isfinite(weights).all():
        raise ValueError("threshold inputs contain NaN or infinity")

    thresholds = (
        np.linspace(0.05, 0.95, 91)
        if threshold_grid is None
        else np.asarray(list(threshold_grid), dtype=float)
    )
    if thresholds.size == 0 or not np.isfinite(thresholds).all():
        raise ValueError("threshold grid must contain finite values")

    best = {
        "best_threshold": float(thresholds[0]),
        "expected_signal": 0.0,
        "expected_background": 0.0,
        "asimov_significance": 0.0,
    }
    scan = []
    for threshold in thresholds:
        selected = scores >= threshold
        signal = float(weights[selected & (labels == 1)].sum())
        background = float(weights[selected & (labels == 0)].sum())
        significance = asimov_significance(signal, background)
        scan.append(
            {
                "threshold": float(threshold),
                "signal": signal,
                "background": background,
                "signal_over_background": signal / background if background > 0 else None,
                "asimov_significance": significance,
            }
        )
        if significance > best["asimov_significance"]:
            best = {
                "best_threshold": float(threshold),
                "expected_signal": signal,
                "expected_background": background,
                "asimov_significance": significance,
            }
    return {**best, "threshold_scan": scan}


def _auc_metrics(frame, split: str) -> tuple[float, float]:
    from sklearn.metrics import roc_auc_score

    subset = frame[frame["split"] == split]
    if set(subset["label"].unique()) != {0, 1}:
        raise ValueError(f"{split} split must contain both signal and background")
    weighted = roc_auc_score(
        subset["label"],
        subset["xgb_score"],
        sample_weight=np.abs(subset["physical_weight"]),
    )
    unweighted = roc_auc_score(subset["label"], subset["xgb_score"])
    return float(weighted), float(unweighted)


def evaluate_scored_events(
    frame,
    *,
    threshold_grid: Iterable[float] | None = None,
    auc_gap_limit: float = 0.05,
    ks_distance_limit: float = 0.10,
) -> dict[str, object]:
    required = {"split", "label", "xgb_score", "physical_weight"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"scored event table is missing columns: {sorted(missing)}")
    if not np.isfinite(
        frame[["xgb_score", "physical_weight"]].to_numpy(dtype=float)
    ).all():
        raise ValueError("scored event table contains NaN or infinity")

    aucs = {}
    for split in ("train", "validation", "test"):
        aucs[split] = _auc_metrics(frame, split)

    validation = frame[frame["split"] == "validation"]
    optimum = optimize_threshold(
        validation["label"],
        validation["xgb_score"],
        validation["physical_weight"],
        threshold_grid,
    )
    threshold = float(optimum["best_threshold"])
    test = frame[frame["split"] == "test"]
    selected_test = test["xgb_score"].to_numpy(dtype=float) >= threshold
    test_labels = test["label"].to_numpy(dtype=int)
    test_weights = test["physical_weight"].to_numpy(dtype=float)
    test_signal = float(test_weights[selected_test & (test_labels == 1)].sum())
    test_background = float(test_weights[selected_test & (test_labels == 0)].sum())
    test_significance = asimov_significance(test_signal, test_background)

    train = frame[frame["split"] == "train"]
    ks_distances = {}
    for label, name in ((1, "signal"), (0, "background")):
        train_class = train[train["label"] == label]
        test_class = test[test["label"] == label]
        ks_distances[name] = weighted_ks_distance(
            train_class["xgb_score"],
            test_class["xgb_score"],
            train_class["physical_weight"],
            test_class["physical_weight"],
        )

    train_test_auc_gap = aucs["train"][0] - aucs["test"][0]
    warning_reasons = []
    if train_test_auc_gap > auc_gap_limit:
        warning_reasons.append("train_test_auc_gap")
    if ks_distances["signal"] > ks_distance_limit:
        warning_reasons.append("signal_ks_distance")
    if ks_distances["background"] > ks_distance_limit:
        warning_reasons.append("background_ks_distance")

    return {
        "threshold_selection_split": "validation",
        "best_threshold": threshold,
        "train_auc": aucs["train"][0],
        "validation_auc": aucs["validation"][0],
        "test_auc": aucs["test"][0],
        "train_unweighted_auc": aucs["train"][1],
        "validation_unweighted_auc": aucs["validation"][1],
        "test_unweighted_auc": aucs["test"][1],
        "weighted_auc": aucs["test"][0],
        "unweighted_auc": aucs["test"][1],
        "train_test_auc_gap": train_test_auc_gap,
        "validation_test_auc_gap": aucs["validation"][0] - aucs["test"][0],
        "signal_ks_distance": ks_distances["signal"],
        "background_ks_distance": ks_distances["background"],
        "auc_gap_limit": float(auc_gap_limit),
        "ks_distance_limit": float(ks_distance_limit),
        "overfitting_warning": bool(warning_reasons),
        "overfitting_warning_reasons": warning_reasons,
        "validation_expected_signal": float(optimum["expected_signal"]),
        "validation_expected_background": float(optimum["expected_background"]),
        "validation_asimov_significance": float(optimum["asimov_significance"]),
        "expected_signal": test_signal,
        "expected_background": test_background,
        "asimov_significance": test_significance,
        "threshold_scan": optimum["threshold_scan"],
    }
