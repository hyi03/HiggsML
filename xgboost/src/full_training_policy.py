from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import numpy as np
import pandas as pd
import yaml

from .features import FEATURES, assert_no_feature_leakage


_REQUIRED_COLUMNS = frozenset(
    [*FEATURES, "m4l", "eventNumber", "channelNumber", "split", "label", "physical_weight"]
)
_APPROVED_DEPTHS = (2, 3, 4)
_APPROVED_CHILD_WEIGHTS = (5, 20)
_APPROVED_PAIRS = frozenset(
    (depth, child) for depth in _APPROVED_DEPTHS for child in _APPROVED_CHILD_WEIGHTS
)
_REQUIRED_COMMON_PARAMETERS = frozenset(
    {
        "n_estimators",
        "learning_rate",
        "subsample",
        "colsample_bytree",
        "reg_alpha",
        "reg_lambda",
        "objective",
        "eval_metric",
        "early_stopping_rounds",
        "tree_method",
    }
)
_COMMON_PARAMETERS = {
    "n_estimators": 1000,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 2.0,
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "early_stopping_rounds": 50,
    "tree_method": "hist",
}
_WORKING_POINTS = {"loose": 0.50, "medium": 0.20, "tight": 0.10}
_WARNINGS = {"auc_gap_limit": 0.05, "ks_distance_limit": 0.10}
_MASS_BINS_GEV = (105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160)


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    max_depth: int
    min_child_weight: float


@dataclass(frozen=True)
class TrainingPolicy:
    folds: int
    random_seed: int
    n_jobs: int
    common_parameters: Mapping[str, object]
    candidates: tuple[CandidateSpec, ...]
    working_points: Mapping[str, float]
    auc_gap_limit: float
    ks_distance_limit: float
    mass_bins_gev: tuple[float, ...]


def class_balanced_training_weights(
    frame: pd.DataFrame, *, multipliers: pd.Series | None = None
) -> np.ndarray:
    labels = frame["label"].to_numpy(dtype=int)
    physical = frame["physical_weight"].to_numpy(dtype=float)
    validated_multipliers = _validated_training_weight_multipliers(frame, multipliers)
    if set(labels) != {0, 1}:
        raise ValueError("fitting subset must contain labels 0 and 1")
    if not np.isfinite(physical).all():
        raise ValueError("physical_weight must be finite")

    output = np.empty(len(frame), dtype=float)
    target = len(frame) / 2.0
    adjusted = np.abs(physical)
    if validated_multipliers is not None:
        adjusted = adjusted * validated_multipliers.to_numpy(dtype=float)
    for label in (0, 1):
        mask = labels == label
        total = float(adjusted[mask].sum())
        if total <= 0:
            raise ValueError("each class must have positive absolute physical-weight sum")
        output[mask] = adjusted[mask] * target / total

    if not np.isfinite(output).all() or np.any(output < 0):
        raise ValueError("training weights must be finite and non-negative")
    class_totals = [float(output[labels == label].sum()) for label in (0, 1)]
    if not all(np.isclose(total, target, rtol=1e-12, atol=1e-12) for total in class_totals):
        raise ValueError("class-balanced training weights have incorrect class totals")
    if not np.isclose(float(output.mean()), 1.0, rtol=1e-12, atol=1e-12):
        raise ValueError("class-balanced training weights must have mean 1")
    return output


def _validated_training_weight_multipliers(
    frame: pd.DataFrame, multipliers: pd.Series | None
) -> pd.Series | None:
    if multipliers is None:
        return None
    if not isinstance(multipliers, pd.Series):
        raise TypeError("training weight multipliers must be a pandas Series")
    if not multipliers.index.equals(frame.index):
        raise ValueError("training weight multiplier index must exactly equal frame index")
    try:
        values = multipliers.to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "training weight multipliers must be finite and strictly positive"
        ) from error
    if not np.isfinite(values).all():
        raise ValueError("training weight multipliers must be finite")
    if np.any(values <= 0):
        raise ValueError("training weight multipliers must be strictly positive")
    return multipliers


