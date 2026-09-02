from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import Tensor

from src.config import InputBindingError
from src.training.config import BASE_SEED, FEATURES, INPUT_COLUMNS
from src.training.losses import adversarial_bin_weights, mass_bin_indices


FEATURE_COLUMNS = FEATURES
_INTEGER_COLUMNS = ("label", "source_entry", "runNumber", "eventNumber", "channelNumber")
_TEXT_COLUMNS = {"split", "source_sample"}


@dataclass(frozen=True)
class FoldLocalScaler:
    mean: np.ndarray
    scale: np.ndarray
    fitting_rows: int

    @classmethod
    def fit(cls, matrix: np.ndarray) -> "FoldLocalScaler":
        values = np.asarray(matrix, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] != 15 or values.shape[0] == 0 or not np.isfinite(values).all():
            raise InputBindingError("scaler fitting matrix must be finite shape (N, 15)")
        mean = values.mean(axis=0, dtype=np.float64)
        variance = ((values - mean) ** 2).mean(axis=0, dtype=np.float64)
        scale = np.sqrt(variance)
        scale[scale == 0.0] = 1.0
        if not np.isfinite(mean).all() or not np.isfinite(scale).all():
            raise InputBindingError("scaler statistics must be finite")
        return cls(mean, scale, int(values.shape[0]))

    def transform(self, matrix: np.ndarray) -> np.ndarray:
        values = np.asarray(matrix, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] != 15:
            raise InputBindingError("scaled features must be finite shape (N, 15)")
        transformed = (values - self.mean) / self.scale
        if not np.isfinite(transformed).all():
            raise InputBindingError("scaled features must be finite shape (N, 15)")
        return transformed.astype(np.float32)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": "fold-local-scaler-v1", "features": list(FEATURE_COLUMNS), "mean": self.mean.tolist(), "scale": self.scale.tolist(), "fitting_rows": self.fitting_rows}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "FoldLocalScaler":
        if set(raw) != {"schema_version", "features", "mean", "scale", "fitting_rows"} or raw.get("schema_version") != "fold-local-scaler-v1" or tuple(raw.get("features", ())) != FEATURE_COLUMNS:
            raise InputBindingError("scaler schema changed")
        mean = np.asarray(raw["mean"], dtype=np.float64)
        scale = np.asarray(raw["scale"], dtype=np.float64)
        if mean.shape != (15,) or scale.shape != (15,) or not np.isfinite(mean).all() or not np.isfinite(scale).all() or np.any(scale <= 0):
            raise InputBindingError("scaler statistics changed")
        rows = raw["fitting_rows"]
        if type(rows) is not int or rows <= 0:
            raise InputBindingError("scaler fitting_rows must be positive")
        return cls(mean, scale, rows)


@dataclass(frozen=True)
class ValidatedDevelopment:
    frame: pd.DataFrame
    protocol_sha256: str


