from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from src.decorrelation_training_plots import (
    plot_candidate_tradeoff,
    plot_selected_mass_sculpting,
    plot_working_point_ks,
)


PNG = b"\x89PNG\r\n\x1a\n"
MASS_BINS = (105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160)


def _candidate_results():
    return tuple(
        SimpleNamespace(
            coefficient=coefficient,
            weighted_auc=auc,
            zz_ks_distances={
                "loose": 0.04 + coefficient / 100,
                "medium": 0.06 + coefficient / 100,
                "tight": 0.08 + coefficient / 100,
            },
        )
        for coefficient, auc in ((0.0, 0.83), (0.5, 0.82), (1.0, 0.81))
    )


def _score_frame(score_column: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "label": [0, 0, 0, 0, 1, 1],
            "physical_weight": [1.0, -0.5, 1.5, -2.0, 7.0, -9.0],
            "m4l": [108.0, 121.0, 139.0, 154.0, 112.0, 149.0],
            score_column: [0.25, 0.55, 0.75, 0.95, 0.1, 0.99],
        }
    )


def _working_points():
    return {
        "loose": {"threshold": 0.4},
        "medium": {"threshold": 0.7},
        "tight": {"threshold": 0.9},
    }


def _assert_valid_png(payload: bytes) -> None:
    assert payload.startswith(PNG)
    image = mpimg.imread(BytesIO(payload), format="png")
    assert image.ndim == 3
    assert image.shape[0] > 100
    assert image.shape[1] > 100


def test_common_plots_are_valid_mc_only_pngs_and_close_figures():
    """Returning empty bytes or leaking Matplotlib figures must fail."""
    before = plt.get_fignums()

    tradeoff = plot_candidate_tradeoff(_candidate_results())
    working_points = plot_working_point_ks(_candidate_results())

    _assert_valid_png(tradeoff)
    _assert_valid_png(working_points)
    assert plt.get_fignums() == before


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("weighted_auc", np.nan),
        (
            "zz_ks_distances",
            {"loose": 0.1, "medium": np.inf, "tight": 0.1},
        ),
    ),
)
def test_common_plots_reject_non_finite_candidate_evidence(field, value):
    """A NaN or infinity in scientific evidence must never reach a PNG."""
    candidate = SimpleNamespace(
        coefficient=1.0,
        weighted_auc=0.81,
        zz_ks_distances={"loose": 0.04, "medium": 0.05, "tight": 0.06},
    )
    setattr(candidate, field, value)

    with pytest.raises(ValueError, match="finite"):
        plot_candidate_tradeoff((candidate,))
    with pytest.raises(ValueError, match="finite"):
        plot_working_point_ks((candidate,))


def test_mass_plot_requires_exact_working_points():
    """Dropping a frozen threshold must fail before a misleading plot exists."""
    with pytest.raises(ValueError, match="exactly loose, medium, and tight"):
        plot_selected_mass_sculpting(
            _score_frame("oof_score"),
            _score_frame("score"),
            {"loose": {"threshold": 0.5}},
            mass_bins_gev=MASS_BINS,
        )


def test_mass_plot_uses_only_zz_absolute_weight_unit_area_shapes():
    """Signal rows, signed-weight convention, and global yield scale cannot alter shapes."""
    oof = _score_frame("oof_score")
    test = _score_frame("score")
    baseline = plot_selected_mass_sculpting(
        oof, test, _working_points(), mass_bins_gev=MASS_BINS
    )

    changed = []
    for frame, score_column in ((oof, "oof_score"), (test, "score")):
        alternative = frame.copy(deep=True)
        alternative.loc[alternative["label"] == 1, ["m4l", score_column]] = [
            159.0,
            0.5,
        ]
        alternative.loc[alternative["label"] == 1, "physical_weight"] = 100_000.0
        changed.append(alternative)
    assert plot_selected_mass_sculpting(
        changed[0], changed[1], _working_points(), mass_bins_gev=MASS_BINS
    ) == baseline

    rescaled = []
    for frame in (oof, test):
        alternative = frame.copy(deep=True)
        alternative.loc[alternative["label"] == 0, "physical_weight"] *= -17.0
        rescaled.append(alternative)
    assert plot_selected_mass_sculpting(
        rescaled[0], rescaled[1], _working_points(), mass_bins_gev=MASS_BINS
    ) == baseline


def test_mass_plot_rejects_non_finite_values_without_leaking_a_figure():
    """A validation exception must not change the caller's open figures."""
    oof = _score_frame("oof_score")
    oof.loc[0, "m4l"] = np.nan
    before = plt.get_fignums()

    with pytest.raises(ValueError, match="finite"):
        plot_selected_mass_sculpting(
            oof, _score_frame("score"), _working_points(), mass_bins_gev=MASS_BINS
        )

    assert plt.get_fignums() == before
