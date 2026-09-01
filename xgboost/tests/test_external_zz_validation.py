from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from src.features import FEATURES


def _module():
    assert importlib.util.find_spec("src.external_zz_validation") is not None
    return importlib.import_module("src.external_zz_validation")


def _feature_values(base: float) -> dict[str, float]:
    return {
        name: base + 0.001 * index
        for index, name in enumerate(FEATURES)
    }


def _external_frame() -> pd.DataFrame:
    rows = []
    for index, (score, weight) in enumerate(
        ((0.10, 1.0), (0.40, -2.0), (0.70, 3.0), (0.90, 4.0))
    ):
        rows.append(
            {
                **_feature_values(score),
                "m4l": 108.0 + 10.0 * index,
                "eventNumber": 100 + index,
                "channelNumber": 700600,
                "split": ("train", "validation", "test", "train")[index],
                "label": 0,
                "physical_weight": weight,
                "score": score,
            }
        )
    return pd.DataFrame(rows)


def _training_test_frame() -> pd.DataFrame:
    rows = []
    specs = (
        (0, 363490, 0.15, 1.0, 109.0),
        (0, 363490, 0.55, -2.0, 132.0),
        (0, 363490, 0.80, 3.0, 154.0),
        (1, 345060, 0.60, 2.0, 124.0),
        (1, 345060, 0.95, -1.0, 126.0),
    )
    for index, (label, channel, score, weight, mass) in enumerate(specs):
        rows.append(
            {
                **_feature_values(score + 0.02),
                "m4l": mass,
                "eventNumber": 500 + index,
                "channelNumber": channel,
                "split": "test",
                "label": label,
                "physical_weight": weight,
                "score": score,
            }
        )
    return pd.DataFrame(rows)


class _FrozenModel:
    def __init__(self) -> None:
        self.received_columns: list[str] | None = None

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        self.received_columns = list(frame.columns)
        scores = np.linspace(0.2, 0.8, len(frame))
        return np.column_stack([1.0 - scores, scores])


def _working_points() -> dict[str, dict[str, float]]:
    return {
        "loose": {"threshold": 0.25},
        "medium": {"threshold": 0.65},
        "tight": {"threshold": 0.85},
    }


def test_score_external_zz_uses_frozen_features_and_returns_only_audit_columns():
    """Adding provenance, mass, or weights to model inputs would leak audit data."""
    frame = _external_frame().drop(columns="score")
    model = _FrozenModel()

    scored = _module().score_external_zz(model, frame)

    assert model.received_columns == FEATURES
    assert list(scored.columns) == [
        "channelNumber",
        "eventNumber",
        "split",
        "label",
        "physical_weight",
        "m4l",
        "mZ1",
        "mZ2",
        "pt4l",
        "score",
    ]
    np.testing.assert_allclose(scored["score"], [0.2, 0.4, 0.6, 0.8])


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda frame: frame.assign(label=1), "label 0"),
        (lambda frame: frame.assign(label=-1), "label 0"),
        (lambda frame: frame.assign(channelNumber=363490), "700600"),
        (lambda frame: frame.assign(split="data"), "data split"),
        (
            lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True),
            "unique",
        ),
        (
            lambda frame: frame.assign(
                **{FEATURES[0]: [np.nan, 0.2, 0.3, 0.4]}
            ),
            "finite",
        ),
        (
            lambda frame: frame.assign(
                physical_weight=[1.0, np.inf, 3.0, 4.0]
            ),
            "finite",
        ),
        (
            lambda frame: frame.assign(
                eventNumber=[100.0, 101.0, 102.0, 103.0]
            ),
            "canonical integers",
        ),
        (
            lambda frame: frame.assign(eventNumber=[True, False, 2, 3]),
            "canonical integers",
        ),
        (lambda frame: frame.assign(label=0.0), "canonical integers"),
    ],
)
def test_score_external_zz_rejects_unsafe_external_rows(mutation, message):
    """A non-700600, data, duplicate, or non-finite row cannot enter validation."""
    frame = mutation(_external_frame().drop(columns="score"))

    with pytest.raises(ValueError, match=message):
        _module().score_external_zz(_FrozenModel(), frame)


def test_large_distinct_integer_identities_are_not_rounded_through_float():
    """Distinct int64 event IDs above 2**53 must remain distinct and auditable."""
    frame = _external_frame().drop(columns="score")
    frame["eventNumber"] = [2**53, 2**53 + 1, 2**53 + 2, 2**53 + 3]

    scored = _module().score_external_zz(_FrozenModel(), frame)

    assert scored["eventNumber"].tolist() == [
        2**53,
        2**53 + 1,
        2**53 + 2,
        2**53 + 3,
    ]