@dataclass(frozen=True)
class ValidatedFold:
    fitting_features: Tensor
    validation_features: Tensor
    labels: Tensor
    validation_labels: Tensor
    train_weights: Tensor
    validation_weights: Tensor
    mass_bins: Tensor
    adversarial_weights: Tensor
    fitting_identities: tuple[tuple[str, int], ...]
    validation_identities: tuple[tuple[str, int], ...]
    scaler: FoldLocalScaler
    fold_index: int
    fold_seed: int
    protocol_sha256: str

    def __post_init__(self) -> None:
        for name, values in (("fitting", self.fitting_features), ("validation", self.validation_features)):
            if values.ndim != 2 or values.shape[1] != 15 or values.dtype != torch.float32 or values.device.type != "cpu" or not torch.isfinite(values).all():
                raise InputBindingError(f"{name} feature tensor changed")
        if (
            self.fitting_features.shape[0] != self.labels.shape[0]
            or self.validation_features.shape[0] != self.validation_labels.shape[0]
            or self.labels.ndim != 1
            or self.validation_labels.ndim != 1
            or self.labels.dtype != torch.int64
            or self.validation_labels.dtype != torch.int64
            or self.labels.device.type != "cpu"
            or self.validation_labels.device.type != "cpu"
        ):
            raise InputBindingError("fold label dtype changed")
        if self.labels.shape != self.train_weights.shape or self.validation_labels.shape != self.validation_weights.shape:
            raise InputBindingError("fold label/weight shape mismatch")
        if set(self.labels.tolist()) != {0, 1} or set(self.validation_labels.tolist()) != {0, 1}:
            raise InputBindingError("fold labels must contain both classes")
        if self.adversarial_weights.shape != self.labels.shape:
            raise InputBindingError("fold adversarial-weight shape changed")
        for weights in (self.train_weights, self.validation_weights, self.adversarial_weights):
            if weights.dtype != torch.float32 or weights.device.type != "cpu" or not torch.isfinite(weights).all() or torch.any(weights < 0):
                raise InputBindingError("fold weights changed")
        if (
            self.train_weights.sum().item() <= 0
            or self.validation_weights.sum().item() <= 0
            or self.mass_bins.dtype != torch.int64
            or self.mass_bins.device.type != "cpu"
            or self.mass_bins.shape != self.labels.shape
        ):
            raise InputBindingError("fold validation or mass-bin contract changed")
        signal = self.labels == 1
        if torch.any(self.mass_bins[signal] != -1) or torch.any(self.adversarial_weights[signal] != 0):
            raise InputBindingError("signal rows entered adversarial contract")
        if torch.any((self.mass_bins[~signal] < 0) | (self.mass_bins[~signal] > 10)):
            raise InputBindingError("background mass bins changed")
        if (
            len(self.fitting_identities) != len(self.labels)
            or len(self.validation_identities) != len(self.validation_labels)
            or len(set(self.fitting_identities)) != len(self.fitting_identities)
            or len(set(self.validation_identities)) != len(self.validation_identities)
            or set(self.fitting_identities) & set(self.validation_identities)
        ):
            raise InputBindingError("fold identity contract changed")
        if self.scaler.fitting_rows != len(self.labels):
            raise InputBindingError("fold scaler binding changed")
        if (
            type(self.fold_index) is not int
            or self.fold_index not in range(5)
            or type(self.fold_seed) is not int
            or self.fold_seed != BASE_SEED + self.fold_index
            or type(self.protocol_sha256) is not str
            or len(self.protocol_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.protocol_sha256)
        ):
            raise InputBindingError("fold binding changed")


def validate_development_frame(frame: pd.DataFrame, *, protocol_sha256: str) -> ValidatedDevelopment:
    if tuple(frame.columns) != INPUT_COLUMNS:
        raise InputBindingError("development frame columns changed")
    splits = frame["split"].to_numpy(copy=False)
    if len(splits) == 0:
        raise InputBindingError("development frame is empty")
    if any(value not in {"train", "validation"} for value in splits):
        raise InputBindingError("development frame contains forbidden split")
    if frame["source_sample"].isna().any() or (frame["source_sample"].astype(str).str.len() == 0).any():
        raise InputBindingError("source_sample must be non-empty")
    identities = list(zip(frame["source_sample"].astype(str), frame["source_entry"], strict=True))
    if len(set(identities)) != len(identities):
        raise InputBindingError("canonical identity must be unique")
    for column in _INTEGER_COLUMNS:
        if not pd.api.types.is_integer_dtype(frame[column].dtype):
            raise InputBindingError(f"integer column changed: {column}")
    if set(frame["label"].unique()) - {0, 1}:
        raise InputBindingError("label must be 0 or 1")
    for column in INPUT_COLUMNS:
        if column in _TEXT_COLUMNS:
            continue
        if not pd.api.types.is_numeric_dtype(frame[column].dtype) or not np.isfinite(frame[column].to_numpy(dtype=np.float64)).all():
            raise InputBindingError(f"numeric column must be finite: {column}")
    if (frame["train_weight"] < 0).any():
        raise InputBindingError("train_weight must be non-negative")
    if ((frame["m4l"] < 105.0) | (frame["m4l"] > 160.0)).any():
        raise InputBindingError("m4l outside sealed range")
    if (
        type(protocol_sha256) is not str
        or len(protocol_sha256) != 64
        or any(character not in "0123456789abcdef" for character in protocol_sha256)
    ):
        raise InputBindingError("protocol SHA-256 is invalid")
    return ValidatedDevelopment(frame.copy(deep=True), protocol_sha256)


