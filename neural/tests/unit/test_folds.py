from __future__ import annotations

import numpy as np
import pytest

from src.config import InputBindingError
from src.training.dataset import validate_development_frame
from src.training.folds import assign_folds, fold_index_for_identity
from tests.training_fixtures import synthetic_development_frame


def test_fold_hash_known_vectors_include_zero_entry() -> None:
    assert fold_index_for_identity("higgs_345060", 0) == 3
    assert fold_index_for_identity("zz_363490", 7) == 4
    assert fold_index_for_identity("sample", 42) == 0
    for sample, entry in (("", 0), ("bad\x00sample", 0), ("sample", -1), ("sample", True)):
        with pytest.raises(InputBindingError):
            fold_index_for_identity(sample, entry)


def test_fold_assignment_is_identity_stable_under_row_reordering() -> None:
    frame = synthetic_development_frame()
    development = validate_development_frame(frame, protocol_sha256="a" * 64)
    original = {
        (row.source_sample, row.source_entry): fold
        for row, fold in zip(frame.itertuples(), assign_folds(development), strict=True)
    }
    shuffled = frame.sample(frac=1.0, random_state=17).reset_index(drop=True)
    shuffled_development = validate_development_frame(shuffled, protocol_sha256="a" * 64)
    reordered = {
        (row.source_sample, row.source_entry): fold
        for row, fold in zip(shuffled.itertuples(), assign_folds(shuffled_development), strict=True)
    }

    assert original == reordered
    assert set(original.values()) == set(range(5))


def test_fold_assignment_rejects_non_development_and_duplicate_identity() -> None:
    frame = synthetic_development_frame()
    development = validate_development_frame(frame, protocol_sha256="a" * 64)
    development.frame.loc[0, "split"] = "test"
    with pytest.raises(InputBindingError, match="non-development"):
        assign_folds(development)

    duplicate = validate_development_frame(frame.assign(split="train"), protocol_sha256="a" * 64)
    duplicate.frame.loc[1, ["source_sample", "source_entry"]] = duplicate.frame.loc[
        0, ["source_sample", "source_entry"]
    ].to_numpy()
    with pytest.raises(InputBindingError, match="not unique"):
        assign_folds(duplicate)
