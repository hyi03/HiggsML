"""Frozen-model, MC-only validation helpers for external DSID 700600."""

from __future__ import annotations

from collections.abc import Mapping
from numbers import Integral
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from .features import FEATURES
from .validation import weighted_ks_distance


AUDIT_COLUMNS = (
    "channelNumber",
    "eventNumber",
    "split",
    "label",
    "physical_weight",
    "m4l",
    "mZ1",
    "mZ2",
    "pt4l",
)
PLOT_NAMES = (
    "external_score_comparison.png",
    "external_kinematics_comparison.png",
    "external_mass_comparison.png",
)
_COMPARISON_COLUMNS = ("score", "mZ1", "mZ2", "pt4l", "m4l")
_WORKING_POINT_NAMES = ("loose", "medium", "tight")
_MC_SPLITS = frozenset({"train", "validation", "test"})


def score_external_zz(model, frame: pd.DataFrame) -> pd.DataFrame:
    """Score selected 700600 MC with an already-fitted model.

    The function deliberately exposes no fit or threshold-selection seam.  It
    validates the external sample before handing exactly ``FEATURES`` to the
    frozen classifier and emits only the fixed prediction-audit contract.
    """
    _validate_external_frame(frame, require_score=False)
    probabilities = np.asarray(
        model.predict_proba(frame.loc[:, FEATURES]), dtype=float
    )
    if probabilities.shape != (len(frame), 2):
        raise ValueError("frozen classifier predict_proba must return two columns")
    scores = probabilities[:, 1]
    if not np.isfinite(scores).all() or np.any((scores < 0.0) | (scores > 1.0)):
        raise ValueError("frozen classifier returned invalid probabilities")
    output = frame.loc[:, AUDIT_COLUMNS].copy()
    output["score"] = scores
    return output


def evaluate_external_zz(
    training_test: pd.DataFrame,
    external_zz: pd.DataFrame,
    working_points: Mapping,
) -> dict[str, object]:
    """Evaluate frozen test Higgs against newly scored external 700600 MC."""
    _validate_training_test(training_test)
    _validate_external_frame(external_zz, require_score=True)
    thresholds = _validated_thresholds(working_points)

    frozen_higgs = training_test.loc[training_test["label"] == 1]
    reference_zz = training_test.loc[training_test["label"] == 0]
    auc_frame = pd.concat([frozen_higgs, external_zz], ignore_index=True)
    labels = auc_frame["label"].to_numpy(dtype=int)
    scores = auc_frame["score"].to_numpy(dtype=float)
    weights = np.abs(auc_frame["physical_weight"].to_numpy(dtype=float))

    point_metrics = {
        name: _external_working_point(external_zz, threshold)
        for name, threshold in thresholds.items()
    }
    distances = {
        column: weighted_ks_distance(
            reference_zz[column],
            external_zz[column],
            reference_zz["physical_weight"],
            external_zz["physical_weight"],
        )
        for column in _COMPARISON_COLUMNS
    }
    return {
        "schema_version": "1.0",
        "reference_dsid": 363490,
        "external_dsid": 700600,
        "reference_test_zz_rows": int(len(reference_zz)),
        "external_auc": {
            "weighted_auc": float(
                roc_auc_score(labels, scores, sample_weight=weights)
            ),
            "unweighted_auc": float(roc_auc_score(labels, scores)),
            "higgs_test_rows": int(len(frozen_higgs)),
            "external_zz_rows": int(len(external_zz)),
        },
        "working_points": point_metrics,
        "weighted_ks_distances": distances,
    }


