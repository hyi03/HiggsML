from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
import torch

from src.config import InputBindingError
from src.training.dataset import (
    FEATURE_COLUMNS,
    FoldLocalScaler,
    ValidatedFold,
    build_validated_fold,
    validate_development_frame,
)
from tests.training_fixtures import synthetic_development_frame


def test_development_contract_and_fold_local_scaler() -> None:
    frame = synthetic_development_frame(validation_shift=1000.0)
    development = validate_development_frame(frame, protocol_sha256="a" * 64)
    fitting = np.flatnonzero(frame["split"].to_numpy() == "train")
    validation = np.flatnonzero(frame["split"].to_numpy() == "validation")
    fold = build_validated_fold(development, fitting, validation, fold_index=0)

    assert fold.fitting_features.shape == (22, 15)
    assert fold.validation_features.shape == (22, 15)
    assert fold.fitting_features.dtype == torch.float32
    assert fold.labels.dtype == torch.int64
    assert np.allclose(fold.scaler.mean, frame.loc[fitting, FEATURE_COLUMNS].to_numpy().mean(axis=0))
    assert float(fold.validation_features.mean()) > 100.0
    assert set(fold.mass_bins[fold.labels == 0].tolist()) == set(range(11))
    assert set(fold.mass_bins[fold.labels == 1].tolist()) == {-1}


@pytest.mark.parametrize("mutation", ["missing", "extra", "reordered", "nan", "test"])
def test_development_contract_fails_closed(mutation: str) -> None:
    frame = synthetic_development_frame()
    if mutation == "missing":
        frame = frame.drop(columns=[FEATURE_COLUMNS[0]])
    elif mutation == "extra":
        frame["extra"] = 1.0
    elif mutation == "reordered":
        frame = frame[frame.columns[::-1]]
    elif mutation == "nan":
        frame.loc[0, FEATURE_COLUMNS[0]] = np.nan
    else:
        frame.loc[0, "split"] = "test"

    with pytest.raises(InputBindingError):
        validate_development_frame(frame, protocol_sha256="a" * 64)


def test_scaler_zero_variance_and_round_trip() -> None:
    matrix = np.ones((4, 15), dtype=np.float64)
    scaler = FoldLocalScaler.fit(matrix)

    assert np.array_equal(scaler.scale, np.ones(15))
    restored = FoldLocalScaler.from_dict(scaler.to_dict())
    assert np.array_equal(restored.transform(matrix), np.zeros_like(matrix, dtype=np.float32))


def test_fold_rejects_identity_overlap_and_empty_mass_bin() -> None:
    frame = synthetic_development_frame()
    development = validate_development_frame(frame, protocol_sha256="a" * 64)
    fitting = np.flatnonzero(frame["split"].to_numpy() == "train")
    validation = np.flatnonzero(frame["split"].to_numpy() == "validation")

    with pytest.raises(InputBindingError, match="overlap"):
        build_validated_fold(development, fitting, np.append(validation, fitting[0]), fold_index=0)

    without_first_bin = fitting[~((frame.loc[fitting, "label"].to_numpy() == 0) & (frame.loc[fitting, "m4l"].to_numpy() < 110))]
    with pytest.raises(InputBindingError, match="mass bin"):
        build_validated_fold(development, without_first_bin, validation, fold_index=0)


class _SplitFirstPoisonFrame(pd.DataFrame):
    accessed: list[str]

    def __getitem__(self, key: object):
        self.accessed.append(str(key))
        if key != "split":
            raise AssertionError(f"accessed {key!r} before forbidden split refusal")
        return super().__getitem__(key)


def test_forbidden_test_split_is_refused_before_other_column_access() -> None:
    source = synthetic_development_frame()
    source.loc[0, "split"] = "test"
    frame = _SplitFirstPoisonFrame(source)
    object.__setattr__(frame, "accessed", [])

    with pytest.raises(InputBindingError, match="forbidden split"):
        validate_development_frame(frame, protocol_sha256="a" * 64)

    assert frame.accessed == ["split"]


