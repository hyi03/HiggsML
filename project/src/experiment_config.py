from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import math
import yaml

from .angular5 import ANGULAR5_FEATURES
from .features import FEATURES, FORBIDDEN_FEATURES


BASE14_PROFILE = tuple(FEATURES)
ANGULAR19_PROFILE = (*BASE14_PROFILE, *tuple(ANGULAR5_FEATURES))
FEATURE_PROFILES = {
    "base14": BASE14_PROFILE,
    "angular19": ANGULAR19_PROFILE,
}

GRID_PARAMETERS = (
    "learning_rate",
    "max_depth",
    "min_child_weight",
    "subsample",
    "colsample_bytree",
    "reg_alpha",
    "reg_lambda",
)
SCALAR_PARAMETERS = (
    "n_estimators",
    "early_stopping_rounds",
    "random_seed",
    "n_jobs",
    "tree_method",
    "folds",
)

_DEFAULT_GRID: dict[str, tuple[object, ...]] = {
    "learning_rate": (0.05,),
    "max_depth": (3,),
    "min_child_weight": (5.0,),
    "subsample": (0.8,),
    "colsample_bytree": (0.8,),
    "reg_alpha": (0.1,),
    "reg_lambda": (2.0,),
}
_DEFAULT_SCALARS: dict[str, object] = {
    "n_estimators": 1000,
    "early_stopping_rounds": 50,
    "random_seed": 42,
    "n_jobs": 1,
    "tree_method": "hist",
    "folds": 5,
}
_DEFAULT_WORKING_POINTS = {"loose": 0.50, "medium": 0.20, "tight": 0.10}
_TOP_LEVEL_KEYS = {
    "schema_version",
    "feature_profile",
    "features",
    "training",
    "working_points",
}


@dataclass(frozen=True)
class ExperimentOverrides:
    feature_profile: str | None = None
    feature_toggles: tuple[tuple[str, bool], ...] = ()
    grid: Mapping[str, tuple[object, ...]] = field(default_factory=dict)
    scalars: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentConfig:
    feature_profile: str
    features: tuple[str, ...]
    grid: Mapping[str, tuple[object, ...]]
    n_estimators: int
    early_stopping_rounds: int
    random_seed: int
    n_jobs: int
    tree_method: str
    folds: int
    working_points: Mapping[str, float]

    def candidates(self) -> tuple[dict[str, object], ...]:
        values = [self.grid[name] for name in GRID_PARAMETERS]
        return tuple(
            dict(zip(GRID_PARAMETERS, candidate, strict=True))
            for candidate in product(*values)
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "feature_profile": self.feature_profile,
            "features": list(self.features),
            "training": {
                "n_estimators": self.n_estimators,
                "early_stopping_rounds": self.early_stopping_rounds,
                "random_seed": self.random_seed,
                "n_jobs": self.n_jobs,
                "tree_method": self.tree_method,
                "folds": self.folds,
                **{name: list(self.grid[name]) for name in GRID_PARAMETERS},
            },
            "working_points": dict(self.working_points),
        }


def resolve_enabled_features(
    profile: str,
    toggles: Mapping[str, bool] | Iterable[tuple[str, bool]],
) -> tuple[str, ...]:
    try:
        registered = FEATURE_PROFILES[profile]
    except (KeyError, TypeError) as error:
        raise ValueError(f"unknown feature profile: {profile}") from error

    items = list(toggles.items()) if isinstance(toggles, Mapping) else list(toggles)
    resolved: dict[str, bool] = {name: True for name in registered}
    seen: dict[str, bool] = {}
    for name, enabled in items:
        if not isinstance(name, str) or name not in registered:
            if name in FORBIDDEN_FEATURES:
                raise ValueError(f"forbidden model feature: {name}")
            raise ValueError(f"unknown feature for profile {profile}: {name}")
        if not isinstance(enabled, bool):
            raise ValueError(f"feature toggle must be boolean: {name}")
        if name in seen and seen[name] != enabled:
            raise ValueError(f"conflicting feature toggles: {name}")
        seen[name] = enabled
        resolved[name] = enabled
    selected = tuple(name for name in registered if resolved[name])
    if not selected:
        raise ValueError("at least one model feature must be enabled")
    return selected


def load_experiment_config(
    path: str | Path | None = None,
    overrides: ExperimentOverrides | None = None,
) -> ExperimentConfig:
    raw: dict[str, object] = {}
    if path is not None:
        with Path(path).open(encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
        if not isinstance(loaded, dict):
            raise ValueError("experiment config must be a mapping")
        raw = loaded
    unknown = set(raw) - _TOP_LEVEL_KEYS
    if unknown:
        raise ValueError(f"unknown experiment config keys: {sorted(unknown)}")
    if raw.get("schema_version", "1.0") != "1.0":
        raise ValueError("unknown experiment config schema_version")

    override = overrides or ExperimentOverrides()
    profile = override.feature_profile or str(raw.get("feature_profile", "base14"))
    config_toggles = dict(_feature_toggles(raw.get("features", {})))
    cli_toggles = _unique_toggles(override.feature_toggles)
    config_toggles.update(cli_toggles)
    features = resolve_enabled_features(profile, config_toggles)

    training = raw.get("training", {})
    if not isinstance(training, Mapping):
        raise ValueError("training config must be a mapping")
    unknown_training = set(training) - set(GRID_PARAMETERS) - set(SCALAR_PARAMETERS)
    if unknown_training:
        raise ValueError(f"unknown training parameters: {sorted(unknown_training)}")

    grid: dict[str, tuple[object, ...]] = {}
    for name in GRID_PARAMETERS:
        value = override.grid.get(name, training.get(name, _DEFAULT_GRID[name]))
        grid[name] = _grid_values(name, value)

    scalars = {
        name: override.scalars.get(name, training.get(name, _DEFAULT_SCALARS[name]))
        for name in SCALAR_PARAMETERS
    }
    normalized = _validate_scalars(scalars)
    working_points = _working_points(raw.get("working_points", _DEFAULT_WORKING_POINTS))
    return ExperimentConfig(
        feature_profile=profile,
        features=features,
        grid=grid,
        n_estimators=normalized["n_estimators"],
        early_stopping_rounds=normalized["early_stopping_rounds"],
        random_seed=normalized["random_seed"],
        n_jobs=normalized["n_jobs"],
        tree_method=normalized["tree_method"],
        folds=normalized["folds"],
        working_points=working_points,
    )


def _feature_toggles(value: object) -> list[tuple[str, bool]]:
    if not isinstance(value, Mapping):
        raise ValueError("features config must be a mapping of name to on/off")
    return [(str(name), _boolean_toggle(enabled)) for name, enabled in value.items()]


def _unique_toggles(items: Iterable[tuple[str, bool]]) -> dict[str, bool]:
    output: dict[str, bool] = {}
    for name, enabled in items:
        if name in output and output[name] != enabled:
            raise ValueError(f"conflicting feature toggles: {name}")
        output[name] = enabled
    return output


def _boolean_toggle(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"on", "off"}:
        return value.lower() == "on"
    raise ValueError("feature values must be on/off or boolean")


def _grid_values(name: str, value: object) -> tuple[object, ...]:
    values: Sequence[object]
    if isinstance(value, (list, tuple)):
        values = value
    else:
        values = (value,)
    if not values:
        raise ValueError(f"training grid parameter must not be empty: {name}")
    normalized: list[object] = []
    for item in values:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"training grid parameter must be numeric: {name}")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"training grid parameter must be finite: {name}")
        if name == "max_depth":
            if not isinstance(item, int) or item <= 0:
                raise ValueError("max_depth must contain positive integers")
            normalized.append(int(item))
        else:
            normalized.append(number)
    if name in {"learning_rate", "min_child_weight"} and any(v <= 0 for v in normalized):
        raise ValueError(f"{name} must be positive")
    if name in {"subsample", "colsample_bytree"} and any(
        v <= 0 or v > 1 for v in normalized
    ):
        raise ValueError(f"{name} must be in (0, 1]")
    if name in {"reg_alpha", "reg_lambda"} and any(v < 0 for v in normalized):
        raise ValueError(f"{name} must be non-negative")
    return tuple(normalized)


def _validate_scalars(values: Mapping[str, object]) -> dict[str, object]:
    output: dict[str, object] = {}
    for name in ("n_estimators", "early_stopping_rounds", "n_jobs", "folds"):
        value = values[name]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        output[name] = int(value)
    if output["folds"] < 2:
        raise ValueError("folds must be at least 2")
    seed = values["random_seed"]
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("random_seed must be a non-negative integer")
    output["random_seed"] = int(seed)
    tree_method = values["tree_method"]
    if not isinstance(tree_method, str) or not tree_method:
        raise ValueError("tree_method must be a non-empty string")
    output["tree_method"] = tree_method
    return output


def _working_points(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("working_points must be a non-empty mapping")
    points: dict[str, float] = {}
    for name, target in value.items():
        if not isinstance(name, str) or not name:
            raise ValueError("working-point names must be non-empty strings")
        if isinstance(target, bool) or not isinstance(target, (int, float)):
            raise ValueError("working-point targets must be numeric")
        number = float(target)
        if not math.isfinite(number) or number <= 0 or number > 1:
            raise ValueError("working-point targets must be in (0, 1]")
        points[name] = number
    ordered = list(points.values())
    if ordered != sorted(ordered, reverse=True):
        raise ValueError("working-point targets must be ordered from loose to tight")
    return points
