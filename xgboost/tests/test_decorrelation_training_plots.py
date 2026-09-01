from types import SimpleNamespace

import pandas as pd
import pytest

from src.decorrelation_training_plots import (
    plot_candidate_tradeoff,
    plot_selected_mass_sculpting,
    plot_working_point_ks,
)


PNG = b"\x89PNG\r\n\x1a\n"


def test_common_plots_are_mc_only_pngs():
    result = SimpleNamespace(
        coefficient=1.0,
        weighted_auc=0.82,
        zz_ks_distances={"loose": 0.05, "medium": 0.06, "tight": 0.07},
    )

    assert plot_candidate_tradeoff((result,)).startswith(PNG)
    assert plot_working_point_ks((result,)).startswith(PNG)


def test_mass_plot_requires_exact_working_points():
    oof = _scores("oof_score")
    test = _scores("score")

    with pytest.raises(ValueError, match="exactly loose, medium, and tight"):
        plot_selected_mass_sculpting(
            oof,
            test,
            {"loose": {"threshold": 0.5}},
            mass_bins_gev=(105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160),
        )


def _scores(score_column):
    return pd.DataFrame(
        {
            "label": [0, 0, 0, 1],
            "physical_weight": [1.0, -0.5, 2.0, 1.0],
            "m4l": [110.0, 125.0, 150.0, 125.0],
            score_column: [0.1, 0.6, 0.9, 0.8],
        }
    )
