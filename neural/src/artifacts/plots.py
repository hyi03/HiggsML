from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from src.config import InputBindingError


def _save(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=120, metadata={"Software": "HiggsML neural educational demo"})
    plt.close()


def write_development_plots(
    directory: str | Path,
    candidates: list[dict[str, Any]],
    oof: pd.DataFrame,
    *,
    selected_lambda: float | None,
    roc_points: tuple[np.ndarray, np.ndarray],
    mass_edges: tuple[float, ...],
) -> tuple[Path, ...]:
    false_positive, true_positive = roc_points
    bins = np.asarray(mass_edges, dtype=np.float64)
    if (
        not candidates
        or "split" in oof
        or not np.isfinite(oof["score"].to_numpy()).all()
        or false_positive.ndim != 1
        or true_positive.shape != false_positive.shape
        or false_positive.size == 0
        or not np.isfinite(false_positive).all()
        or not np.isfinite(true_positive).all()
        or bins.ndim != 1
        or bins.size < 2
        or not np.isfinite(bins).all()
        or not np.all(np.diff(bins) > 0)
    ):
        raise InputBindingError("development plot input changed")
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    lambdas = [float(item["target_lambda"]) for item in candidates]

    plt.figure()
    plt.plot(lambdas, [item["weighted_oof_auc"] for item in candidates], marker="o")
    plt.xlabel("target lambda")
    plt.ylabel("weighted development OOF AUC")
    auc_path = destination / "auc_vs_lambda.png"
    _save(auc_path)

    plt.figure()
    for name in ("loose", "medium", "tight"):
        plt.plot(
            lambdas,
            [item["working_points"][name]["ks"] for item in candidates],
            marker="o",
            label=name,
        )
    plt.xlabel("target lambda")
    plt.ylabel("OOF ZZ weighted mass KS")
    plt.legend()
    ks_path = destination / "ks_vs_lambda.png"
    _save(ks_path)

    display_lambda = selected_lambda
    if display_lambda is None:
        display_lambda = float(max(candidates, key=lambda item: item["weighted_oof_auc"])["target_lambda"])
    display = oof.loc[oof["target_lambda"] == display_lambda]
    scores = display["score"].to_numpy(dtype=np.float64)
    plt.figure()
    plt.plot(false_positive, true_positive)
    plt.plot([0, 1], [0, 1], linestyle="--")
    plt.xlabel("background efficiency")
    plt.ylabel("signal efficiency")
    roc_path = destination / "oof_roc.png"
    _save(roc_path)

    candidate = next(item for item in candidates if item["target_lambda"] == display_lambda)
    threshold = float(candidate["working_points"]["medium"]["threshold"])
    background = display["label"].to_numpy() == 0
    selected = background & (scores >= threshold)
    masses = display["m4l"].to_numpy(dtype=np.float64)
    absolute = np.abs(display["physical_weight"].to_numpy(dtype=np.float64))
    plt.figure()
    plt.hist(masses[background], bins=bins, weights=absolute[background], histtype="step", density=True, label="all ZZ")
    plt.hist(masses[selected], bins=bins, weights=absolute[selected], histtype="step", density=True, label="medium selected ZZ")
    plt.xlabel("m4l [GeV]")
    plt.ylabel("normalized absolute-weight density")
    plt.legend()
    mass_path = destination / "oof_mass_sculpting.png"
    _save(mass_path)
    return auc_path, ks_path, roc_path, mass_path
