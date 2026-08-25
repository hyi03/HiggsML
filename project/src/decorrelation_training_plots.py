"""MC-only PNG builders for the flatness study."""

from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


_POINTS = ("loose", "medium", "tight")


def plot_candidate_tradeoff(results) -> bytes:
    normalized = tuple(results)
    if not normalized:
        raise ValueError("candidate trade-off plot requires results")
    figure, axis = plt.subplots(figsize=(6.5, 4.5))
    for result in normalized:
        auc = _finite(result.weighted_auc, "weighted AUC")
        maximum_ks = max(
            _finite(value, "ZZ KS") for value in result.zz_ks_distances.values()
        )
        name = _candidate_name(result.coefficient)
        axis.scatter(auc, maximum_ks, label=name)
        axis.annotate(name, (auc, maximum_ks))
    axis.axvline(0.80, color="black", linestyle="--", label="AUC gate")
    axis.axhline(0.10, color="gray", linestyle="--", label="KS gate")
    axis.set(
        xlabel="Weighted development OOF AUC",
        ylabel="Maximum development OOF ZZ mass KS",
        title="MC-only KNN-flatness candidate trade-off",
    )
    axis.legend(fontsize=8)
    figure.tight_layout()
    return _png_bytes(figure)


def plot_working_point_ks(results) -> bytes:
    normalized = tuple(results)
    if not normalized:
        raise ValueError("working-point KS plot requires results")
    coefficients = [float(result.coefficient) for result in normalized]
    figure, axis = plt.subplots(figsize=(7, 4.5))
    for name in _POINTS:
        values = [
            _finite(result.zz_ks_distances[name], f"{name} ZZ KS")
            for result in normalized
        ]
        axis.plot(coefficients, values, marker="o", label=name)
    axis.axhline(0.10, color="black", linestyle="--", label="KS gate")
    axis.set(
        xlabel="Flatness coefficient",
        ylabel="Development OOF ZZ mass KS",
        title="MC-only mass-shape diagnostics by working point",
    )
    axis.legend()
    figure.tight_layout()
    return _png_bytes(figure)


def plot_selected_mass_sculpting(
    oof: pd.DataFrame,
    test: pd.DataFrame,
    working_points,
    *,
    mass_bins_gev,
) -> bytes:
    if set(working_points) != set(_POINTS):
        raise ValueError("working points must be exactly loose, medium, and tight")
    bins = np.asarray(tuple(mass_bins_gev), dtype=float)
    if (
        bins.ndim != 1
        or len(bins) < 2
        or not np.isfinite(bins).all()
        or np.any(np.diff(bins) <= 0)
    ):
        raise ValueError("mass bins must be finite and strictly increasing")
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for axis, frame, score_column, title in (
        (axes[0], oof, "oof_score", "Development OOF ZZ MC"),
        (axes[1], test, "score", "Independent test ZZ MC"),
    ):
        _validate_mass_frame(frame, score_column)
        background = frame.loc[frame["label"] == 0]
        if background.empty:
            raise ValueError("mass-sculpting plot requires ZZ rows")
        _density(axis, background, bins, "inclusive")
        for name in _POINTS:
            threshold = _finite(working_points[name]["threshold"], "threshold")
            selected = background.loc[background[score_column] >= threshold]
            _density(axis, selected, bins, f"{name} (score ≥ {threshold:.3f})")
        axis.set(
            title=title,
            xlabel=r"$m_{4\ell}$ [GeV]",
            ylabel="Unit-normalized |weight| density",
        )
        axis.legend(fontsize=8)
    figure.tight_layout()
    return _png_bytes(figure)


def _density(axis, frame: pd.DataFrame, bins: np.ndarray, label: str) -> None:
    weights = np.abs(frame["physical_weight"].to_numpy(dtype=float))
    total = float(weights.sum())
    if total <= 0.0:
        raise ValueError(f"selected ZZ shape has zero absolute weight: {label}")
    axis.hist(
        frame["m4l"].to_numpy(dtype=float),
        bins=bins,
        weights=weights / total,
        histtype="step",
        linewidth=1.5,
        label=label,
    )


def _validate_mass_frame(frame: pd.DataFrame, score_column: str) -> None:
    required = {"label", "physical_weight", "m4l", score_column}
    if not isinstance(frame, pd.DataFrame) or not required <= set(frame):
        raise ValueError("mass-sculpting plot frame is missing required columns")
    values = frame.loc[:, sorted(required)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("mass-sculpting plot values must be finite")


def _candidate_name(coefficient: float) -> str:
    return f"lambda_{float(coefficient):.1f}".replace(".", "p")


def _finite(value, name: str) -> float:
    normalized = float(value)
    if not np.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _png_bytes(figure) -> bytes:
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=140)
    plt.close(figure)
    return buffer.getvalue()
