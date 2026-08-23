"""Frozen, deterministic MC-only plots for the full-training workflow."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURES


PLOT_NAMES = (
    "roc_curve.png",
    "score_distributions.png",
    "cv_stability.png",
    "feature_importance.png",
    "mc_mass_sculpting.png",
    "mc_mass_signal_background.png",
    "mc_mass_working_points.png",
)
_SCORE_COLUMNS = ("score", "oof_score", "xgb_score")
_FIXED_MASS_RANGE_GEV = (105.0, 160.0)


def save_full_training_plots(
    oof_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    cv_results: Sequence[object],
    model: object,
    working_points: Mapping[str, Mapping[str, object]],
    policy: object,
    output_dir: str | Path,
) -> None:
    """Save exactly seven MC-only diagnostic figures beneath ``output_dir``.

    Validation deliberately precedes the lazy matplotlib import: these plots
    must never be reached by real-data rows or a data split.
    """
    oof_score = _validate_mc_score_frame(oof_frame, "OOF")
    test_score = _validate_mc_score_frame(test_frame, "test")
    thresholds = _validated_thresholds(working_points, policy)
    _validate_cv_results(cv_results, policy)
    importances = _validated_feature_importances(model)
    bins = _validated_mass_bins(policy)
    destination = _prepare_output_dir(output_dir)

    pyplot, roc_curve, auc = _plotting_dependencies()
    _save_roc(pyplot, roc_curve, auc, test_frame, test_score, destination)
    _save_score_distributions(pyplot, oof_frame, oof_score, test_frame, test_score, destination)
    _save_cv_stability(pyplot, cv_results, destination)
    _save_feature_importance(pyplot, importances, destination)
    _save_mass_sculpting(
        pyplot, oof_frame, oof_score, test_frame, test_score, thresholds, bins, destination
    )
    _save_mass_signal_background(
        pyplot, oof_frame, oof_score, test_frame, test_score, bins, destination
    )
    _save_mass_working_points(
        pyplot,
        oof_frame,
        oof_score,
        test_frame,
        test_score,
        thresholds,
        bins,
        destination,
    )


def _validate_mc_score_frame(frame: pd.DataFrame, name: str) -> str:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError(f"{name} MC frame must be a non-empty DataFrame")
    if "split" in frame.columns and not frame["split"].isin(
        ("train", "validation", "test")
    ).all():
        raise ValueError(f"{name} MC frame must not contain a non-MC split")
    required = {"label", "physical_weight", "m4l"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name} MC frame is missing columns: {missing}")
    labels = frame["label"].to_numpy(dtype=int)
    if set(labels) != {0, 1}:
        raise ValueError(f"{name} MC frame labels must be exactly 0 and 1")
    score_columns = [column for column in _SCORE_COLUMNS if column in frame.columns]
    if len(score_columns) != 1:
        raise ValueError(f"{name} MC frame must contain exactly one score column")
    numeric = frame[[score_columns[0], "physical_weight", "m4l"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError(f"{name} MC frame values must be finite")
    for label, class_name in ((0, "ZZ"), (1, "Higgs")):
        if float(np.abs(frame.loc[frame["label"] == label, "physical_weight"]).sum()) <= 0.0:
            raise ValueError(f"{name} MC {class_name} must have positive absolute weight")
    return score_columns[0]


def _validated_thresholds(points: Mapping[str, Mapping[str, object]], policy: object) -> dict[str, float]:
    expected = tuple(policy.working_points)
    if not isinstance(points, Mapping) or set(points) != set(expected):
        raise ValueError("MC working points must match the policy")
    thresholds: dict[str, float] = {}
    for name in expected:
        try:
            threshold = float(points[name]["threshold"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"MC working point {name} needs a finite threshold") from error
        if not np.isfinite(threshold):
            raise ValueError(f"MC working point {name} needs a finite threshold")
        thresholds[name] = threshold
    if any(first > second for first, second in zip(thresholds.values(), list(thresholds.values())[1:])):
        raise ValueError("MC working-point thresholds must be monotonic")
    return thresholds


def _validate_cv_results(cv_results: Sequence[object], policy: object) -> None:
    if len(cv_results) != 6 or len(policy.candidates) != 6:
        raise ValueError("MC CV stability requires exactly six candidates")
    expected_names = [candidate.name for candidate in policy.candidates]
    if [result.candidate.name for result in cv_results] != expected_names:
        raise ValueError("MC CV results must use the frozen candidate order")
    for result in cv_results:
        folds = tuple(result.folds)
        if len(folds) != policy.folds or {metric.fold for metric in folds} != set(range(policy.folds)):
            raise ValueError("MC CV results must contain five folds")
        values = np.asarray([metric.weighted_auc for metric in folds], dtype=float)
        if not np.isfinite(values).all() or np.any((values < 0.0) | (values > 1.0)):
            raise ValueError("MC CV weighted AUC values must be finite and bounded")


def _validated_feature_importances(model: object) -> np.ndarray:
    try:
        values = np.asarray(model.feature_importances_, dtype=float)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("MC model must expose feature_importances_") from error
    if values.shape != (len(FEATURES),) or not np.isfinite(values).all():
        raise ValueError("MC model feature importances must match frozen FEATURES")
    return values


def _validated_mass_bins(policy: object) -> np.ndarray:
    bins = np.asarray(policy.mass_bins_gev, dtype=float)
    if bins.ndim != 1 or bins.size < 2 or not np.isfinite(bins).all() or np.any(np.diff(bins) <= 0):
        raise ValueError("MC mass bins must be finite and strictly increasing")
    if (bins[0], bins[-1]) != _FIXED_MASS_RANGE_GEV:
        raise ValueError("MC mass bins must span the fixed 105--160 GeV range")
    return bins


def _prepare_output_dir(output_dir: str | Path) -> Path:
    destination = Path(output_dir)
    if destination.is_symlink():
        raise ValueError("MC plot output_dir must not be a symlink")
    if destination.exists() and not destination.is_dir():
        raise ValueError("MC plot output_dir must be a directory")
    destination.mkdir(parents=True, exist_ok=True)
    resolved = destination.resolve()
    for name in PLOT_NAMES:
        target = destination / name
        if target.exists() or target.is_symlink():
            raise ValueError(f"MC plot target already exists: {target}")
        if target.parent.resolve() != resolved:
            raise ValueError("MC plot output path must remain inside output_dir")
    return destination


def _plotting_dependencies():
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as pyplot
    from sklearn.metrics import auc, roc_curve

    return pyplot, roc_curve, auc


def _save_roc(pyplot, roc_curve, auc, frame, score_column, output_dir: Path) -> None:
    labels = frame["label"].to_numpy(dtype=int)
    scores = frame[score_column].to_numpy(dtype=float)
    weights = np.abs(frame["physical_weight"].to_numpy(dtype=float))
    false_positive, true_positive, _ = roc_curve(labels, scores, sample_weight=weights)
    figure, axis = pyplot.subplots(figsize=(6.4, 4.8))
    axis.plot(false_positive, true_positive, label=f"MC weighted ROC (AUC = {auc(false_positive, true_positive):.3f})")
    axis.plot([0, 1], [0, 1], "--", color="0.5", label="Unweighted random baseline")
    axis.set(title="Test MC ROC curve", xlabel="ZZ MC false-positive rate", ylabel="Higgs MC true-positive rate")
    axis.legend(loc="lower right")
    _save_and_close(figure, output_dir / "roc_curve.png")


def _save_score_distributions(pyplot, oof, oof_score, test, test_score, output_dir: Path) -> None:
    figure, axes = pyplot.subplots(1, 2, figsize=(10.0, 4.8), sharey=True)
    for axis, frame, score_column, split_name in zip(axes, (oof, test), (oof_score, test_score), ("OOF", "Test"), strict=True):
        for label, name, color in ((0, "ZZ", "tab:blue"), (1, "Higgs", "tab:orange")):
            subset = frame.loc[frame["label"] == label]
            axis.hist(subset[score_column], bins=np.linspace(0.0, 1.0, 21), weights=np.abs(subset["physical_weight"]), histtype="step", linewidth=1.8, color=color, label=f"{name} MC (absolute physical weight)")
        axis.set(title=f"{split_name} MC score distribution", xlabel="XGBoost score", ylabel="MC absolute physical yield")
        axis.legend()
    _save_and_close(figure, output_dir / "score_distributions.png")


def _save_cv_stability(pyplot, cv_results, output_dir: Path) -> None:
    figure, axis = pyplot.subplots(figsize=(8.0, 4.8))
    for result in cv_results:
        folds = sorted(result.folds, key=lambda metric: metric.fold)
        axis.plot([metric.fold + 1 for metric in folds], [metric.weighted_auc for metric in folds], marker="o", label=f"{result.candidate.name} MC")
    axis.set(title="MC cross-validation stability", xlabel="Development fold", ylabel="Weighted MC AUC", xticks=range(1, 6), ylim=(0.0, 1.0))
    axis.legend(ncol=2, fontsize="small")
    _save_and_close(figure, output_dir / "cv_stability.png")


def _save_feature_importance(pyplot, importances, output_dir: Path) -> None:
    figure, axis = pyplot.subplots(figsize=(8.0, 6.4))
    indices = np.arange(len(FEATURES))
    axis.barh(indices, importances, color="tab:green")
    axis.set(title="Full-model MC feature importance", xlabel="Unweighted XGBoost feature importance", yticks=indices, yticklabels=FEATURES)
    axis.invert_yaxis()
    _save_and_close(figure, output_dir / "feature_importance.png")


def _save_mass_sculpting(pyplot, oof, oof_score, test, test_score, thresholds, bins, output_dir: Path) -> None:
    figure, axes = pyplot.subplots(1, 2, figsize=(12.0, 4.8), sharey=True)
    for axis, frame, score_column, split_name in zip(axes, (oof, test), (oof_score, test_score), ("OOF", "Test"), strict=True):
        zz = frame.loc[frame["label"] == 0]
        weights = np.abs(zz["physical_weight"])
        axis.hist(zz["m4l"], bins=bins, weights=weights, histtype="step", linewidth=1.8, label="Inclusive ZZ MC")
        for name, threshold in thresholds.items():
            selected = zz[score_column] >= threshold
            axis.hist(zz.loc[selected, "m4l"], bins=bins, weights=weights.loc[selected], histtype="step", linewidth=1.5, label=f"{name.title()} ZZ MC")
        axis.set(title=f"{split_name} ZZ MC mass sculpting", xlabel="m4l [GeV]", ylabel="ZZ MC absolute physical yield", xlim=(bins[0], bins[-1]))
        axis.legend(fontsize="small")
    _save_and_close(figure, output_dir / "mc_mass_sculpting.png")


def _save_mass_signal_background(
    pyplot,
    oof,
    oof_score,
    test,
    test_score,
    bins,
    output_dir: Path,
) -> None:
    figure, axes = pyplot.subplots(2, 2, figsize=(12.0, 8.0), sharex=True)
    for row, (frame, score_column, split_name) in enumerate(
        zip((oof, test), (oof_score, test_score), ("OOF", "Test"), strict=True)
    ):
        del score_column  # The inclusive distribution is intentionally score-independent.
        yield_axis, shape_axis = axes[row]
        for label, class_name, color in ((0, "ZZ", "tab:blue"), (1, "Higgs", "tab:orange")):
            subset = frame.loc[frame["label"] == label]
            signed_weights = subset["physical_weight"].to_numpy(dtype=float)
            absolute_weights = np.abs(signed_weights)
            yield_axis.hist(
                subset["m4l"],
                bins=bins,
                weights=signed_weights,
                histtype="step",
                linewidth=1.8,
                color=color,
                label=f"{class_name} MC",
            )
            shape_axis.hist(
                subset["m4l"],
                bins=bins,
                weights=absolute_weights / absolute_weights.sum(),
                histtype="step",
                linewidth=1.8,
                color=color,
                label=f"{class_name} MC",
            )
        yield_axis.axhline(0.0, color="0.4", linewidth=1.0)
        yield_axis.set(
            title=f"{split_name} MC inclusive m4l signed physical yields",
            ylabel="Signed MC physical yield",
            xlim=_FIXED_MASS_RANGE_GEV,
        )
        shape_axis.set(
            title=f"{split_name} MC inclusive m4l unit-area shapes",
            ylabel="MC absolute physical weight (unit area per class)",
            xlim=_FIXED_MASS_RANGE_GEV,
        )
        yield_axis.legend(fontsize="small")
        shape_axis.legend(fontsize="small")
    for axis in axes[-1]:
        axis.set_xlabel("m4l [GeV]")
    for axis in axes[0]:
        axis.set_xlabel("m4l [GeV]")
    _save_and_close(figure, output_dir / "mc_mass_signal_background.png")


def _save_mass_working_points(
    pyplot,
    oof,
    oof_score,
    test,
    test_score,
    thresholds,
    bins,
    output_dir: Path,
) -> None:
    figure, axes = pyplot.subplots(1, 2, figsize=(14.0, 5.2), sharey=True)
    for axis, frame, score_column, split_name in zip(
        axes, (oof, test), (oof_score, test_score), ("OOF", "Test"), strict=True
    ):
        for label, class_name, color in ((0, "ZZ", "tab:blue"), (1, "Higgs", "tab:orange")):
            subset = frame.loc[frame["label"] == label]
            weights = subset["physical_weight"].to_numpy(dtype=float)
            axis.hist(
                subset["m4l"],
                bins=bins,
                weights=weights,
                histtype="step",
                linewidth=1.8,
                color=color,
                label=f"Inclusive {class_name} MC",
            )
            for point_name, threshold in thresholds.items():
                selected = subset[score_column] >= threshold
                axis.hist(
                    subset.loc[selected, "m4l"],
                    bins=bins,
                    weights=weights[selected.to_numpy()],
                    histtype="step",
                    linewidth=1.2,
                    color=color,
                    linestyle={"loose": "--", "medium": "-.", "tight": ":"}[point_name],
                    label=(
                        f"{point_name.title()} {class_name} MC "
                        f"(score >= frozen {threshold:.3f})"
                    ),
                )
        axis.axhline(0.0, color="0.4", linewidth=1.0)
        axis.set(
            title=f"{split_name} MC m4l working points (frozen OOF thresholds)",
            xlabel="m4l [GeV]",
            ylabel="Signed MC physical yield",
            xlim=_FIXED_MASS_RANGE_GEV,
        )
        axis.legend(fontsize="x-small", ncol=2)
    _save_and_close(figure, output_dir / "mc_mass_working_points.png")


def _save_and_close(figure, path: Path) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    figure.clear()
    import matplotlib.pyplot as pyplot

    pyplot.close(figure)
