from __future__ import annotations

import gzip
from pathlib import Path

import pandas as pd
import pytest

from src.preprocessing.outputs import canonical_csv_bytes, write_canonical_table


def test_canonical_csv_has_fixed_tokens_and_line_endings(tmp_path: Path) -> None:
    frame = pd.DataFrame({"value": [-0.0, 1.2345678901234567], "label": [1, 0]})
    payload = canonical_csv_bytes(frame, ("value", "label"), integer_columns={"label"})

    assert payload == b"value,label\n0,1\n1.2345678901234567,0\n"

    first = write_canonical_table(tmp_path / "a.csv.gz", payload)
    second = write_canonical_table(tmp_path / "b.csv.gz", payload)
    assert first.canonical_content_sha256 == second.canonical_content_sha256
    assert (tmp_path / "a.csv.gz").read_bytes() == (tmp_path / "b.csv.gz").read_bytes()
    assert gzip.decompress((tmp_path / "a.csv.gz").read_bytes()) == payload


def test_canonical_csv_rejects_non_finite_non_integer_and_bad_enum() -> None:
    with pytest.raises(ValueError, match="finite"):
        canonical_csv_bytes(pd.DataFrame({"value": [float("nan")]}), ("value",))
    with pytest.raises(ValueError, match="integer"):
        canonical_csv_bytes(
            pd.DataFrame({"label": [1.5]}), ("label",), integer_columns={"label"}
        )
    with pytest.raises(ValueError, match="allowed enum"):
        canonical_csv_bytes(
            pd.DataFrame({"split": ["train,evil"]}),
            ("split",),
            string_columns={"split"},
            string_enums={"split": {"train", "validation", "test"}},
        )
