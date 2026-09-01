"""In-memory MC-only diagnostic plots for mass-bin reweighting outcomes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from io import BytesIO

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .mass_bin_reweighting import ReweightingStudyOutcome


_MASS_EDGES = np.arange(105.0, 161.0, 5.0)
_MASS_CENTERS = (_MASS_EDGES[:-1] + _MASS_EDGES[1:]) / 2.0
_MASS_BIN_NAMES = tuple(
    f"[{int(lower)},{int(upper)}{']' if upper == 160.0 else ')'}"
    for lower, upper in zip(_MASS_EDGES[:-1], _MASS_EDGES[1:])
)
_WORKING_POINTS = (("loose", 0.50), ("medium", 0.20), ("tight", 0.10))
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def build_iteration_tradeoff_png(outcome: ReweightingStudyOutcome) -> bytes:
    """Render OOF AUC/KS history and cumulative fitting-weight audit values."""
    iterations = _validated_iterations(outcome)
    iteration_numbers = np.asarray([item.iteration for item in iterations], dtype=float)
    auc = np.asarray([item.weighted_oof_auc for item in iterations], dtype=float)
    ks = {
        name: np.asarray(
            [_finite_value(item.zz_ks_distances, name, "OOF KS") for item in iterations],
            dtype=float,
        )
        for name, _ in _WORKING_POINTS
    }
    heatmap = np.asarray(
        [_multipliers_for_iteration(item) for item in iterations], dtype=float
    )

    figure, axes = plt.subplots(3, 1, figsize=(10, 10), constrained_layout=True)
    try:
        axes[0].plot(iteration_numbers, auc, marker="o", color="C0", label="OOF AUC")
        axes[0].axhline(0.80, color="black", linestyle="--", linewidth=1.0, label="OOF AUC gate (0.80)")
        axes[0].set(
            title="OOF discrimination by iteration (MC-only)",
            xlabel="Iteration",
            ylabel="Weighted OOF AUC",
            xticks=iteration_numbers,
            ylim=(0.0, 1.05),
        )
        axes[0].legend(loc="best", fontsize=8)

        for color, (name, _) in zip(("C0", "C1", "C2"), _WORKING_POINTS, strict=True):
            axes[1].plot(
                iteration_numbers,
                ks[name],
                marker="o",
                color=color,
                label=f"{name} OOF ZZ KS",
            )
        axes[1].axhline(0.10, color="black", linestyle="--", linewidth=1.0, label="OOF KS gate (0.10)")
        axes[1].set(
            title="OOF ZZ mass-shape distance by iteration (MC-only)",
            xlabel="Iteration",
            ylabel="Inclusive-to-selected ZZ KS distance",
            xticks=iteration_numbers,
            ylim=(0.0, 1.05),
        )
        axes[1].legend(loc="best", fontsize=8)

        image = axes[2].imshow(heatmap, aspect="auto", interpolation="nearest", cmap="viridis")
        axes[2].set(
            title="Cumulative ZZ fitting-weight multiplier audit",
            xlabel=r"$m_{4\ell}$ bin [GeV]",
            ylabel="Iteration",
            xticks=np.arange(len(_MASS_BIN_NAMES)),
            xticklabels=_MASS_BIN_NAMES,
            yticks=np.arange(len(iteration_numbers)),
            yticklabels=[str(int(value)) for value in iteration_numbers],
        )
        axes[2].tick_params(axis="x", labelrotation=45, labelsize=8)
        figure.colorbar(image, ax=axes[2], label="Cumulative fitting multiplier")
        return _png_bytes(figure)
    finally:
        plt.close(figure)


def build_zz_efficiency_by_mass_png(outcome: ReweightingStudyOutcome) -> bytes:
    """Render final-executed OOF ZZ efficiencies with effective-binomial errors."""
    iteration = _validated_iterations(outcome)[-1]
    table = _validated_bin_efficiencies(iteration.bin_efficiencies)

    figure, axis = plt.subplots(figsize=(10, 5), constrained_layout=True)
    try:
        for color, (name, target) in zip(("C0", "C1", "C2"), _WORKING_POINTS, strict=True):
            values = table.xs(name, level="working_point").reindex(_MASS_BIN_NAMES)
            efficiencies = values["efficiency"].to_numpy(dtype=float)
            effective_counts = values["effective_count"].to_numpy(dtype=float)
            errors = np.sqrt(efficiencies * (1.0 - efficiencies) / effective_counts)
            axis.errorbar(
                _MASS_CENTERS,
                efficiencies,
                yerr=errors,
                marker="o",
                linestyle="-",
                capsize=3,
                color=color,
                label=f"{name} OOF ZZ efficiency",
            )
            axis.axhline(target, color=color, linestyle="--", linewidth=1.0, label=f"{name} target ({target:.2f})")
        axis.set(
            title="OOF ZZ efficiency by fixed $m_{4\\ell}$ bin (MC-only)",
            xlabel=r"$m_{4\ell}$ bin center [GeV]",
            ylabel="OOF ZZ efficiency (absolute physical weight)",
            xlim=(105.0, 160.0),
            ylim=(0.0, 1.05),
            xticks=_MASS_CENTERS,
        )
        axis.legend(loc="best", ncol=2, fontsize=8)
        return _png_bytes(figure)
    finally:
        plt.close(figure)


def build_selected_mass_sculpting_png(outcome: ReweightingStudyOutcome) -> bytes:
    """Render OOF and independent-test ZZ shapes after OOF selection freezes."""
    if getattr(outcome, "selected_iteration", None) is None or getattr(
        outcome, "selected_oof_scores", None
    ) is None:
        raise ValueError("selected OOF iteration is required for the selected-mass plot")

    iterations = _validated_iterations(outcome)
    selected_iteration = int(outcome.selected_iteration)
    evidence = next(
        (item for item in iterations if item.iteration == selected_iteration), None
    )
    if evidence is None:
        raise ValueError("selected OOF iteration is absent from executed iterations")
    thresholds = _validated_thresholds(evidence.working_points)
    oof = _validated_scored_frame(outcome.selected_oof_scores, "oof_score", "OOF")
    test = _validated_scored_frame(outcome.test_scores, "score", "test")

    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True, constrained_layout=True)
    try:
        _plot_zz_shapes(
            axes[0],
            oof,
            "oof_score",
            thresholds,
            title="Development OOF ZZ MC mass shapes",
            evidence_label="OOF",
        )
        _plot_zz_shapes(
            axes[1],
            test,
            "score",
            thresholds,
            title="Independent test ZZ MC mass shapes",
            evidence_label="test",
        )
        axes[0].set_ylabel("Absolute physical weight / 5 GeV")
        return _png_bytes(figure)
    finally:
        plt.close(figure)


def _plot_zz_shapes(axis, frame: pd.DataFrame, score_column: str, thresholds: Mapping[str, float], *, title: str, evidence_label: str) -> None:
    zz = frame.loc[frame["label"] == 0]
    if zz.empty:
        raise ValueError(f"{evidence_label} plot requires non-empty ZZ evidence")
    _histogram(axis, zz, label=f"inclusive {evidence_label} ZZ")
    scores = zz[score_column].to_numpy(dtype=float)
    for name, _ in _WORKING_POINTS:
        selected = zz.loc[scores >= thresholds[name]]
        if selected.empty:
            raise ValueError(f"{evidence_label} selected ZZ evidence is non-empty only")
        _histogram(
            axis,
            selected,
            label=f"{name} ({evidence_label}; OOF-frozen score ≥ {thresholds[name]:.3f})",
        )
    axis.set(
        title=title,
        xlabel=r"$m_{4\ell}$ [GeV]",
        xlim=(105.0, 160.0),
    )
    axis.legend(loc="best", fontsize=8)


def _histogram(axis, frame: pd.DataFrame, *, label: str) -> None:
    axis.hist(
        frame["m4l"].to_numpy(dtype=float),
        bins=_MASS_EDGES,
        weights=np.abs(frame["physical_weight"].to_numpy(dtype=float)),
        histtype="step",
        linewidth=1.5,
        label=label,
    )


def _validated_iterations(outcome: ReweightingStudyOutcome) -> tuple[object, ...]:
    items = getattr(outcome, "iterations", None)
    if not isinstance(items, Sequence) or not items:
        raise ValueError("plot evidence must contain non-empty executed iterations")
    iteration_numbers: list[int] = []
    for item in items:
        iteration = getattr(item, "iteration", None)
        if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 0:
            raise ValueError("iteration evidence must be finite non-negative integers")
        iteration_numbers.append(iteration)
        if not np.isfinite(float(getattr(item, "weighted_oof_auc", np.nan))):
            raise ValueError("plot evidence must be finite")
        _multipliers_for_iteration(item)
        _validated_thresholds(getattr(item, "working_points", None))
        for name, _ in _WORKING_POINTS:
            _finite_value(getattr(item, "zz_ks_distances", None), name, "OOF KS")
    if iteration_numbers != list(range(len(iteration_numbers))):
        raise ValueError("executed iterations must be finite consecutive iteration numbers")
    return tuple(items)


def _multipliers_for_iteration(item: object) -> np.ndarray:
    values = getattr(item, "cumulative_multipliers", None)
    if not isinstance(values, Mapping) or tuple(values) != _MASS_BIN_NAMES:
        raise ValueError("cumulative multiplier audit must contain the fixed eleven mass bins")
    output = np.asarray([_finite_value(values, name, "cumulative multiplier") for name in _MASS_BIN_NAMES], dtype=float)
    if (output <= 0.0).any():
        raise ValueError("cumulative multiplier audit must be finite and positive")
    return output


def _validated_thresholds(working_points: object) -> dict[str, float]:
    if not isinstance(working_points, Mapping) or tuple(working_points) != tuple(
        name for name, _ in _WORKING_POINTS
    ):
        raise ValueError("working-point keys must be exactly loose, medium, and tight")
    output: dict[str, float] = {}
    for name, target in _WORKING_POINTS:
        point = working_points[name]
        if not isinstance(point, Mapping):
            raise ValueError("working-point evidence must be finite")
        threshold = _finite_value(point, "threshold", "OOF-frozen threshold")
        recorded_target = _finite_value(
            point, "target_background_efficiency", "working-point target"
        )
        if recorded_target != target:
            raise ValueError("working-point targets must equal 0.50, 0.20, and 0.10")
        output[name] = threshold
    if any(first > second for first, second in zip(output.values(), tuple(output.values())[1:])):
        raise ValueError("OOF-frozen thresholds must be monotonic")
    return output


def _validated_bin_efficiencies(table: object) -> pd.DataFrame:
    if not isinstance(table, pd.DataFrame) or table.empty:
        raise ValueError("bin-efficiency plot evidence must be non-empty")
    expected = pd.MultiIndex.from_product(
        [_MASS_BIN_NAMES, tuple(name for name, _ in _WORKING_POINTS)],
        names=["mass_bin", "working_point"],
    )
    if not isinstance(table.index, pd.MultiIndex) or not table.index.is_unique or set(table.index) != set(expected):
        raise ValueError("bin-efficiency plot evidence must contain fixed bins and working points")
    required = {"numerator", "denominator", "efficiency", "effective_count", "standard_error"}
    if not required <= set(table.columns):
        raise ValueError("bin-efficiency plot evidence must be finite")
    values = table.reindex(expected).loc[:, sorted(required)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("bin-efficiency plot evidence must be finite")
    efficiency = table.reindex(expected)["efficiency"].to_numpy(dtype=float)
    effective_count = table.reindex(expected)["effective_count"].to_numpy(dtype=float)
    standard_error = table.reindex(expected)["standard_error"].to_numpy(dtype=float)
    if (efficiency < 0.0).any() or (efficiency > 1.0).any() or (effective_count <= 0.0).any():
        raise ValueError("bin-efficiency plot evidence must be finite")
    expected_error = np.sqrt(efficiency * (1.0 - efficiency) / effective_count)
    if not np.allclose(standard_error, expected_error, rtol=1e-12, atol=1e-12):
        raise ValueError("bin-efficiency errors must use the effective-binomial formula")
    return table.reindex(expected).copy(deep=True)


def _validated_scored_frame(frame: object, score_column: str, name: str) -> pd.DataFrame:
    required = {"label", "m4l", "physical_weight", score_column}
    if not isinstance(frame, pd.DataFrame) or frame.empty or not required <= set(frame.columns):
        raise ValueError(f"{name} plot evidence must be non-empty")
    values = frame.loc[:, ["label", "m4l", "physical_weight", score_column]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"{name} plot evidence must be finite")
    if not frame["label"].isin({0, 1}).all():
        raise ValueError(f"{name} plot labels must be finite class labels")
    if (values[:, 1] < _MASS_EDGES[0]).any() or (values[:, 1] > _MASS_EDGES[-1]).any():
        raise ValueError(f"{name} plot masses must use fixed mass bins")
    return frame.copy(deep=True)


def _finite_value(mapping: object, key: str, name: str) -> float:
    if not isinstance(mapping, Mapping) or key not in mapping:
        raise ValueError(f"{name} evidence must be finite")
    try:
        value = float(mapping[key])
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} evidence must be finite") from error
    if not np.isfinite(value):
        raise ValueError(f"{name} evidence must be finite")
    return value


def _png_bytes(figure) -> bytes:
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=140)
    payload = buffer.getvalue()
    if not payload.startswith(_PNG_SIGNATURE):
        raise RuntimeError("Matplotlib did not produce a PNG")
    return payload
