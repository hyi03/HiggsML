from __future__ import annotations

from dataclasses import dataclass
import gzip
import io
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import InputBindingError
from src.training.config import INPUT_COLUMNS
from src.training.development_reader import _field_token


_INTEGER_COLUMNS = {"label", "source_entry", "runNumber", "eventNumber", "channelNumber"}
_TEXT_COLUMNS = {"split", "source_sample"}
_SAMPLES = {"higgs_345060", "zz_363490"}
_SAMPLE_LABELS = {"higgs_345060": 1, "zz_363490": 0}


@dataclass(frozen=True)
class ValidatedTest:
    frame: pd.DataFrame


def _decode_test_rows(payload: bytes) -> pd.DataFrame:
    dtypes = {
        name: (
            "int64"
            if name in _INTEGER_COLUMNS
            else "object"
            if name in _TEXT_COLUMNS
            else "float64"
        )
        for name in INPUT_COLUMNS
    }
    try:
        return pd.read_csv(io.BytesIO(payload), dtype=dtypes)
    except (ValueError, TypeError, UnicodeError) as error:
        raise InputBindingError("test rows cannot be decoded") from error


def read_test_rows_after_claim(table: str | Path, *, expected_rows: int) -> ValidatedTest:
    if type(expected_rows) is not int or expected_rows <= 0:
        raise InputBindingError("expected test row count changed")
    header = b",".join(name.encode("utf-8") for name in INPUT_COLUMNS) + b"\n"
    split_index = INPUT_COLUMNS.index("split")
    approved = bytearray(header)
    test_rows = 0
    try:
        with gzip.open(table, "rb") as stream:
            if stream.readline() != header:
                raise InputBindingError("preprocess table header changed")
            for line in stream:
                try:
                    split = _field_token(line, split_index).decode("ascii")
                except UnicodeError as error:
                    raise InputBindingError("preprocess split token is invalid") from error
                if split == "test":
                    test_rows += 1
                    approved.extend(line)
                elif split not in {"train", "validation"}:
                    raise InputBindingError("preprocess split token is invalid")
    except InputBindingError:
        raise
    except (OSError, EOFError) as error:
        raise InputBindingError("preprocess table cannot be routed") from error
    if test_rows != expected_rows:
        raise InputBindingError("test row count changed")
    frame = _decode_test_rows(bytes(approved))
    validate_test_frame(frame, expected_rows=expected_rows)
    return ValidatedTest(frame.copy(deep=True))


def validate_test_frame(frame: pd.DataFrame, *, expected_rows: int) -> None:
    if tuple(frame.columns) != INPUT_COLUMNS or len(frame) != expected_rows:
        raise InputBindingError("test frame schema or row count changed")
    if set(frame["split"].tolist()) != {"test"}:
        raise InputBindingError("test frame contains forbidden split")
    if set(frame["source_sample"].tolist()) - _SAMPLES:
        raise InputBindingError("test source sample changed")
    identities = tuple(zip(frame["source_sample"], frame["source_entry"], strict=True))
    if len(set(identities)) != len(identities):
        raise InputBindingError("test canonical identity is not unique")
    for column in _INTEGER_COLUMNS:
        if frame[column].dtype != np.dtype("int64"):
            raise InputBindingError("test integer dtype changed")
    if set(frame["label"].tolist()) != {0, 1}:
        raise InputBindingError("test labels changed")
    if any(
        int(row.label) != _SAMPLE_LABELS[str(row.source_sample)]
        for row in frame[["source_sample", "label"]].itertuples(index=False)
    ):
        raise InputBindingError("test sample-label binding changed")
    for column in INPUT_COLUMNS:
        if column in _TEXT_COLUMNS:
            continue
        expected_dtype = np.dtype("int64" if column in _INTEGER_COLUMNS else "float64")
        if (
            frame[column].dtype != expected_dtype
            or not np.isfinite(frame[column].to_numpy(dtype=np.float64)).all()
        ):
            raise InputBindingError("test numeric field is invalid")
    if (frame["train_weight"] < 0).any():
        raise InputBindingError("test train weight is negative")
    labels = frame["label"].to_numpy(dtype=np.int64)
    train_weights = frame["train_weight"].to_numpy(dtype=np.float64)
    physical_weights = np.abs(frame["physical_weight"].to_numpy(dtype=np.float64))
    if any(
        train_weights[labels == label].sum() <= 0.0
        or physical_weights[labels == label].sum() <= 0.0
        for label in (0, 1)
    ):
        raise InputBindingError("test class weight total is not positive")
    if ((frame["m4l"] < 105.0) | (frame["m4l"] > 160.0)).any():
        raise InputBindingError("test m4l is outside sealed range")
