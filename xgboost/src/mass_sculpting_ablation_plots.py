"""MC-only plot byte builders for the ablation study."""

from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_oof_profile_tradeoff(results) -> bytes:
    figure, axis = plt.subplots(figsize=(6, 4))
    for name, values in results.items():
        axis.scatter(values["weighted_auc"], values["maximum_ks"], label=name)
        axis.annotate(name, (values["weighted_auc"], values["maximum_ks"]))
    axis.axvline(0.80, color="black", linestyle="--")
    axis.axhline(0.10, color="black", linestyle="--")
    axis.set(xlabel="Weighted OOF AUC", ylabel="Maximum OOF ZZ KS")
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=120)
    plt.close(figure)
    return buffer.getvalue()


def plot_selected_mass_sculpting(
    oof: pd.DataFrame,
    test: pd.DataFrame,
    working_points,
    *,
    mass_bins_gev,
) -> bytes:
    """Plot inclusive and OOF-threshold-selected ZZ shapes with absolute weights."""
    required_points = {"loose", "medium", "tight"}
    if set(working_points) != required_points:
        raise ValueError("working points must be exactly loose, medium, and tight")
    bins = np.asarray(tuple(mass_bins_gev), dtype=float)
    if bins.ndim != 1 or len(bins) < 2 or not np.isfinite(bins).all() or np.any(np.diff(bins) <= 0):
        raise ValueError("mass bins must be finite and strictly increasing")
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for axis, frame, score_column, title in (
        (axes[0], oof, "oof_score", "Development OOF ZZ MC"),
        (axes[1], test, "score", "Independent test ZZ MC"),
    ):
        _validate_mass_frame(frame, score_column)
        zz = frame.loc[frame["label"] == 0]
        if zz.empty:
            raise ValueError("mass-sculpting plot requires ZZ rows")
        _density_step(axis, zz, bins, label="inclusive", score_column=None, threshold=None)
        for name in ("loose", "medium", "tight"):
            point = working_points[name]
            threshold = float(point["threshold"])
            if not np.isfinite(threshold):
                raise ValueError("working-point threshold must be finite")
            _density_step(
                axis,
                zz,
                bins,
                label=f"{name} (score ≥ {threshold:.3f})",
                score_column=score_column,
                threshold=threshold,
            )
        axis.set(title=title, xlabel=r"$m_{4\ell}$ [GeV]", ylabel="Unit-normalized |weight| density")
        axis.legend(fontsize=8)
    figure.tight_layout()
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=140)
    plt.close(figure)
    return buffer.getvalue()


def _density_step(axis, frame, bins, *, label, score_column, threshold) -> None:
    selected = frame if score_column is None else frame.loc[frame[score_column] >= threshold]
    weights = np.abs(selected["physical_weight"].to_numpy(dtype=float))
    total = float(weights.sum())
    if total <= 0.0:
        raise ValueError(f"selected ZZ shape has zero absolute weight: {label}")
    axis.hist(
        selected["m4l"].to_numpy(dtype=float),
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
    values = frame.loc[:, ["label", "physical_weight", "m4l", score_column]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("mass-sculpting plot values must be finite")
