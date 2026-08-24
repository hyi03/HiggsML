"""Validated MC-only PNG builders for the DropTop4 flatness study."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable, Mapping

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_WORKING_POINTS = ("loose", "medium", "tight")


def plot_candidate_tradeoff(results: Iterable[Any]) -> bytes:
    """Plot weighted OOF AUC against maximum OOF ZZ mass KS."""
    figure, _axis = _build_candidate_tradeoff_figure(results)
    try:
        return _render_png(figure)
    finally:
        plt.close(figure)


def _build_candidate_tradeoff_figure(results: Iterable[Any]):
    """Build the trade-off figure; the caller owns the figure lifecycle."""
    candidates = _validated_candidates(results)
    figure, axis = plt.subplots(figsize=(7, 4.5))
    for candidate in candidates:
        coefficient = candidate["coefficient"]
        auc = candidate["weighted_auc"]
        maximum_ks = max(candidate["zz_ks_distances"].values())
        label = _candidate_name(coefficient)
        axis.scatter(auc, maximum_ks, label=label)
        axis.annotate(
            label,
            (auc, maximum_ks),
            xytext=(4, 4),
            textcoords="offset points",
        )
    axis.axvline(
        0.80,
        color="black",
        linestyle="--",
        linewidth=1.0,
        label="AUC floor 0.80",
    )
    axis.axhline(
        0.10,
        color="dimgray",
        linestyle=":",
        linewidth=1.2,
        label="KS limit 0.10",
    )
    axis.set(
        title="MC-only DropTop4 flatness candidate trade-off",
        xlabel="Weighted development OOF AUC",
        ylabel="Maximum development OOF ZZ mass KS",
    )
    axis.legend(fontsize=8)
    figure.tight_layout()
    return figure, axis


def plot_working_point_ks(results: Iterable[Any]) -> bytes:
    """Plot each development OOF ZZ mass KS against flatness coefficient."""
    figure, _axis = _build_working_point_ks_figure(results)
    try:
        return _render_png(figure)
    finally:
        plt.close(figure)


def _build_working_point_ks_figure(results: Iterable[Any]):
    """Build the per-working-point KS figure; the caller closes it."""
    candidates = _validated_candidates(results)
    coefficients = [candidate["coefficient"] for candidate in candidates]
    figure, axis = plt.subplots(figsize=(7, 4.5))
    for name in _WORKING_POINTS:
        axis.plot(
            coefficients,
            [candidate["zz_ks_distances"][name] for candidate in candidates],
            marker="o",
            label=name,
        )
    axis.axhline(
        0.10,
        color="black",
        linestyle="--",
        linewidth=1.0,
        label="KS limit 0.10",
    )
    axis.set(
        title="MC-only development OOF ZZ mass-shape stability",
        xlabel="KNN flatness coefficient",
        ylabel="Inclusive-to-selected ZZ mass KS",
    )
    axis.legend(fontsize=8)
    figure.tight_layout()
    return figure, axis


def plot_selected_mass_sculpting(
    oof_scores: pd.DataFrame,
    test_scores: pd.DataFrame,
    working_points: Mapping[str, Mapping[str, object]],
    *,
    mass_bins_gev: Iterable[float],
) -> bytes:
    """Compare unit-area inclusive and selected ZZ shapes in OOF and test MC."""
    figure, _axes = _build_selected_mass_sculpting_figure(
        oof_scores,
        test_scores,
        working_points,
        mass_bins_gev=mass_bins_gev,
    )
    try:
        return _render_png(figure)
    finally:
        plt.close(figure)


def _build_selected_mass_sculpting_figure(
    oof_scores: pd.DataFrame,
    test_scores: pd.DataFrame,
    working_points: Mapping[str, Mapping[str, object]],
    *,
    mass_bins_gev: Iterable[float],
):
    """Build selected ZZ mass panels; the caller owns the figure lifecycle."""
    points = _validated_working_points(working_points)
    bins = _validated_bins(mass_bins_gev)
    _validate_mass_frame(oof_scores, "oof_score")
    _validate_mass_frame(test_scores, "score")

    figure, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    panels = (
        (axes[0], oof_scores, "oof_score", "Development OOF ZZ MC"),
        (axes[1], test_scores, "score", "Independent test ZZ MC"),
    )
    try:
        for axis, frame, score_column, title in panels:
            zz = frame.loc[frame["label"] == 0]
            if zz.empty:
                raise ValueError("mass-sculpting plot requires label-0 ZZ MC rows")
            _density_step(axis, zz, bins, label="inclusive")
            for point_index, name in enumerate(_WORKING_POINTS):
                threshold = points[name]
                selected = zz.loc[zz[score_column] >= threshold]
                if selected.empty:
                    _annotate_empty_selection(axis, name, point_index)
                    continue
                _density_step(
                    axis,
                    selected,
                    bins,
                    label=f"{name} (score ≥ {threshold:.3f})",
                )
            axis.set(
                title=title,
                xlabel=r"$m_{4\ell}$ [GeV]",
                ylabel="Unit-area |physical weight| shape",
            )
            axis.legend(fontsize=8)
        figure.suptitle("MC-only selected-candidate ZZ mass sculpting")
        figure.tight_layout()
        return figure, tuple(axes)
    except Exception:
        plt.close(figure)
        raise


def _validated_candidates(results: Iterable[Any]) -> tuple[dict[str, Any], ...]:
    try:
        raw = tuple(results)
    except TypeError as error:
        raise ValueError("candidate results must be iterable") from error
    if not raw:
        raise ValueError("candidate results must not be empty")
    normalized: list[dict[str, Any]] = []
    for result in raw:
        coefficient = _finite(getattr(result, "coefficient", None), "coefficient")
        auc = _finite(getattr(result, "weighted_auc", None), "weighted AUC")
        distances = getattr(result, "zz_ks_distances", None)
        if not isinstance(distances, Mapping) or set(distances) != set(_WORKING_POINTS):
            raise ValueError("ZZ KS distances must be exactly loose, medium, and tight")
        normalized.append(
            {
                "coefficient": coefficient,
                "weighted_auc": auc,
                "zz_ks_distances": {
                    name: _finite(distances[name], f"{name} ZZ mass KS")
                    for name in _WORKING_POINTS
                },
            }
        )
    return tuple(normalized)


def _validated_working_points(
    working_points: Mapping[str, Mapping[str, object]],
) -> dict[str, float]:
    if not isinstance(working_points, Mapping) or set(working_points) != set(
        _WORKING_POINTS
    ):
        raise ValueError("working points must be exactly loose, medium, and tight")
    thresholds: dict[str, float] = {}
    for name in _WORKING_POINTS:
        point = working_points[name]
        if not isinstance(point, Mapping) or "threshold" not in point:
            raise ValueError(f"working point {name} must contain a finite threshold")
        thresholds[name] = _finite(point["threshold"], f"{name} threshold")
    values = [thresholds[name] for name in _WORKING_POINTS]
    if any(first > second for first, second in zip(values, values[1:])):
        raise ValueError("working-point thresholds must be monotonic")
    return thresholds


def _validated_bins(mass_bins_gev: Iterable[float]) -> np.ndarray:
    try:
        bins = np.asarray(tuple(mass_bins_gev), dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("mass bins must be finite and strictly increasing") from error
    if (
        bins.ndim != 1
        or len(bins) < 2
        or not np.isfinite(bins).all()
        or np.any(np.diff(bins) <= 0.0)
    ):
        raise ValueError("mass bins must be finite and strictly increasing")
    return bins


def _validate_mass_frame(frame: pd.DataFrame, score_column: str) -> None:
    required = {"label", "physical_weight", "m4l", score_column}
    if not isinstance(frame, pd.DataFrame) or not required <= set(frame):
        raise ValueError("mass-sculpting plot frame is missing required columns")
    try:
        values = frame.loc[
            :, ["label", "physical_weight", "m4l", score_column]
        ].to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("mass-sculpting plot values must be finite") from error
    if not np.isfinite(values).all():
        raise ValueError("mass-sculpting plot values must be finite")


def _density_step(axis, frame: pd.DataFrame, bins: np.ndarray, *, label: str) -> None:
    weights = np.abs(frame["physical_weight"].to_numpy(dtype=float))
    total = float(weights.sum())
    if total <= 0.0:
        raise ValueError(f"selected ZZ shape has zero absolute physical weight: {label}")
    axis.hist(
        frame["m4l"].to_numpy(dtype=float),
        bins=bins,
        weights=weights / total,
        histtype="step",
        linewidth=1.5,
        label=label,
    )


def _annotate_empty_selection(axis, working_point: str, point_index: int) -> None:
    axis.text(
        0.98,
        0.96 - 0.07 * point_index,
        f"{working_point}: No selected ZZ MC",
        transform=axis.transAxes,
        ha="right",
        va="top",
        color="dimgray",
        fontsize=8,
    )


def _render_png(figure) -> bytes:
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=140)
    payload = buffer.getvalue()
    if not payload.startswith(_PNG_SIGNATURE):
        raise RuntimeError("Matplotlib did not produce a PNG")
    return payload


def _candidate_name(coefficient: float) -> str:
    return f"lambda_{str(float(coefficient)).replace('.', 'p')}"


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name} must be finite")
    normalized = float(value)
    if not np.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized
