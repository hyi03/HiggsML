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
_WORKING_POINTS = {
    "loose": 0.50,
    "medium": 0.20,
    "tight": 0.10,
}
_COEFFICIENTS = (0.0, 0.5, 1.0, 2.0, 3.0)
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
_TOP_LEVEL_KEYS = {
    "schema_version",
    "input_run",
    "input_manifest_sha256",
    "input_mc_sha256",
    "features",
    "folds",
    "model",
    "flatness",
    "coefficients",
    "working_points",
    "auc_floor",
    "ks_limit",
    "require_signal_efficiency_above_background",
    "artifacts_no_selection",
    "artifacts_selected",
}


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


def approved_decorrelation_artifacts(*, selected: bool) -> set[str]:
    return set(_COMMON_ARTIFACTS | (_SELECTED_ARTIFACTS if selected else frozenset()))


def load_decorrelation_config(path: str | Path) -> DecorrelationConfig:
    try:
        payload = Path(path).read_bytes()
    except OSError as error:
        raise ValueError("decorrelation config is not valid YAML") from error
    return _load_config_bytes(payload)


def _load_config_bytes(payload: bytes) -> DecorrelationConfig:
    try:
        raw = yaml.safe_load(payload)
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ValueError("decorrelation config is not valid YAML") from error
    if not isinstance(raw, dict) or set(raw) != _TOP_LEVEL_KEYS:
        raise ValueError("decorrelation config does not match an approved schema")
    if not _matches_frozen_decisions(raw):
        raise ValueError("decorrelation config changes a frozen decision")

    no_selection = raw.get("artifacts_no_selection")
    selected = raw.get("artifacts_selected")
    if (
        not isinstance(no_selection, list)
        or len(no_selection) != len(set(no_selection))
        or set(no_selection) != approved_decorrelation_artifacts(selected=False)
        or not isinstance(selected, list)
        or len(selected) != len(set(selected))
        or set(selected) != approved_decorrelation_artifacts(selected=True)
    ):
        raise ValueError(
            "conditional artifact allowlists do not match the approved contract"
        )

    return DecorrelationConfig(
        schema_version="1.0",
        input_run=raw["input_run"],
        input_manifest_sha256=raw["input_manifest_sha256"],
        input_mc_sha256=raw["input_mc_sha256"],
        features=_FEATURES,
        folds=5,
        model=MappingProxyType(dict(_MODEL)),
        flatness=MappingProxyType(dict(_FLATNESS)),
        coefficients=_COEFFICIENTS,
        working_points=MappingProxyType(dict(_WORKING_POINTS)),
        auc_floor=0.80,
        ks_limit=0.10,
        require_signal_efficiency_above_background=True,
        artifacts_no_selection=tuple(no_selection),
        artifacts_selected=tuple(selected),
    )


def _matches_frozen_decisions(raw: Mapping[str, Any]) -> bool:
    return (
        raw.get("schema_version") == "1.0"
        and raw.get("input_run") == "runs/full-baseline-363490-2026-08-11-r2"
        and raw.get("input_manifest_sha256")
        == "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8"
        and raw.get("input_mc_sha256")
        == "1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e"
        and raw.get("features") == list(_FEATURES)
        and type(raw.get("folds")) is int
        and raw["folds"] == 5
        and raw.get("model") == _MODEL
        and raw.get("flatness") == _FLATNESS
        and raw.get("coefficients") == list(_COEFFICIENTS)
        and raw.get("working_points") == _WORKING_POINTS
        and type(raw.get("auc_floor")) is float
        and raw["auc_floor"] == 0.80
        and type(raw.get("ks_limit")) is float
        and raw["ks_limit"] == 0.10
        and raw.get("require_signal_efficiency_above_background") is True
    )
