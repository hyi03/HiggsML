from __future__ import annotations

import math
from collections.abc import Mapping
from io import BytesIO
from types import MappingProxyType

import matplotlib.axes
import matplotlib.figure
import numpy as np
import pandas as pd
import pytest

from src.mass_bin_reweighting import (
    IterationEvidence,
    ReweightingStudyOutcome,
)
from src.mass_bin_reweighting_plots import (
    build_iteration_tradeoff_png,
    build_selected_mass_sculpting_png,
    build_zz_efficiency_by_mass_png,
)


EDGES = tuple(float(value) for value in range(105, 161, 5))
BIN_NAMES = tuple(
    f"[{int(lower)},{int(upper)}{']' if upper == 160 else ')'}"
    for lower, upper in zip(EDGES, EDGES[1:])
)
POINTS = MappingProxyType(
    {
        "loose": MappingProxyType(
            {"threshold": 0.25, "target_background_efficiency": 0.50}
        ),
        "medium": MappingProxyType(
            {"threshold": 0.50, "target_background_efficiency": 0.20}
        ),
        "tight": MappingProxyType(
            {"threshold": 0.75, "target_background_efficiency": 0.10}
        ),
    }
)


def _bin_efficiencies(*, offset: float = 0.0) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for index, mass_bin in enumerate(BIN_NAMES):
        effective_count = 100.0 + index
        for name, target in (("loose", 0.50), ("medium", 0.20), ("tight", 0.10)):
            efficiency = target + offset
            rows.append(
                {
                    "mass_bin": mass_bin,
                    "working_point": name,
                    "numerator": efficiency * effective_count,
                    "denominator": effective_count,
                    "efficiency": efficiency,
                    "effective_count": effective_count,
                    "standard_error": math.sqrt(
                        efficiency * (1.0 - efficiency) / effective_count
                    ),
                }
            )
    return pd.DataFrame(rows).set_index(["mass_bin", "working_point"])


def _evidence(iteration: int, *, offset: float = 0.0) -> IterationEvidence:
    return IterationEvidence(
        iteration=iteration,
        cumulative_multipliers=MappingProxyType(
            {name: 0.4 + 0.1 * index + iteration for index, name in enumerate(BIN_NAMES)}
        ),
        candidate_name="depth2_child5",
        final_tree_count=17,
        weighted_oof_auc=0.79 + 0.01 * iteration,
        working_points=POINTS,
        zz_ks_distances=MappingProxyType(
            {"loose": 0.08, "medium": 0.06, "tight": 0.04}
        ),
        signal_efficiencies=MappingProxyType(
            {"loose": 0.70, "medium": 0.50, "tight": 0.30}
        ),
        achieved_zz_efficiencies=MappingProxyType(
            {"loose": 0.50, "medium": 0.20, "tight": 0.10}
        ),
        bin_efficiencies=_bin_efficiencies(offset=offset),
        eligible=iteration == 1,
        eligibility_reasons=() if iteration == 1 else ("loose_zz_ks_above_limit",),
    )


def _scored_rows(score_column: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "label": [0, 0, 0, 0, 1],
            "m4l": [107.5, 112.5, 127.5, 157.5, 125.0],
            "physical_weight": [-2.0, 3.0, -5.0, 7.0, 1.0],
            score_column: [0.25, 0.50, 0.75, 0.90, 0.95],
            "training_multiplier": [99.0, 98.0, 97.0, 96.0, 1.0],
        }
    )


def _outcome(*, selected: bool = True) -> ReweightingStudyOutcome:
    return ReweightingStudyOutcome(
        status="eligible_iteration_test_reproduced" if selected else "no_eligible_iteration",
        iterations=(_evidence(0), _evidence(1, offset=0.01)),
        selected_iteration=1 if selected else None,
        selected_oof_scores=_scored_rows("oof_score") if selected else None,
        model=None,
        test_scores=_scored_rows("score") if selected else None,
        test_metrics=None,
    )


