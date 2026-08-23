from __future__ import annotations

import pandas as pd

from src.mass_sculpting_ablation_plots import (
    plot_oof_profile_tradeoff,
    plot_selected_mass_sculpting,
)


def test_tradeoff_plot_is_png_with_fixed_reference_lines():
    payload = plot_oof_profile_tradeoff({"shape8": {"weighted_auc": 0.81, "maximum_ks": 0.05}})
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")


def test_selected_mass_plot_is_png_and_uses_frozen_thresholds():
    oof = pd.DataFrame({
        "label": [0, 0, 0, 1],
        "physical_weight": [1.0, -0.5, 2.0, 1.0],
        "m4l": [110.0, 125.0, 150.0, 125.0],
        "oof_score": [0.1, 0.6, 0.9, 0.8],
    })
    test = pd.DataFrame({
        "label": [0, 0, 0, 1],
        "physical_weight": [1.0, 1.0, -0.5, 1.0],
        "m4l": [112.0, 127.0, 152.0, 125.0],
        "score": [0.2, 0.7, 0.95, 0.85],
    })
    points = {
        "loose": {"threshold": 0.4},
        "medium": {"threshold": 0.7},
        "tight": {"threshold": 0.9},
    }
    payload = plot_selected_mass_sculpting(
        oof, test, points, mass_bins_gev=(105, 120, 135, 160)
    )
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
