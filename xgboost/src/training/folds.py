"""Frozen development-fold and XGBoost sample-weight rules."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from .dataset import validate_development_frame


def development_fold(channel_number: int, event_number: int, folds: int = 5) -> int:
    if isinstance(folds, bool) or not isinstance(folds, (int, np.integer)) or folds <= 0:
        raise ValueError("folds must be a positive integer")
    payload = f"task4b-fold:{int(channel_number)}:{int(event_number)}".encode()
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big") % int(folds)


def assign_development_folds(frame: pd.DataFrame, folds: int = 5) -> pd.Series:
    validate_development_frame(frame)
    assigned = pd.Series(
        [
            development_fold(channel, event, folds)
            for channel, event in zip(
                frame["channelNumber"], frame["eventNumber"], strict=True
            )
        ],
        index=frame.index,
        dtype=int,
        name="development_fold",
    )
    for fold in range(folds):
        if set(frame.loc[assigned == fold, "label"]) != {0, 1}:
            raise ValueError(f"development fold {fold} must contain labels 0 and 1")
    return assigned


def class_balanced_training_weights(frame: pd.DataFrame) -> np.ndarray:
    labels = frame["label"].to_numpy(dtype=int)
    physical = frame["physical_weight"].to_numpy(dtype=float)
    if set(labels) != {0, 1}:
        raise ValueError("fitting subset must contain labels 0 and 1")
    if not np.isfinite(physical).all():
        raise ValueError("physical_weight must be finite")
    output = np.empty(len(frame), dtype=float)
    target = len(frame) / 2.0
    absolute = np.abs(physical)
    for label in (0, 1):
        mask = labels == label
        total = float(absolute[mask].sum())
        if total <= 0.0:
            raise ValueError("each class must have positive absolute physical-weight sum")
        output[mask] = absolute[mask] * target / total
    class_totals = [float(output[labels == label].sum()) for label in (0, 1)]
    if not all(np.isclose(total, target, rtol=1e-12, atol=1e-12) for total in class_totals):
        raise ValueError("class-balanced training weights have incorrect class totals")
    if not np.isclose(float(output.mean()), 1.0, rtol=1e-12, atol=1e-12):
        raise ValueError("class-balanced training weights must have mean 1")
    return output