def test_evaluate_external_zz_uses_only_frozen_test_higgs_for_external_auc():
    """Training ZZ or development rows must not contaminate the external AUC."""
    training = _training_test_frame()
    external = _external_frame()

    report = _module().evaluate_external_zz(
        training, external, _working_points()
    )

    higgs = training.loc[training["label"] == 1]
    expected = pd.concat([higgs, external], ignore_index=True)
    expected_auc = roc_auc_score(
        expected["label"],
        expected["score"],
        sample_weight=np.abs(expected["physical_weight"]),
    )
    assert report["external_auc"]["weighted_auc"] == pytest.approx(expected_auc)
    assert report["external_auc"]["higgs_test_rows"] == 2
    assert report["external_auc"]["external_zz_rows"] == 4
    assert report["reference_test_zz_rows"] == 3
    assert set(report["weighted_ks_distances"]) == {
        "score",
        "mZ1",
        "mZ2",
        "pt4l",
        "m4l",
    }
    json.dumps(report, allow_nan=False)


def test_external_working_points_use_absolute_weights_and_effective_size_uncertainty():
    """Signed cancellation or raw-count errors would misstate 700600 efficiency."""
    report = _module().evaluate_external_zz(
        _training_test_frame(), _external_frame(), _working_points()
    )

    loose = report["working_points"]["loose"]
    absolute = np.array([1.0, 2.0, 3.0, 4.0])
    efficiency = (2.0 + 3.0 + 4.0) / absolute.sum()
    n_eff = absolute.sum() ** 2 / np.square(absolute).sum()
    sigma = np.sqrt(efficiency * (1.0 - efficiency) / n_eff)
    assert loose["background_efficiency"] == pytest.approx(efficiency)
    assert loose["effective_sample_size"] == pytest.approx(n_eff)
    assert loose["background_efficiency_uncertainty"] == pytest.approx(sigma)
    assert loose["selected_raw_count"] == 3


def test_evaluate_external_zz_rejects_non_test_training_rows():
    """A development row in the frozen test table would bias the external metric."""
    training = _training_test_frame()
    training.loc[0, "split"] = "validation"

    with pytest.raises(ValueError, match="test"):
        _module().evaluate_external_zz(training, _external_frame(), _working_points())


def test_save_external_zz_plots_creates_three_unit_area_dsid_labelled_mc_plots(
    tmp_path, monkeypatch
):
    """A yield-normalized or ambiguously labelled plot would confuse sample shape shifts."""
    import matplotlib.axes
    import matplotlib.figure

    histogram_calls = []
    captured = {}
    original_hist = matplotlib.axes.Axes.hist
    original_savefig = matplotlib.figure.Figure.savefig

    def recording_hist(axis, values, *args, **kwargs):
        histogram_calls.append(
            {
                "weights": np.asarray(kwargs["weights"], dtype=float).copy(),
                "label": kwargs.get("label"),
            }
        )
        return original_hist(axis, values, *args, **kwargs)

    def recording_savefig(figure, path, *args, **kwargs):
        captured[Path(path).name] = [
            (axis.get_title(), axis.get_xlabel(), axis.get_ylabel())
            for axis in figure.axes
        ]
        return original_savefig(figure, path, *args, **kwargs)

    monkeypatch.setattr(matplotlib.axes.Axes, "hist", recording_hist)
    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", recording_savefig)
    output = tmp_path / "plots"

    _module().save_external_zz_plots(
        _training_test_frame(), _external_frame(), _working_points(), output
    )

    expected_names = {
        "external_score_comparison.png",
        "external_kinematics_comparison.png",
        "external_mass_comparison.png",
    }
    assert {path.name for path in output.iterdir()} == expected_names
    assert set(captured) == expected_names
    assert all("MC" in title for axes in captured.values() for title, _, _ in axes if title)
    labels = {call["label"] for call in histogram_calls}
    assert any("363490" in label for label in labels)
    assert any("700600" in label for label in labels)
    assert all(call["weights"].sum() == pytest.approx(1.0) for call in histogram_calls)
    assert all("unit area" in ylabel.lower() for axes in captured.values() for _, _, ylabel in axes if ylabel)


def test_plot_validation_rejects_data_before_importing_matplotlib(tmp_path, monkeypatch):
    """Real data must be rejected before plotting libraries are reached."""
    module = _module()
    calls = []
    monkeypatch.setattr(module, "_plotting_dependencies", lambda: calls.append(True))

    with pytest.raises(ValueError, match="label 0"):
        module.save_external_zz_plots(
            _training_test_frame(),
            _external_frame().assign(label=-1),
            _working_points(),
            tmp_path / "plots",
        )

    assert calls == []
