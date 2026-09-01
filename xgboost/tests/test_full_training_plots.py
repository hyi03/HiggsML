import builtins
import importlib
import sys

import numpy as np
import pandas as pd
import pytest

from src.features import FEATURES
from src.full_training_evaluation import build_working_points
from src.full_training_model import CandidateResult, FoldMetric
from src.full_training_policy import load_training_policy


PLOT_NAMES = {
    "roc_curve.png",
    "score_distributions.png",
    "cv_stability.png",
    "feature_importance.png",
    "mc_mass_sculpting.png",
    "mc_mass_signal_background.png",
    "mc_mass_working_points.png",
}


class _FeatureModel:
    feature_importances_ = np.linspace(1.0, 2.0, len(FEATURES))


@pytest.fixture
def policy():
    return load_training_policy("config/full_training.yaml")


@pytest.fixture
def scored_frames():
    def frame(offset: float) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "label": [0, 0, 0, 0, 1, 1, 1, 1],
                "score": [0.10, 0.35, 0.70, 0.90, 0.20, 0.55, 0.75, 0.95],
                "physical_weight": [1.0, -2.0, 1.0, 2.0, 1.0, -1.0, 2.0, 1.0],
                "m4l": [106.0, 114.0, 122.0, 150.0, 118.0, 126.0, 138.0, 156.0],
            }
        ).assign(score=lambda values: values["score"] + offset)

    return frame(0.0), frame(-0.02)


@pytest.fixture
def cv_results(policy):
    return tuple(
        CandidateResult(
            candidate=candidate,
            folds=tuple(
                FoldMetric(
                    fold=fold,
                    weighted_auc=0.70 + 0.01 * index + 0.001 * fold,
                    unweighted_auc=0.69 + 0.01 * index + 0.001 * fold,
                    best_iteration=10 + fold,
                )
                for fold in range(policy.folds)
            ),
            mean_weighted_auc=0.70 + 0.01 * index,
            standard_error_weighted_auc=0.002,
        )
        for index, candidate in enumerate(policy.candidates)
    )


def _plots_module():
    return importlib.import_module("src.full_training_plots")


def test_save_full_training_plots_creates_only_seven_nonempty_mc_pngs(
    tmp_path, policy, scored_frames, cv_results
):
    """Writing an alternate or empty plot artifact would break the frozen run contract."""
    oof, test = scored_frames
    working_points = build_working_points(oof, policy.working_points)
    output_dir = tmp_path / "plots"

    _plots_module().save_full_training_plots(
        oof, test, cv_results, _FeatureModel(), working_points, policy, output_dir
    )

    assert {path.name for path in output_dir.iterdir()} == PLOT_NAMES
    assert all((output_dir / name).stat().st_size > 0 for name in PLOT_NAMES)
    assert not [path for path in tmp_path.iterdir() if path != output_dir]


