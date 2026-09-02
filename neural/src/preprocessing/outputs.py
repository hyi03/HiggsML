from __future__ import annotations

import csv
import gzip
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TableReceipt:
    sha256: str
    canonical_content_sha256: str
    size_bytes: int
    row_count: int | None = None


def _float_token(value) -> str:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError("canonical CSV floats must be finite")
    token = format(number, ".17g")
    return "0" if token == "-0" else token


def canonical_csv_bytes(
    frame: pd.DataFrame,
    columns: Iterable[str],
    *,
    integer_columns: set[str] | None = None,
    string_columns: set[str] | None = None,
    string_enums: dict[str, set[str]] | None = None,
) -> bytes:
    ordered = tuple(columns)
    if tuple(frame.columns) != ordered:
        raise ValueError("dataframe columns do not match canonical order")
    integers = integer_columns or set()
    strings = string_columns or set()
    enums = string_enums or {}
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(ordered)
    for row in frame.itertuples(index=False, name=None):
        tokens = []
        for name, value in zip(ordered, row):
            if name in integers:
                if isinstance(value, bool) or int(value) != value:
                    raise ValueError(f"{name} must be an integer")
                tokens.append(str(int(value)))
            elif name in strings:
                token = str(value)
                if name in enums and token not in enums[name]:
                    raise ValueError(f"{name} is not an allowed enum value")
                if any(character in token for character in (",", '"', "\r", "\n")):
                    raise ValueError(f"{name} contains a CSV special character")
                tokens.append(token)
            else:
                tokens.append(_float_token(value))
        writer.writerow(tokens)
    return buffer.getvalue().encode("utf-8")


def write_canonical_table(path: str | Path, payload: bytes, *, row_count: int | None = None) -> TableReceipt:
    compressed = gzip.compress(payload, compresslevel=9, mtime=0)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(compressed)
    return TableReceipt(
        hashlib.sha256(compressed).hexdigest(), hashlib.sha256(payload).hexdigest(), len(compressed), row_count
    )