def test_iteration_tradeoff_png_uses_all_iterations_audit_heatmap_and_fixed_gates(
    monkeypatch,
):
    """Dropping an iteration, audit multiplier, or gate reference misstates OOF evidence."""
    lines: list[tuple[str, float]] = []
    series: list[tuple[float, ...]] = []
    heatmaps: list[np.ndarray] = []
    original_plot = matplotlib.axes.Axes.plot
    original_imshow = matplotlib.axes.Axes.imshow

    def capture_hline(axis, value, *args, **kwargs):
        lines.append(("horizontal", float(value)))
        return original_hline(axis, value, *args, **kwargs)

    def capture_plot(axis, values, *args, **kwargs):
        series.append(tuple(np.asarray(values, dtype=float)))
        return original_plot(axis, values, *args, **kwargs)

    def capture_imshow(axis, values, *args, **kwargs):
        heatmaps.append(np.asarray(values, dtype=float).copy())
        return original_imshow(axis, values, *args, **kwargs)

    original_hline = matplotlib.axes.Axes.axhline
    monkeypatch.setattr(matplotlib.axes.Axes, "axhline", capture_hline)
    monkeypatch.setattr(matplotlib.axes.Axes, "plot", capture_plot)
    monkeypatch.setattr(matplotlib.axes.Axes, "imshow", capture_imshow)

    payload = build_iteration_tradeoff_png(_outcome())

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert ("horizontal", 0.80) in lines
    assert ("horizontal", 0.10) in lines
    assert (0.0, 1.0) in series
    assert len(heatmaps) == 1
    assert heatmaps[0].shape == (2, 11)
    np.testing.assert_allclose(
        heatmaps[0],
        [
            list(_outcome().iterations[0].cumulative_multipliers.values()),
            list(_outcome().iterations[1].cumulative_multipliers.values()),
        ],
    )


def test_zz_efficiency_png_uses_fixed_centers_physical_table_and_effective_binomial_errors(
    monkeypatch,
):
    """Replacing physical OOF statistics with training multipliers breaks plotted uncertainty."""
    calls: list[dict[str, np.ndarray]] = []
    original_errorbar = matplotlib.axes.Axes.errorbar

    def capture_errorbar(axis, x, y, *args, **kwargs):
        calls.append(
            {
                "x": np.asarray(x, dtype=float).copy(),
                "y": np.asarray(y, dtype=float).copy(),
                "yerr": np.asarray(kwargs["yerr"], dtype=float).copy(),
            }
        )
        return original_errorbar(axis, x, y, *args, **kwargs)

    monkeypatch.setattr(matplotlib.axes.Axes, "errorbar", capture_errorbar)

    payload = build_zz_efficiency_by_mass_png(_outcome())

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(calls) == 3
    np.testing.assert_allclose(calls[0]["x"], np.arange(107.5, 160.0, 5.0))
    table = _outcome().iterations[-1].bin_efficiencies
    for call, name in zip(calls, ("loose", "medium", "tight"), strict=True):
        values = table.xs(name, level="working_point").reindex(BIN_NAMES)
        np.testing.assert_allclose(call["y"], values["efficiency"].to_numpy())
        np.testing.assert_allclose(
            call["yerr"],
            np.sqrt(
                values["efficiency"].to_numpy()
                * (1.0 - values["efficiency"].to_numpy())
                / values["effective_count"].to_numpy()
            ),
        )


def test_zz_efficiency_png_draws_exact_three_target_lines(monkeypatch):
    """Changing a predeclared target line makes the OOF comparison misleading."""
    values: list[float] = []
    original_hline = matplotlib.axes.Axes.axhline

    def capture_hline(axis, value, *args, **kwargs):
        values.append(float(value))
        return original_hline(axis, value, *args, **kwargs)

    monkeypatch.setattr(matplotlib.axes.Axes, "axhline", capture_hline)

    build_zz_efficiency_by_mass_png(_outcome())

    assert values == [0.50, 0.20, 0.10]


