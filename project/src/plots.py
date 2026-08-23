from __future__ import annotations

from pathlib import Path

import numpy as np

from .features import FEATURES


def _plot_modules():
    try:
        import matplotlib.pyplot as plt
        from sklearn.metrics import roc_curve
    except ImportError as exc:
        raise RuntimeError("matplotlib and scikit-learn are required for plots") from exc
    return plt, roc_curve


def save_evaluation_plots(evaluated, model, output_dir: str | Path) -> None:
    plt, roc_curve = _plot_modules()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    test = evaluated[evaluated["split"] == "test"]
    signal = test["label"] == 1
    weights = np.abs(test["physical_weight"])

    figure, axis = plt.subplots(figsize=(6, 5))
    for weighted, label in [(None, "unweighted"), (weights, "weighted")]:
        fpr, tpr, _ = roc_curve(test["label"], test["xgb_score"], sample_weight=weighted)
        axis.plot(fpr, tpr, label=label)
    axis.plot([0, 1], [0, 1], "--", color="0.6")
    axis.set(xlabel="Background efficiency", ylabel="Signal efficiency")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_dir / "roc_curve.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(7, 4.5))
    bins = np.linspace(0, 1, 31)
    for split, linestyle in [("train", "-"), ("test", "--")]:
        subset = evaluated[evaluated["split"] == split]
        for label, process, color in [(0, "ZZ*", "tab:blue"), (1, "Higgs", "tab:red")]:
            axis.hist(
                subset.loc[subset["label"] == label, "xgb_score"],
                bins=bins,
                density=True,
                histtype="step",
                linestyle=linestyle,
                color=color,
                label=f"{process} · {split}",
            )
    axis.set(xlabel="XGBoost score", ylabel="Normalized events")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_dir / "score_distribution.png", dpi=160)
    figure.savefig(output_dir / "train_test_score_comparison.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(6, 5))
    axis.scatter(test["m4l"], test["xgb_score"], s=5, alpha=0.25)
    correlation = np.corrcoef(test["m4l"], test["xgb_score"])[0, 1]
    axis.set(
        xlabel=r"$m_{4\ell}$ [GeV]",
        ylabel="XGBoost score",
        title=f"score–mass correlation = {correlation:.3f}",
    )
    figure.tight_layout()
    figure.savefig(output_dir / "score_vs_m4l.png", dpi=160)
    plt.close(figure)

    figure, axes = plt.subplots(4, 4, figsize=(13, 10))
    for index, feature in enumerate(FEATURES):
        axis = axes.flat[index]
        values = test[feature].to_numpy()
        low, high = np.nanquantile(values, [0.01, 0.99])
        bins = np.linspace(low, high, 26)
        axis.hist(
            test.loc[~signal, feature],
            bins=bins,
            density=True,
            histtype="step",
            color="tab:blue",
            label="ZZ*",
        )
        axis.hist(
            test.loc[signal, feature],
            bins=bins,
            density=True,
            histtype="step",
            color="tab:red",
            label="Higgs",
        )
        axis.set_title(feature, fontsize=9)
        axis.tick_params(labelsize=7)
    for axis in axes.flat[len(FEATURES) :]:
        axis.remove()
    axes.flat[0].legend(fontsize=7)
    figure.tight_layout()
    figure.savefig(output_dir / "feature_distributions.png", dpi=160)
    plt.close(figure)


def save_data_mass_plots(data, threshold: float, output_dir: str | Path) -> None:
    plt, _ = _plot_modules()
    output_dir = Path(output_dir)
    bins = np.linspace(105, 145, 41)
    for filename, mask, title in [
        ("m4l_before_xgb.png", np.ones(len(data), dtype=bool), "All data events"),
        (
            "m4l_low_score.png",
            data["xgb_score"].to_numpy() < threshold,
            f"XGBoost score < {threshold:.2f}",
        ),
        (
            "m4l_high_score.png",
            data["xgb_score"].to_numpy() >= threshold,
            f"XGBoost score ≥ {threshold:.2f}",
        ),
    ]:
        figure, axis = plt.subplots(figsize=(7, 4.5))
        axis.hist(data.loc[mask, "m4l"], bins=bins, histtype="step", linewidth=1.6)
        axis.axvspan(122, 128, color="tab:red", alpha=0.1)
        axis.set(xlabel=r"$m_{4\ell}$ [GeV]", ylabel="Events", title=title)
        figure.tight_layout()
        figure.savefig(output_dir / filename, dpi=160)
        plt.close(figure)