def validate_mc_frame(frame: pd.DataFrame) -> None:
    _validate_analysis_frame(
        frame,
        required_splits={"train", "validation", "test"},
        split_error="splits must be exactly {'train', 'validation', 'test'}",
    )


def validate_development_frame(frame: pd.DataFrame) -> None:
    """Validate only train/validation rows without consulting held-out test content."""
    _validate_analysis_frame(
        frame,
        required_splits={"train", "validation"},
        split_error="development splits must be exactly {'train', 'validation'}",
    )


def _validate_analysis_frame(
    frame: pd.DataFrame, *, required_splits: set[str], split_error: str
) -> None:
    missing = sorted(_REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    collisions = identity_collision_summary(frame)
    if collisions["cross_label_groups"]:
        raise ValueError("identifier collision groups must not span labels")
    if collisions["cross_split_groups"]:
        raise ValueError("identifier collision groups must not span splits")

    labels = set(frame["label"])
    if labels != {0, 1}:
        raise ValueError("labels must be exactly {0, 1}")
    splits = set(frame["split"])
    if not splits <= required_splits:
        raise ValueError("unknown split")
    if splits != required_splits:
        raise ValueError(split_error)
    for split in required_splits:
        if set(frame.loc[frame["split"] == split, "label"]) != {0, 1}:
            raise ValueError(f"{split} split must contain labels 0 and 1")

    numeric_columns = [*FEATURES, "m4l", "physical_weight"]
    try:
        numeric = frame[numeric_columns].to_numpy(dtype=float)
        identifiers = frame[["channelNumber", "eventNumber"]].to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("analysis values and identifiers must be numeric") from error
    if not np.isfinite(numeric).all():
        raise ValueError("feature, mass, and physical_weight values must be finite")
    if not np.isfinite(identifiers).all():
        raise ValueError("event identifiers must be finite")
    assert_no_feature_leakage()


def identity_collision_summary(frame: pd.DataFrame) -> dict[str, int]:
    groups = frame.groupby(
        ["channelNumber", "eventNumber"], dropna=False, sort=False
    )
    rows_per_pair = groups.size()
    duplicate_pairs = rows_per_pair > 1
    labels_per_pair = groups["label"].nunique(dropna=False)
    splits_per_pair = groups["split"].nunique(dropna=False)
    return {
        "unique_pairs": int(len(rows_per_pair)),
        "duplicate_pair_groups": int(duplicate_pairs.sum()),
        "rows_in_duplicate_pair_groups": int(rows_per_pair[duplicate_pairs].sum()),
        "cross_label_groups": int((labels_per_pair > 1).sum()),
        "cross_split_groups": int((splits_per_pair > 1).sum()),
    }


def development_fold(channel_number: int, event_number: int, folds: int = 5) -> int:
    if folds <= 0:
        raise ValueError("folds must be positive")
    payload = f"task4b-fold:{int(channel_number)}:{int(event_number)}".encode()
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big") % folds


def assign_development_folds(frame: pd.DataFrame, folds: int = 5) -> pd.Series:
    if folds <= 0:
        raise ValueError("folds must be positive")
    if set(frame["split"]) == {"train", "validation"}:
        validate_development_frame(frame)
        development = frame
    else:
        validate_mc_frame(frame)
        development = frame.loc[frame["split"] != "test"]
    assigned = pd.Series(
        [
            development_fold(channel, event, folds)
            for channel, event in zip(
                development["channelNumber"], development["eventNumber"], strict=True
            )
        ],
        index=development.index,
        dtype=int,
        name="development_fold",
    )
    for fold in range(folds):
        labels = set(development.loc[assigned == fold, "label"])
        if labels != {0, 1}:
            raise ValueError(f"development fold {fold} must contain labels 0 and 1")
    return assigned


def candidate_specs(policy: TrainingPolicy) -> tuple[CandidateSpec, ...]:
    return policy.candidates


def load_training_policy(path: str | Path) -> TrainingPolicy:
    with Path(path).open() as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError("training policy must be a mapping")
    if raw.get("schema_version") != "1.0":
        raise ValueError("unknown schema_version")
    if raw.get("folds") != 5:
        raise ValueError("folds must be exactly 5")
    n_jobs = raw.get("n_jobs")
    if not isinstance(n_jobs, int) or n_jobs <= 0:
        raise ValueError("n_jobs must be positive")
    if n_jobs != 4:
        raise ValueError("n_jobs must be exactly 4")
    if raw.get("random_seed") != 42:
        raise ValueError("random_seed must be exactly 42")

    common = raw.get("common_parameters")
    if not isinstance(common, dict) or not _REQUIRED_COMMON_PARAMETERS <= set(common):
        raise ValueError("missing common parameters")
    if not _values_are_finite(common):
        raise ValueError("common parameters must be finite")
    if common != _COMMON_PARAMETERS:
        raise ValueError("common_parameters must retain the frozen values")

    candidates_raw = raw.get("candidates")
    if not isinstance(candidates_raw, dict):
        raise ValueError("candidates must be a mapping")
    depths = candidates_raw.get("max_depth")
    child_weights = candidates_raw.get("min_child_weight")
    if depths != list(_APPROVED_DEPTHS) or child_weights != list(_APPROVED_CHILD_WEIGHTS):
        raise ValueError("candidate product must be the exact six approved pairs")
    pairs = {(int(depth), float(child)) for depth in depths for child in child_weights}
    normalized_pairs = {(depth, int(child)) for depth, child in pairs}
    if normalized_pairs != _APPROVED_PAIRS or len(pairs) != 6:
        raise ValueError("candidate product must be the exact six approved pairs")
    candidates = tuple(
        CandidateSpec(f"depth{depth}_child{child}", depth, float(child))
        for depth in _APPROVED_DEPTHS
        for child in sorted(_APPROVED_CHILD_WEIGHTS, reverse=True)
    )

    working_points = raw.get("working_points")
    if working_points != _WORKING_POINTS:
        raise ValueError("working_points must retain the frozen names and efficiencies")
    warnings = raw.get("warnings")
    if not isinstance(warnings, dict) or warnings != _WARNINGS:
        raise ValueError("warnings must be a mapping")
    auc_gap_limit = warnings.get("auc_gap_limit")
    ks_distance_limit = warnings.get("ks_distance_limit")
    mass_bins = raw.get("mass_bins_gev")
    if not _values_are_finite([auc_gap_limit, ks_distance_limit, *(mass_bins or [])]):
        raise ValueError("policy numeric values must be finite")
    if (
        not isinstance(mass_bins, list)
        or len(mass_bins) < 2
        or mass_bins != sorted(mass_bins)
        or tuple(mass_bins) != _MASS_BINS_GEV
    ):
        raise ValueError("mass_bins_gev must be sorted")

    return TrainingPolicy(
        folds=5,
        random_seed=int(raw.get("random_seed")),
        n_jobs=n_jobs,
        common_parameters=MappingProxyType(dict(common)),
        candidates=candidates,
        working_points=MappingProxyType(dict(working_points)),
        auc_gap_limit=float(auc_gap_limit),
        ks_distance_limit=float(ks_distance_limit),
        mass_bins_gev=tuple(float(value) for value in mass_bins),
    )


def _values_are_finite(values: object) -> bool:
    if isinstance(values, Mapping):
        return all(_values_are_finite(value) for value in values.values())
    if isinstance(values, (list, tuple)):
        return all(_values_are_finite(value) for value in values)
    if isinstance(values, (int, float, np.number)) and not isinstance(values, bool):
        return bool(np.isfinite(values))
    return True