def _indices(values: np.ndarray, *, rows: int, name: str) -> np.ndarray:
    result = np.asarray(values)
    if result.ndim != 1 or result.size == 0 or not np.issubdtype(result.dtype, np.integer):
        raise InputBindingError(f"{name} indices must be non-empty integer vector")
    result = result.astype(np.int64)
    if np.any(result < 0) or np.any(result >= rows) or len(np.unique(result)) != len(result):
        raise InputBindingError(f"{name} indices are invalid")
    return result


def build_validated_fold(
    development: ValidatedDevelopment,
    fitting_indices: np.ndarray,
    validation_indices: np.ndarray,
    *,
    fold_index: int,
) -> ValidatedFold:
    if fold_index not in range(5):
        raise InputBindingError("fold index changed")
    frame = development.frame
    fitting = _indices(fitting_indices, rows=len(frame), name="fitting")
    validation = _indices(validation_indices, rows=len(frame), name="validation")
    if np.intersect1d(fitting, validation).size:
        raise InputBindingError("fitting and validation identity overlap")
    fit_identities = tuple(zip(frame.iloc[fitting]["source_sample"].astype(str), frame.iloc[fitting]["source_entry"].astype(int), strict=True))
    val_identities = tuple(zip(frame.iloc[validation]["source_sample"].astype(str), frame.iloc[validation]["source_entry"].astype(int), strict=True))
    if set(fit_identities) & set(val_identities):
        raise InputBindingError("fitting and validation identity overlap")
    scaler = FoldLocalScaler.fit(frame.iloc[fitting][list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64))
    fitting_features = torch.from_numpy(scaler.transform(frame.iloc[fitting][list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64)))
    validation_features = torch.from_numpy(scaler.transform(frame.iloc[validation][list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64)))
    labels = torch.tensor(frame.iloc[fitting]["label"].to_numpy(), dtype=torch.int64)
    validation_labels = torch.tensor(frame.iloc[validation]["label"].to_numpy(), dtype=torch.int64)
    train_weights = torch.tensor(frame.iloc[fitting]["train_weight"].to_numpy(), dtype=torch.float32)
    validation_weights = torch.tensor(frame.iloc[validation]["train_weight"].to_numpy(), dtype=torch.float32)
    if set(validation_labels.tolist()) != {0, 1} or not torch.isfinite(validation_weights).all() or torch.any(validation_weights < 0) or validation_weights.sum().item() <= 0:
        raise InputBindingError("validation weighted AUC preconditions failed")
    background = labels == 0
    masses = torch.tensor(frame.iloc[fitting]["m4l"].to_numpy(), dtype=torch.float64)[background]
    physical = torch.tensor(frame.iloc[fitting]["physical_weight"].to_numpy(), dtype=torch.float32)[background]
    bins = mass_bin_indices(masses)
    adversarial_weights = adversarial_bin_weights(bins, physical)
    all_bins = torch.full_like(labels, -1)
    all_adv = torch.zeros_like(train_weights)
    all_bins[background] = bins
    all_adv[background] = adversarial_weights
    return ValidatedFold(
        fitting_features, validation_features, labels, validation_labels, train_weights,
        validation_weights, all_bins, all_adv, fit_identities, val_identities, scaler,
        fold_index, BASE_SEED + fold_index, development.protocol_sha256,
    )