def test_selected_mass_png_uses_absolute_physical_weights_and_oof_frozen_thresholds(
    monkeypatch,
):
    """Using fitting weights or test-derived cuts would falsify OOF/test ZZ shapes."""
    calls: list[dict[str, object]] = []
    original_hist = matplotlib.axes.Axes.hist

    def capture_hist(axis, values, *args, **kwargs):
        calls.append(
            {
                "masses": np.asarray(values, dtype=float).copy(),
                "weights": np.asarray(kwargs["weights"], dtype=float).copy(),
                "label": kwargs["label"],
            }
        )
        return original_hist(axis, values, *args, **kwargs)

    monkeypatch.setattr(matplotlib.axes.Axes, "hist", capture_hist)

    payload = build_selected_mass_sculpting_png(_outcome())

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(calls) == 8
    np.testing.assert_allclose(calls[0]["weights"], [2.0, 3.0, 5.0, 7.0])
    np.testing.assert_allclose(calls[1]["masses"], [107.5, 112.5, 127.5, 157.5])
    np.testing.assert_allclose(calls[2]["masses"], [112.5, 127.5, 157.5])
    np.testing.assert_allclose(calls[3]["masses"], [127.5, 157.5])
    np.testing.assert_allclose(calls[4]["weights"], [2.0, 3.0, 5.0, 7.0])
    np.testing.assert_allclose(calls[5]["masses"], [107.5, 112.5, 127.5, 157.5])
    np.testing.assert_allclose(calls[6]["masses"], [112.5, 127.5, 157.5])
    np.testing.assert_allclose(calls[7]["masses"], [127.5, 157.5])
    assert "OOF" in str(calls[1]["label"])
    assert "test" in str(calls[5]["label"])


@pytest.mark.parametrize(
    "builder",
    [build_iteration_tradeoff_png, build_zz_efficiency_by_mass_png],
)
def test_nonselected_builders_accept_no_eligible_synthetic_outcomes(builder):
    """Development-only plots must remain available when no iteration is selected."""
    assert builder(_outcome(selected=False)).startswith(b"\x89PNG\r\n\x1a\n")


def test_selected_mass_png_rejects_no_selected_outcome_before_test_access():
    """Reading test evidence on a no-selection terminal breaks the sealed test boundary."""
    class NoSelectionOutcome:
        selected_iteration = None
        selected_oof_scores = None

        @property
        def test_scores(self):
            pytest.fail("selected-mass plot accessed sealed test scores")

    with pytest.raises(ValueError, match="selected OOF iteration"):
        build_selected_mass_sculpting_png(NoSelectionOutcome())


@pytest.mark.parametrize(
    "builder",
    [
        build_iteration_tradeoff_png,
        build_zz_efficiency_by_mass_png,
        build_selected_mass_sculpting_png,
    ],
)
def test_builders_publish_only_to_memory_buffers(builder, monkeypatch):
    """Passing a pathname to Matplotlib would create an unreviewed plot artifact."""
    destinations: list[object] = []
    original_savefig = matplotlib.figure.Figure.savefig

    def capture_savefig(figure, destination, *args, **kwargs):
        destinations.append(destination)
        return original_savefig(figure, destination, *args, **kwargs)

    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", capture_savefig)

    assert builder(_outcome()).startswith(b"\x89PNG\r\n\x1a\n")
    assert len(destinations) == 1
    assert isinstance(destinations[0], BytesIO)


@pytest.mark.parametrize(
    "builder",
    [
        build_iteration_tradeoff_png,
        build_zz_efficiency_by_mass_png,
        build_selected_mass_sculpting_png,
    ],
)
def test_builders_reject_empty_or_nonfinite_plot_evidence(builder):
    """Empty or non-finite evidence must not be rendered as a plausible diagnostic."""
    if builder is build_iteration_tradeoff_png:
        outcome = _outcome()
        outcome = ReweightingStudyOutcome(
            **{**outcome.__dict__, "iterations": ()}
        )
    elif builder is build_zz_efficiency_by_mass_png:
        evidence = _evidence(0)
        outcome = ReweightingStudyOutcome(
            **{**_outcome().__dict__, "iterations": (evidence,)}
        )
        outcome.iterations[0].bin_efficiencies.iloc[0, 2] = np.nan
    else:
        outcome = _outcome()
        outcome.selected_oof_scores.loc[0, "physical_weight"] = np.nan
    with pytest.raises(ValueError, match="non-empty|finite"):
        builder(outcome)