@pytest.mark.parametrize(
    "mutation",
    ["empty_identity", "duplicate_identity", "label_dtype", "m4l_nonfinite", "m4l_range", "negative_weight", "bad_hash"],
)
def test_development_representative_contract_mutations(mutation: str) -> None:
    frame = synthetic_development_frame()
    protocol_sha256 = "a" * 64
    if mutation == "empty_identity":
        frame.loc[0, "source_sample"] = ""
    elif mutation == "duplicate_identity":
        frame.loc[1, ["source_sample", "source_entry"]] = frame.loc[
            0, ["source_sample", "source_entry"]
        ].to_numpy()
    elif mutation == "label_dtype":
        frame["label"] = frame["label"].astype(np.float64)
    elif mutation == "m4l_nonfinite":
        frame.loc[0, "m4l"] = np.inf
    elif mutation == "m4l_range":
        frame.loc[0, "m4l"] = 104.999
    elif mutation == "negative_weight":
        frame.loc[0, "train_weight"] = -1.0
    else:
        protocol_sha256 = "not-a-sha"

    with pytest.raises(InputBindingError):
        validate_development_frame(frame, protocol_sha256=protocol_sha256)


def test_fold_indices_and_validation_auc_preconditions_fail_closed() -> None:
    frame = synthetic_development_frame()
    development = validate_development_frame(frame, protocol_sha256="a" * 64)
    fitting = np.flatnonzero(frame["split"].to_numpy() == "train")
    validation = np.flatnonzero(frame["split"].to_numpy() == "validation")

    for invalid in (
        np.array([], dtype=np.int64),
        np.array([fitting[0], fitting[0]], dtype=np.int64),
        np.array([len(frame)], dtype=np.int64),
        np.array([float(fitting[0])]),
    ):
        with pytest.raises(InputBindingError):
            build_validated_fold(development, invalid, validation, fold_index=0)

    one_class = validation[frame.loc[validation, "label"].to_numpy() == 0]
    with pytest.raises(InputBindingError, match="AUC preconditions"):
        build_validated_fold(development, fitting, one_class, fold_index=0)

    zero_weight_frame = frame.copy()
    zero_weight_frame.loc[validation, "train_weight"] = 0.0
    zero_weight_development = validate_development_frame(
        zero_weight_frame, protocol_sha256="a" * 64
    )
    with pytest.raises(InputBindingError, match="AUC preconditions"):
        build_validated_fold(zero_weight_development, fitting, validation, fold_index=0)


def test_validated_fold_rejects_representative_direct_mutations() -> None:
    frame = synthetic_development_frame()
    development = validate_development_frame(frame, protocol_sha256="a" * 64)
    fitting = np.flatnonzero(frame["split"].to_numpy() == "train")
    validation = np.flatnonzero(frame["split"].to_numpy() == "validation")
    fold = build_validated_fold(development, fitting, validation, fold_index=0)

    mutations = (
        lambda: replace(fold, fitting_features=fold.fitting_features[:, :-1]),
        lambda: replace(fold, labels=fold.labels.to(torch.int32)),
        lambda: replace(fold, adversarial_weights=fold.adversarial_weights[:-1]),
        lambda: replace(fold, mass_bins=torch.zeros_like(fold.mass_bins)),
        lambda: replace(
            fold,
            scaler=FoldLocalScaler(
                fold.scaler.mean, fold.scaler.scale, fold.scaler.fitting_rows + 1
            ),
        ),
    )
    for mutate in mutations:
        with pytest.raises(InputBindingError):
            mutate()


def test_input_errors_do_not_expose_rows_values_or_paths() -> None:
    frame = synthetic_development_frame()
    secret_value = "987654.321"
    frame.loc[0, FEATURE_COLUMNS[0]] = float(secret_value)
    frame.loc[0, FEATURE_COLUMNS[1]] = np.nan

    with pytest.raises(InputBindingError) as caught:
        validate_development_frame(frame, protocol_sha256="a" * 64)

    message = str(caught.value)
    assert secret_value not in message
    assert "D:\\" not in message
    assert "source_entry" not in message