@pytest.mark.parametrize("column", ["label", "split"])
def test_invalid_data_rows_raise_before_plotting_imports(
    monkeypatch, tmp_path, policy, scored_frames, cv_results, column
):
    """A real-data row must be rejected before matplotlib can be imported."""
    sys.modules.pop("src.full_training_plots", None)
    imported = []
    original_import = builtins.__import__

    def recording_import(name, *args, **kwargs):
        if name.startswith("matplotlib"):
            imported.append(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", recording_import)
    oof, test = scored_frames
    if column == "label":
        oof = oof.copy()
        oof.loc[0, "label"] = -1
    else:
        oof = oof.assign(split="data")
    working_points = build_working_points(test, policy.working_points)

    with pytest.raises(ValueError, match="MC"):
        _plots_module().save_full_training_plots(
            oof, test, cv_results, _FeatureModel(), working_points, policy, tmp_path / "plots"
        )

    assert imported == []


@pytest.mark.parametrize("target_kind", ["outside_symlink", "dangling_symlink", "regular_file"])
def test_existing_plot_target_is_rejected_before_plotting(
    monkeypatch, tmp_path, policy, scored_frames, cv_results, target_kind
):
    """An existing fixed target could otherwise redirect or overwrite a plot."""
    module = _plots_module()
    oof, test = scored_frames
    working_points = build_working_points(oof, policy.working_points)
    output_dir = tmp_path / "plots"
    output_dir.mkdir()
    target = output_dir / "roc_curve.png"
    sentinel = tmp_path / "outside-sentinel"
    sentinel.write_bytes(b"do-not-change")
    if target_kind == "outside_symlink":
        target.symlink_to(sentinel)
    elif target_kind == "dangling_symlink":
        target.symlink_to(tmp_path / "missing-target")
    else:
        target.write_bytes(b"existing")
    plotting_calls = []
    monkeypatch.setattr(module, "_plotting_dependencies", lambda: plotting_calls.append(True))

    with pytest.raises(ValueError, match="existing"):
        module.save_full_training_plots(
            oof, test, cv_results, _FeatureModel(), working_points, policy, output_dir
        )

    assert plotting_calls == []
    assert sentinel.read_bytes() == b"do-not-change"


def test_plot_titles_are_mc_and_mass_axes_cover_policy_bins(
    monkeypatch, tmp_path, policy, scored_frames, cv_results
):
    """A data-labelled title or clipped mass range would misstate the MC diagnostic."""
    import matplotlib.figure

    captured = {}
    original_savefig = matplotlib.figure.Figure.savefig

    def capture_figure(figure, *args, **kwargs):
        captured[args[0].name] = [
            {
                "title": axis.get_title(),
                "xlabel": axis.get_xlabel(),
                "ylabel": axis.get_ylabel(),
                "xlim": axis.get_xlim(),
                "legend": (
                    []
                    if axis.get_legend() is None
                    else [text.get_text() for text in axis.get_legend().get_texts()]
                ),
                "has_zero_line": any(
                    len(line.get_ydata()) == 2
                    and np.allclose(line.get_ydata(), [0.0, 0.0])
                    for line in axis.get_lines()
                ),
            }
            for axis in figure.axes
        ]
        return original_savefig(figure, *args, **kwargs)

    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", capture_figure)
    oof, test = scored_frames
    working_points = build_working_points(oof, policy.working_points)

    _plots_module().save_full_training_plots(
        oof, test, cv_results, _FeatureModel(), working_points, policy, tmp_path / "plots"
    )

    assert captured
    assert set(captured) == PLOT_NAMES
    titles = [axis["title"] for axes in captured.values() for axis in axes if axis["title"]]
    assert all("MC" in title for title in titles)
    assert not any(
        banned in title.lower()
        for title in titles
        for banned in ("data", "observ", "discover")
    )
    mass_axes = [
        axis for axes in captured.values() for axis in axes if axis["xlabel"] == "m4l [GeV]"
    ]
    assert mass_axes
    assert all(
        axis["xlim"] == (105.0, 160.0) for axis in mass_axes
    )

    signal_background = captured["mc_mass_signal_background.png"]
    assert all(axis["xlabel"] == "m4l [GeV]" for axis in signal_background)
    assert {axis["ylabel"] for axis in signal_background} == {
        "Signed MC physical yield",
        "MC absolute physical weight (unit area per class)",
    }
    assert all(
        {"Higgs MC", "ZZ MC"}.issubset(axis["legend"])
        for axis in signal_background
    )
    assert any(axis["has_zero_line"] for axis in signal_background)

    working_points = captured["mc_mass_working_points.png"]
    assert all(axis["xlabel"] == "m4l [GeV]" for axis in working_points)
    assert all(
        {"Inclusive", "Loose", "Medium", "Tight"}.issubset(
            {name.split(" ")[0] for name in axis["legend"]}
        )
        and all(class_name in " ".join(axis["legend"]) for class_name in ("Higgs MC", "ZZ MC"))
        for axis in working_points
    )


def _capture_histogram_calls(monkeypatch):
    import matplotlib.axes
    import matplotlib.figure

    calls = []
    original_histogram = matplotlib.axes.Axes.hist
    original_savefig = matplotlib.figure.Figure.savefig

    def recording_histogram(axis, values, *args, **kwargs):
        calls.append(
            {
                "axis": axis,
                "values": np.asarray(values, dtype=float).copy(),
                "weights": np.asarray(kwargs.get("weights"), dtype=float).copy(),
                "label": kwargs.get("label"),
            }
        )
        return original_histogram(axis, values, *args, **kwargs)

    def recording_savefig(figure, *args, **kwargs):
        for call in calls:
            if call["axis"].figure is figure:
                call["title"] = call["axis"].get_title()
        return original_savefig(figure, *args, **kwargs)

    monkeypatch.setattr(matplotlib.axes.Axes, "hist", recording_histogram)
    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", recording_savefig)
    return calls


def test_mass_signal_background_histograms_preserve_signed_and_normalized_weights(
    monkeypatch, tmp_path, policy, scored_frames, cv_results
):
    """Using absolute or globally normalized yield weights would hide negative MC bins."""
    calls = _capture_histogram_calls(monkeypatch)
    oof, test = scored_frames
    working_points = build_working_points(oof, policy.working_points)

    _plots_module().save_full_training_plots(
        oof, test, cv_results, _FeatureModel(), working_points, policy, tmp_path / "plots"
    )

    expected = {
        "ZZ MC": {
            "m4l": np.array([106.0, 114.0, 122.0, 150.0]),
            "signed": np.array([1.0, -2.0, 1.0, 2.0]),
            "shape": np.array([1.0, 2.0, 1.0, 2.0]) / 6.0,
        },
        "Higgs MC": {
            "m4l": np.array([118.0, 126.0, 138.0, 156.0]),
            "signed": np.array([1.0, -1.0, 2.0, 1.0]),
            "shape": np.array([1.0, 1.0, 2.0, 1.0]) / 5.0,
        },
    }
    for split_name in ("OOF", "Test"):
        signed_title = f"{split_name} MC inclusive m4l signed physical yields"
        shape_title = f"{split_name} MC inclusive m4l unit-area shapes"
        for class_name, expected_values in expected.items():
            signed = next(
                call
                for call in calls
                if call["title"] == signed_title
                and call["label"] == class_name
            )
            shape = next(
                call
                for call in calls
                if call["title"] == shape_title
                and call["label"] == class_name
            )
            np.testing.assert_array_equal(signed["values"], expected_values["m4l"])
            np.testing.assert_array_equal(signed["weights"], expected_values["signed"])
            assert np.any(signed["weights"] < 0.0)
            np.testing.assert_array_equal(shape["values"], expected_values["m4l"])
            np.testing.assert_allclose(shape["weights"], expected_values["shape"])
            assert shape["weights"].sum() == pytest.approx(1.0)


def test_mass_working_point_histograms_apply_supplied_frozen_scores(
    monkeypatch, tmp_path, policy, scored_frames, cv_results
):
    """Selecting a mass curve with m4l instead of the frozen score would be invalid."""
    calls = _capture_histogram_calls(monkeypatch)
    oof, test = scored_frames
    frozen_points = {
        "loose": {"threshold": 0.34},
        "medium": {"threshold": 0.72},
        "tight": {"threshold": 0.92},
    }

    _plots_module().save_full_training_plots(
        oof, test, cv_results, _FeatureModel(), frozen_points, policy, tmp_path / "plots"
    )

    expected = {
        "OOF": {
            "ZZ": {
                "Loose": ([114.0, 122.0, 150.0], [-2.0, 1.0, 2.0]),
                "Medium": ([150.0], [2.0]),
                "Tight": ([], []),
            },
            "Higgs": {
                "Loose": ([126.0, 138.0, 156.0], [-1.0, 2.0, 1.0]),
                "Medium": ([138.0, 156.0], [2.0, 1.0]),
                "Tight": ([156.0], [1.0]),
            },
        },
        "Test": {
            "ZZ": {
                "Loose": ([122.0, 150.0], [1.0, 2.0]),
                "Medium": ([150.0], [2.0]),
                "Tight": ([], []),
            },
            "Higgs": {
                "Loose": ([126.0, 138.0, 156.0], [-1.0, 2.0, 1.0]),
                "Medium": ([138.0, 156.0], [2.0, 1.0]),
                "Tight": ([156.0], [1.0]),
            },
        },
    }
    for split_name, by_class in expected.items():
        title = f"{split_name} MC m4l working points (frozen OOF thresholds)"
        for class_name, by_point in by_class.items():
            for point_name, (masses, weights) in by_point.items():
                threshold = frozen_points[point_name.lower()]["threshold"]
                label = (
                    f"{point_name} {class_name} MC "
                    f"(score >= frozen {threshold:.3f})"
                )
                call = next(
                    call
                    for call in calls
                    if call["title"] == title and call["label"] == label
                )
                np.testing.assert_array_equal(call["values"], np.asarray(masses))
                np.testing.assert_array_equal(call["weights"], np.asarray(weights))
