from __future__ import annotations

import hashlib

import numpy as np

from src.config import InputBindingError
from src.training.dataset import ValidatedDevelopment


def fold_index_for_identity(event_group_id: str) -> int:
    if not isinstance(event_group_id, str) or not event_group_id or "\x00" in event_group_id:
        raise InputBindingError("physical event group is invalid")
    digest = hashlib.sha256(event_group_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % 5


def assign_folds(development: ValidatedDevelopment) -> np.ndarray:
    frame = development.frame
    if "split" not in frame or any(value not in {"train", "validation"} for value in frame["split"]):
        raise InputBindingError("fold assignment received non-development split")
    identities = tuple(
        zip(frame["source_sample"].tolist(), frame["source_entry"].tolist(), strict=True)
    )
    normalized = tuple((sample, int(entry)) for sample, entry in identities)
    if len(set(normalized)) != len(normalized):
        raise InputBindingError("canonical identity is not unique for fold assignment")
    folds = np.asarray(
        [fold_index_for_identity(group) for group in frame["event_group_id"]],
        dtype=np.int64,
    )
    if folds.shape != (len(frame),) or np.any(folds < 0) or np.any(folds >= 5):
        raise InputBindingError("fold assignment is incomplete")
    return folds