def save_external_zz_plots(
    training_test: pd.DataFrame,
    external_zz: pd.DataFrame,
    working_points: Mapping,
    output_dir: str | Path,
) -> None:
    """Save exactly three absolute-weight unit-area MC shape comparisons."""
    _validate_training_test(training_test)
    _validate_external_frame(external_zz, require_score=True)
    _validated_thresholds(working_points)
    destination = _prepare_output_dir(output_dir)
    reference = training_test.loc[training_test["label"] == 0]
    pyplot = _plotting_dependencies()

    figure, axis = pyplot.subplots(figsize=(7.2, 5.0))
    _shape_histograms(
        axis,
        reference,
        external_zz,
        "score",
        np.linspace(0.0, 1.0, 21),
    )
    axis.set(
        title="Frozen-test and external ZZ MC score shapes",
        xlabel="Frozen XGBoost score",
        ylabel="MC absolute physical weight (unit area per DSID)",
        xlim=(0.0, 1.0),
    )
    axis.legend()
    _save_and_close(pyplot, figure, destination / PLOT_NAMES[0])

    figure, axes = pyplot.subplots(2, 2, figsize=(11.0, 8.0))
    for axis, column, label, bins in zip(
        axes.flat[:3],
        ("mZ1", "mZ2", "pt4l"),
        ("mZ1 [GeV]", "mZ2 [GeV]", "pt4l [GeV]"),
        (
            np.linspace(50.0, 106.0, 21),
            np.linspace(12.0, 115.0, 21),
            _shared_bins(reference["pt4l"], external_zz["pt4l"]),
        ),
        strict=True,
    ):
        _shape_histograms(axis, reference, external_zz, column, bins)
        axis.set(
            title=f"ZZ MC {label.split()[0]} shape",
            xlabel=label,
            ylabel="MC absolute physical weight (unit area per DSID)",
        )
    axes.flat[3].axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    axes.flat[3].legend(handles, labels, loc="center", title="MC samples")
    _save_and_close(pyplot, figure, destination / PLOT_NAMES[1])

    figure, axis = pyplot.subplots(figsize=(7.2, 5.0))
    _shape_histograms(
        axis,
        reference,
        external_zz,
        "m4l",
        np.linspace(105.0, 160.0, 23),
    )
    axis.set(
        title="Frozen-test and external ZZ MC m4l shapes",
        xlabel="m4l [GeV]",
        ylabel="MC absolute physical weight (unit area per DSID)",
        xlim=(105.0, 160.0),
    )
    axis.legend()
    _save_and_close(pyplot, figure, destination / PLOT_NAMES[2])


def _validate_external_frame(frame: pd.DataFrame, *, require_score: bool) -> None:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("external ZZ must be a non-empty DataFrame")
    required = {*AUDIT_COLUMNS, "score"} if require_score else {*FEATURES, *AUDIT_COLUMNS}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"external ZZ is missing columns: {missing}")
    labels = _integer_values(frame["label"], "external ZZ label")
    if set(labels) != {0}:
        raise ValueError("external ZZ rows must contain only label 0")
    channels = _integer_values(frame["channelNumber"], "external ZZ channelNumber")
    if set(channels) != {700600}:
        raise ValueError("external ZZ rows must contain only channel 700600")
    _validate_mc_splits(frame, "external ZZ")
    _validate_unique_identities(frame, "external ZZ")
    numeric_columns = (
        ["score", "mZ1", "mZ2", "pt4l", "m4l", "physical_weight"]
        if require_score
        else [*FEATURES, "m4l", "physical_weight"]
    )
    _require_finite(frame, numeric_columns, "external ZZ")
    if float(np.abs(frame["physical_weight"].to_numpy(dtype=float)).sum()) <= 0.0:
        raise ValueError("external ZZ must have positive total absolute weight")


def _validate_training_test(frame: pd.DataFrame) -> None:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("frozen training test must be a non-empty DataFrame")
    required = {*AUDIT_COLUMNS, "score"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"frozen training test is missing columns: {missing}")
    labels = _integer_values(frame["label"], "frozen training test label")
    if set(labels) != {0, 1}:
        raise ValueError("frozen training test must contain labels 0 and 1")
    if set(frame["split"]) != {"test"}:
        raise ValueError("frozen training score rows must all be independent test rows")
    channels = _integer_values(
        frame["channelNumber"], "frozen training test channelNumber"
    )
    if set(channels[labels == 0]) != {363490}:
        raise ValueError("frozen training background test rows must be DSID 363490")
    if set(channels[labels == 1]) != {345060}:
        raise ValueError("frozen training signal test rows must be Higgs DSID 345060")
    _validate_unique_identities(frame, "frozen training test")
    _require_finite(
        frame,
        ["score", "mZ1", "mZ2", "pt4l", "m4l", "physical_weight"],
        "frozen training test",
    )
    for label, name in ((0, "background"), (1, "signal")):
        total = float(
            np.abs(
                frame.loc[frame["label"] == label, "physical_weight"].to_numpy(
                    dtype=float
                )
            ).sum()
        )
        if total <= 0.0:
            raise ValueError(f"frozen training test {name} weight must be positive")


def _validate_mc_splits(frame: pd.DataFrame, name: str) -> None:
    values = set(frame["split"])
    if "data" in values:
        raise ValueError(f"{name} must not contain a data split")
    if not values <= _MC_SPLITS:
        raise ValueError(f"{name} contains an unknown MC split")


