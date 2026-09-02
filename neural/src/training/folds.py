from __future__ import annotations

import hashlib

import numpy as np

from src.config import InputBindingError
from src.training.dataset import ValidatedDevelopment


def fold_index_for_identity(source_sample: str, source_entry: int) -> int:
    if (
        type(source_sample) is not str
        or not source_sample
        or "\x00" in source_sample
        or type(source_entry) is not int
        or source_entry < 0
    ):
        raise InputBindingError("canonical identity is invalid for fold assignment")
    payload = source_sample.encode("utf-8") + b"\x00" + str(source_entry).encode("ascii")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False) % 5


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
        [fold_index_for_identity(sample, entry) for sample, entry in normalized],
        dtype=np.int64,
    )
    if folds.shape != (len(frame),) or np.any(folds < 0) or np.any(folds >= 5):
        raise InputBindingError("fold assignment is incomplete")
    return folds
