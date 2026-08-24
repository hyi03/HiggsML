"""Frozen configuration contract for the MC-only flatness study."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml


_FEATURES = (
    "lep1_pt",
    "lep2_pt",
    "lep1_eta",
    "lep2_eta",
    "lep3_eta",
    "lep4_eta",
    "pt4l",
    "deltaR_Z1",
    "deltaR_Z2",
    "deltaPhi_ZZ",
)
_COEFFICIENTS = (0.0, 0.5, 1.0, 2.0, 3.0)
_WORKING_POINTS = {"loose": 0.50, "medium": 0.20, "tight": 0.10}
_MODEL = {
    "type": "hep_ml.UGradientBoostingClassifier",
    "n_estimators": 300,
    "learning_rate": 0.05,
    "max_depth": 3,
    "min_samples_leaf": 50,
    "subsample": 0.8,
    "random_seed": 42,
}
_FLATNESS = {
    "type": "hep_ml.losses.KnnFlatnessLossFunction",
    "uniform_feature": "m4l",
    "uniform_label": 0,
    "n_neighbours": 100,
    "max_groups": 5000,
    "power": 2.0,
    "allow_wrong_signs": True,
}
_COMMON_ARTIFACTS = frozenset(
    {
        "artifacts/candidate_results.csv",
        "artifacts/working_point_metrics.csv",
        "artifacts/selection.json",
        "predictions/oof_scores.csv.gz",
        "plots/candidate_tradeoff.png",
        "plots/working_point_ks.png",
    }
)
_SELECTED_ARTIFACTS = frozenset(
    {
        "artifacts/test_metrics.json",
        "model/flatness_model.pkl",
        "predictions/selected_oof_scores.csv.gz",
        "predictions/test_scores.csv.gz",
        "plots/selected_mass_sculpting.png",
    }
)


@dataclass(frozen=True)
class DecorrelationConfig:
    schema_version: str
    input_run: str
    input_manifest_sha256: str
    input_mc_sha256: str
    features: tuple[str, ...]
    folds: int
    model: Mapping[str, Any]
    flatness: Mapping[str, Any]
    coefficients: tuple[float, ...]
    working_points: Mapping[str, float]
    auc_floor: float
    ks_limit: float
    require_signal_efficiency_above_background: bool
    artifacts_no_selection: tuple[str, ...]
    artifacts_selected: tuple[str, ...]

    @property
    def mass_bins_gev(self) -> tuple[float, ...]:
        return tuple(float(value) for value in range(105, 165, 5))

    @property
    def ks_distance_limit(self) -> float:
        return self.ks_limit


def approved_decorrelation_artifacts(*, selected: bool) -> set[str]:
    return set(
        _COMMON_ARTIFACTS
        | (_SELECTED_ARTIFACTS if selected else frozenset())
    )


def _expected_config() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "input_run": "runs/full-baseline-363490-2026-08-11-r2",
        "input_manifest_sha256": (
            "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8"
        ),
        "input_mc_sha256": (
            "1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e"
        ),
        "features": list(_FEATURES),
        "folds": 5,
        "model": dict(_MODEL),
        "flatness": dict(_FLATNESS),
        "coefficients": list(_COEFFICIENTS),
        "working_points": dict(_WORKING_POINTS),
        "auc_floor": 0.80,
        "ks_limit": 0.10,
        "require_signal_efficiency_above_background": True,
        "artifacts_no_selection": sorted(_COMMON_ARTIFACTS),
        "artifacts_selected": sorted(_COMMON_ARTIFACTS | _SELECTED_ARTIFACTS),
    }


def load_decorrelation_config(path: str | Path) -> DecorrelationConfig:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ValueError("decorrelation config is not valid YAML") from error
    if not isinstance(raw, dict):
        raise ValueError("decorrelation config must be a mapping")

    expected = _expected_config()
    comparable = dict(raw)
    for key in ("artifacts_no_selection", "artifacts_selected"):
        value = comparable.get(key)
        if isinstance(value, list):
            comparable[key] = sorted(value)
    if comparable != expected:
        raise ValueError("decorrelation config changed a frozen decision")

    return DecorrelationConfig(
        schema_version="1.0",
        input_run=expected["input_run"],
        input_manifest_sha256=expected["input_manifest_sha256"],
        input_mc_sha256=expected["input_mc_sha256"],
        features=_FEATURES,
        folds=5,
        model=MappingProxyType(dict(_MODEL)),
        flatness=MappingProxyType(dict(_FLATNESS)),
        coefficients=_COEFFICIENTS,
        working_points=MappingProxyType(dict(_WORKING_POINTS)),
        auc_floor=0.80,
        ks_limit=0.10,
        require_signal_efficiency_above_background=True,
        artifacts_no_selection=tuple(raw["artifacts_no_selection"]),
        artifacts_selected=tuple(raw["artifacts_selected"]),
    )
