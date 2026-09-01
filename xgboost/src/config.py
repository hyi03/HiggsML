from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any, Mapping

import yaml

from .angular5 import ANGULAR5_FEATURES
from .features import FEATURES


ANGULAR19 = (*tuple(FEATURES), *tuple(ANGULAR5_FEATURES))
_SCHEMA_VERSION = "1.0"
_FORBIDDEN_FEATURES = (
    "m4l",
    "channelNumber",
    "eventNumber",
    "runNumber",
    "physical_weight",
    "train_weight",
    "source_sample",
    "source_entry",
)


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False):
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


@dataclass(frozen=True)
class PreprocessingProtocol:
    path: Path
    model_features: tuple[str, ...]
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class PreprocessingRunConfig:
    path: Path
    higgs_root: Path
    zz_root: Path
    chunk_size_events: int


@dataclass(frozen=True)
class XGBoostProtocol:
    path: Path
    features: tuple[str, ...]
    candidate: Mapping[str, int | float]
    common: Mapping[str, int | str]
    working_points: Mapping[str, float]
    qualification: Mapping[str, float | bool]
    raw: Mapping[str, Any]


def _load_mapping(path: str | Path) -> tuple[Path, dict[str, Any]]:
    source = Path(path)
    try:
        value = yaml.load(source.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML: {source}") from exc
    if not isinstance(value, dict):
        raise ValueError("configuration must be a mapping")
    return source, value


def _require_schema(raw: Mapping[str, Any]) -> None:
    if raw.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("schema_version must be the string '1.0'")


def _reject_unknown(raw: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown {label} keys: {sorted(unknown)}")


def _require_exact_keys(raw: Mapping[str, Any], expected: set[str], label: str) -> None:
    _reject_unknown(raw, expected, label)
    if set(raw) != expected:
        raise ValueError(f"{label} keys must be exactly {sorted(expected)}")


def _mapping(raw: Mapping[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _integer(value: Any, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"{name} must be a non-empty string list")
    return value


def _number_list(value: Any, name: str, *, length: int | None = None) -> list[float]:
    if not isinstance(value, list) or (length is not None and len(value) != length):
        suffix = f" with length {length}" if length is not None else ""
        raise ValueError(f"{name} must be a numeric list{suffix}")
    return [_finite_number(item, f"{name}[{index}]") for index, item in enumerate(value)]


def _validate_selection(selection: Mapping[str, Any]) -> None:
    expected = {
        "require_exactly_four_leptons",
        "allowed_lepton_types",
        "lepton_pt_thresholds_gev",
        "electron_max_abs_eta",
        "muon_max_abs_eta",
        "require_zero_charge",
        "min_all_sfos_mass_gev",
        "z1_mass_window_gev",
        "z2_mass",
        "m4l_window_gev",
        "lepton_quality",
    }
    _require_exact_keys(selection, expected, "selection")
    for name in ("require_exactly_four_leptons", "require_zero_charge"):
        _boolean(selection[name], f"selection.{name}")
    if selection["allowed_lepton_types"] != [11, 13]:
        raise ValueError("selection.allowed_lepton_types must equal [11, 13]")
    pt = _number_list(
        selection["lepton_pt_thresholds_gev"],
        "selection.lepton_pt_thresholds_gev",
        length=4,
    )
    if not all(value > 0 for value in pt) or pt != sorted(pt, reverse=True):
        raise ValueError("selection lepton pT thresholds must be positive and descending")
    for name in (
        "electron_max_abs_eta",
        "muon_max_abs_eta",
        "min_all_sfos_mass_gev",
    ):
        if _finite_number(selection[name], f"selection.{name}") <= 0:
            raise ValueError(f"selection.{name} must be positive")
    for name in ("z1_mass_window_gev", "m4l_window_gev"):
        low, high = _number_list(selection[name], f"selection.{name}", length=2)
        if not low < high:
            raise ValueError(f"selection.{name} must be ordered")
    z2 = _mapping(selection, "z2_mass")
    _require_exact_keys(z2, {"min_mode", "fixed_min_gev", "max_gev", "sliding"}, "selection.z2_mass")
    if z2["min_mode"] != "fixed":
        raise ValueError("selection.z2_mass.min_mode must be fixed")
    if not 0 < _finite_number(z2["fixed_min_gev"], "selection.z2_mass.fixed_min_gev") < _finite_number(
        z2["max_gev"], "selection.z2_mass.max_gev"
    ):
        raise ValueError("selection z2 mass limits must be positive and ordered")
    sliding = _mapping(z2, "sliding")
    _require_exact_keys(
        sliding,
        {"low_m4l_gev", "high_m4l_gev", "low_min_gev", "high_min_gev"},
        "selection.z2_mass.sliding",
    )
    sliding_values = {
        name: _finite_number(value, f"selection.z2_mass.sliding.{name}")
        for name, value in sliding.items()
    }
    if not sliding_values["low_m4l_gev"] < sliding_values["high_m4l_gev"]:
        raise ValueError("selection sliding m4l limits must be ordered")
    if not sliding_values["low_min_gev"] <= sliding_values["high_min_gev"]:
        raise ValueError("selection sliding z2 limits must be ordered")
    quality = _mapping(selection, "lepton_quality")
    quality_keys = {
        "enabled",
        "require_event_trigger",
        "require_trigger_match",
        "require_tight_id",
        "track_isolation_max",
        "calo_isolation_max",
        "electron_d0sig_max",
        "muon_d0sig_max",
        "z0_sintheta_max_mm",
    }
    _require_exact_keys(quality, quality_keys, "selection.lepton_quality")
    for name in ("enabled", "require_event_trigger", "require_trigger_match", "require_tight_id"):
        _boolean(quality[name], f"selection.lepton_quality.{name}")
    for name in quality_keys - {"enabled", "require_event_trigger", "require_trigger_match", "require_tight_id"}:
        if _finite_number(quality[name], f"selection.lepton_quality.{name}") <= 0:
            raise ValueError(f"selection.lepton_quality.{name} must be positive")


def _validate_preprocessing_sections(raw: Mapping[str, Any]) -> None:
    samples = _mapping(raw, "samples")
    _require_exact_keys(samples, {"higgs", "zz"}, "samples")
    expected_samples = {
        "higgs": ({"channel_numbers", "label", "input_profile", "tree_name", "momentum_unit"}, [345060], 1, "release22", "analysis", "GeV"),
        "zz": ({"channel_numbers", "label", "input_profile", "tree_name", "momentum_unit", "normalization"}, [363490], 0, "open_data_2020", "mini", "MeV"),
    }
    for name, (keys, channels, label, profile, tree, unit) in expected_samples.items():
        sample = _mapping(samples, name)
        _require_exact_keys(sample, keys, f"samples.{name}")
        if sample["channel_numbers"] != channels:
            raise ValueError(f"samples.{name}.channel_numbers must equal {channels}")
        if sample["label"] != label or isinstance(sample["label"], bool):
            raise ValueError(f"samples.{name}.label must equal {label}")
        if (sample["input_profile"], sample["tree_name"], sample["momentum_unit"]) != (
            profile,
            tree,
            unit,
        ):
            raise ValueError(f"samples.{name} input profile contract is invalid")
    normalization = _mapping(_mapping(samples, "zz"), "normalization")
    _require_exact_keys(
        normalization,
        {"source", "xsec_pb", "k_factor", "filter_efficiency", "sum_of_weights"},
        "samples.zz.normalization",
    )
    if normalization["source"] != "official_metadata":
        raise ValueError("samples.zz.normalization.source must be official_metadata")
    for name in ("xsec_pb", "k_factor", "filter_efficiency", "sum_of_weights"):
        if _finite_number(normalization[name], f"samples.zz.normalization.{name}") <= 0:
            raise ValueError(f"samples.zz.normalization.{name} must be positive")

    _validate_selection(_mapping(raw, "selection"))
    weighting = _mapping(raw, "weighting")
    _require_exact_keys(weighting, {"physical_weight", "training_weight"}, "weighting")
    if weighting != {
        "physical_weight": "signed_mc_normalization",
        "training_weight": "per_class_normalized_absolute_physical_weight",
    }:
        raise ValueError("weighting contract is invalid")
    identity = _mapping(raw, "identity")
    _require_exact_keys(identity, {"fields", "integer_only"}, "identity")
    if identity != {"fields": ["channelNumber", "eventNumber"], "integer_only": True}:
        raise ValueError("canonical identity contract is invalid")

    features = _mapping(raw, "features")
    _require_exact_keys(features, {"base14", "angular5", "model"}, "features")
    if tuple(_string_list(features["base14"], "features.base14")) != tuple(FEATURES):
        raise ValueError("features.base14 must equal frozen Base14")
    if tuple(_string_list(features["angular5"], "features.angular5")) != tuple(ANGULAR5_FEATURES):
        raise ValueError("features.angular5 must equal frozen Angular5")
    if tuple(_string_list(features["model"], "features.model")) != ANGULAR19:
        raise ValueError("features.model must equal frozen Angular19")
    forbidden = _string_list(raw.get("forbidden_features"), "forbidden_features")
    if tuple(forbidden) != _FORBIDDEN_FEATURES:
        raise ValueError("forbidden_features must equal the frozen new-schema contract")

    splitting = _mapping(raw, "splitting")
    split_keys = {
        "algorithm",
        "payload",
        "digest_size_bytes",
        "modulo",
        "train_buckets",
        "validation_buckets",
        "test_buckets",
        "train_fraction",
        "validation_fraction",
        "test_fraction",
    }
    _require_exact_keys(splitting, split_keys, "splitting")
    expected_split = {
        "algorithm": "blake2b_64_big_endian_modulo",
        "payload": "{channelNumber}:{eventNumber}",
        "digest_size_bytes": 8,
        "modulo": 10,
        "train_buckets": [0, 1, 2, 3, 4, 5],
        "validation_buckets": [6, 7],
        "test_buckets": [8, 9],
    }
    for name, value in expected_split.items():
        if splitting[name] != value:
            raise ValueError(f"splitting.{name} does not match the stable split contract")
    fractions = [
        _finite_number(splitting[name], f"splitting.{name}")
        for name in ("train_fraction", "validation_fraction", "test_fraction")
    ]
    if any(value < 0 or value > 1 for value in fractions) or not isfinite(sum(fractions)):
        raise ValueError("splitting fractions must be between 0 and 1")
    if abs(sum(fractions) - 1.0) > 1e-12:
        raise ValueError("splitting fractions must sum to 1")
    if fractions != [0.6, 0.2, 0.2]:
        raise ValueError("splitting fractions must match the stable bucket assignment")

    inputs = _mapping(raw, "inputs")
    _require_exact_keys(
        inputs,
        {"require_regular_file", "reject_symlinks", "sha256_required", "allowed_suffixes"},
        "inputs",
    )
    if inputs != {
        "require_regular_file": True,
        "reject_symlinks": True,
        "sha256_required": True,
        "allowed_suffixes": [".root"],
    }:
        raise ValueError("inputs contract is invalid")


def load_preprocessing_protocol(path: str | Path) -> PreprocessingProtocol:
    source, raw = _load_mapping(path)
    allowed = {
        "schema_version", "role", "samples", "selection", "weighting", "identity",
        "features", "forbidden_features", "splitting", "inputs",
    }
    _require_exact_keys(raw, allowed, "preprocessing protocol")
    _require_schema(raw)
    if raw.get("role") != "mc_preprocessing":
        raise ValueError("preprocessing protocol role must be mc_preprocessing")
    _validate_preprocessing_sections(raw)
    return PreprocessingProtocol(source, ANGULAR19, raw)


def load_preprocessing_run_config(path: str | Path) -> PreprocessingRunConfig:
    source, raw = _load_mapping(path)
    allowed = {"schema_version", "higgs_root", "zz_root", "chunk_size_events"}
    _reject_unknown(raw, allowed, "preprocessing run config")
    _require_schema(raw)
    if "chunk_size_events" in raw:
        chunk_float = _finite_number(raw["chunk_size_events"], "chunk_size_events")
        if not chunk_float.is_integer() or chunk_float <= 0:
            raise ValueError("chunk_size_events must be a positive integer")
    else:
        raise ValueError("chunk_size_events is required")
    for name in ("higgs_root", "zz_root"):
        if not isinstance(raw.get(name), str) or not raw[name]:
            raise ValueError(f"{name} must be a non-empty path string")
    return PreprocessingRunConfig(
        source,
        Path(raw["higgs_root"]),
        Path(raw["zz_root"]),
        int(chunk_float),
    )


def load_xgboost_protocol(path: str | Path) -> XGBoostProtocol:
    source, raw = _load_mapping(path)
    allowed = {
        "schema_version", "role", "features", "candidate", "common",
        "working_points", "qualification",
    }
    _require_exact_keys(raw, allowed, "XGBoost protocol")
    _require_schema(raw)
    if raw.get("role") != "xgboost_development":
        raise ValueError("XGBoost protocol role must be xgboost_development")
    features = raw.get("features")
    if not isinstance(features, list) or tuple(features) != ANGULAR19:
        raise ValueError("XGBoost protocol features must equal frozen Angular19")
    candidate = _mapping(raw, "candidate")
    common = _mapping(raw, "common")
    working_points = _mapping(raw, "working_points")
    qualification = _mapping(raw, "qualification")
    candidate_keys = {
        "learning_rate", "max_depth", "min_child_weight", "subsample",
        "colsample_bytree", "reg_alpha", "reg_lambda",
    }
    _require_exact_keys(candidate, candidate_keys, "candidate")
    _integer(candidate["max_depth"], "candidate.max_depth", minimum=1)
    for name in candidate_keys - {"max_depth"}:
        value = _finite_number(candidate[name], f"candidate.{name}")
        if name in {"learning_rate", "subsample", "colsample_bytree"} and not 0 < value <= 1:
            raise ValueError(f"candidate.{name} must be between 0 and 1")
        if name in {"min_child_weight", "reg_alpha", "reg_lambda"} and value < 0:
            raise ValueError(f"candidate.{name} must be non-negative")
    common_keys = {
        "n_estimators", "early_stopping_rounds", "random_seed", "n_jobs",
        "tree_method", "folds",
    }
    _require_exact_keys(common, common_keys, "common")
    for name in common_keys - {"tree_method"}:
        _integer(common[name], f"common.{name}", minimum=1 if name != "random_seed" else 0)
    _string(common["tree_method"], "common.tree_method")
    if common["folds"] < 2:
        raise ValueError("common.folds must be at least 2")
    _require_exact_keys(working_points, {"loose", "medium", "tight"}, "working_points")
    points = {
        name: _finite_number(value, f"working_points.{name}")
        for name, value in working_points.items()
    }
    if any(value <= 0 or value > 1 for value in points.values()):
        raise ValueError("working points must be between 0 and 1")
    if not points["loose"] > points["medium"] > points["tight"]:
        raise ValueError("working points must be ordered loose > medium > tight")
    qualification_keys = {
        "minimum_weighted_oof_auc",
        "maximum_background_ks",
        "require_signal_efficiency_above_background",
    }
    _require_exact_keys(qualification, qualification_keys, "qualification")
    for name in ("minimum_weighted_oof_auc", "maximum_background_ks"):
        value = _finite_number(qualification[name], f"qualification.{name}")
        if value < 0 or value > 1:
            raise ValueError(f"qualification.{name} must be between 0 and 1")
    _boolean(
        qualification["require_signal_efficiency_above_background"],
        "qualification.require_signal_efficiency_above_background",
    )
    return XGBoostProtocol(
        source,
        tuple(features),
        candidate,
        common,
        working_points,
        qualification,
        raw,
    )