def _validate_unique_identities(frame: pd.DataFrame, name: str) -> None:
    events = _integer_values(frame["eventNumber"], f"{name} eventNumber")
    channels = _integer_values(frame["channelNumber"], f"{name} channelNumber")
    if np.any(events < 0) or np.any(channels < 0):
        raise ValueError(f"{name} identities must be canonical integers")
    if pd.MultiIndex.from_arrays([channels, events]).has_duplicates:
        raise ValueError(f"{name} channel/event identities must be unique")


def _integer_values(series: pd.Series, name: str) -> np.ndarray:
    normalized: list[int] = []
    minimum = int(np.iinfo(np.int64).min)
    maximum = int(np.iinfo(np.int64).max)
    for value in series.to_numpy():
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
            raise ValueError(f"{name} values must be canonical integers")
        integer = int(value)
        if integer < minimum or integer > maximum:
            raise ValueError(f"{name} values must be canonical integers")
        normalized.append(integer)
    return np.asarray(normalized, dtype=np.int64)


def _require_finite(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    try:
        values = frame.loc[:, columns].to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} values must be finite") from error
    if not np.isfinite(values).all():
        raise ValueError(f"{name} values must be finite")


def _validated_thresholds(points: Mapping) -> dict[str, float]:
    if not isinstance(points, Mapping) or set(points) != set(_WORKING_POINT_NAMES):
        raise ValueError("frozen working points must be exactly loose, medium, and tight")
    output: dict[str, float] = {}
    for name in _WORKING_POINT_NAMES:
        point = points[name]
        if not isinstance(point, Mapping):
            raise ValueError(f"frozen working point {name} must be a mapping")
        try:
            threshold = float(point["threshold"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"frozen working point {name} needs a finite threshold"
            ) from error
        if not np.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
            raise ValueError(f"frozen working point {name} needs a finite threshold")
        output[name] = threshold
    if any(
        first > second
        for first, second in zip(output.values(), list(output.values())[1:])
    ):
        raise ValueError("frozen working-point thresholds must be monotonic")
    return output


def _external_working_point(
    frame: pd.DataFrame, threshold: float
) -> dict[str, object]:
    scores = frame["score"].to_numpy(dtype=float)
    weights = np.abs(frame["physical_weight"].to_numpy(dtype=float))
    selected = scores >= threshold
    total = float(weights.sum())
    selected_weight = float(weights[selected].sum())
    efficiency = selected_weight / total
    effective_size = float(total**2 / np.square(weights).sum())
    uncertainty = float(
        np.sqrt(efficiency * (1.0 - efficiency) / effective_size)
    )
    return {
        "threshold": float(threshold),
        "raw_count": int(len(frame)),
        "selected_raw_count": int(selected.sum()),
        "absolute_weight": total,
        "selected_absolute_weight": selected_weight,
        "background_efficiency": float(efficiency),
        "effective_sample_size": effective_size,
        "background_efficiency_uncertainty": uncertainty,
    }


def _prepare_output_dir(output_dir: str | Path) -> Path:
    destination = Path(output_dir)
    if destination.is_symlink():
        raise ValueError("external plot output directory must not be a symlink")
    if destination.exists() and not destination.is_dir():
        raise ValueError("external plot output directory must be a directory")
    destination.mkdir(parents=True, exist_ok=True)
    resolved = destination.resolve()
    for name in PLOT_NAMES:
        target = destination / name
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"external plot target already exists: {target}")
        if target.parent.resolve() != resolved:
            raise ValueError("external plot target escaped output directory")
    return destination


def _plotting_dependencies():
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as pyplot

    return pyplot


def _shape_histograms(axis, reference, external, column: str, bins) -> None:
    for frame, label, color in (
        (reference, "ZZ DSID 363490 MC (frozen test)", "tab:blue"),
        (external, "ZZ DSID 700600 MC (external)", "tab:orange"),
    ):
        weights = np.abs(frame["physical_weight"].to_numpy(dtype=float))
        axis.hist(
            frame[column],
            bins=bins,
            weights=weights / weights.sum(),
            histtype="step",
            linewidth=1.8,
            color=color,
            label=label,
        )


def _shared_bins(first, second) -> np.ndarray:
    values = np.concatenate(
        (np.asarray(first, dtype=float), np.asarray(second, dtype=float))
    )
    lower = float(values.min())
    upper = float(values.max())
    if lower == upper:
        lower -= 0.5
        upper += 0.5
    return np.linspace(lower, upper, 21)


def _save_and_close(pyplot, figure, path: Path) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    pyplot.close(figure)
