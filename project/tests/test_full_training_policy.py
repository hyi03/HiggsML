from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.features import FEATURES, FORBIDDEN_FEATURES
import src.full_training_policy as full_training_policy
from src.full_training_policy import (
    assign_development_folds,
    candidate_specs,
    class_balanced_training_weights,
    development_fold,
    load_training_policy,
    validate_mc_frame,
)


@pytest.fixture
def valid_frame() -> pd.DataFrame:
    rows = []
    found = {0: set(), 1: set()}
    event_number = 1
    while any(len(values) < 5 for values in found.values()):
        channel_number = 345060 if event_number % 2 else 700600
        payload = f"task4b-fold:{channel_number}:{event_number}".encode()
        fold = int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big") % 5
        label = event_number % 2
        if fold not in found[label]:
            found[label].add(fold)
            rows.append(
                {
                    **{feature: float(event_number) for feature in FEATURES},
                    "m4l": 125.0,
                    "eventNumber": event_number,
                    "channelNumber": channel_number,
                    "split": "train" if event_number % 3 else "validation",
                    "label": label,
                    "physical_weight": -1.0 if label else 1.0,
                }
            )
        event_number += 1
    for label in (0, 1):
        rows.append(
            {
                **{feature: 1.0 for feature in FEATURES},
                "m4l": 125.0,
                "eventNumber": event_number,
                "channelNumber": 345060,
                "split": "test",
                "label": label,
                "physical_weight": 1.0,
            }
        )
        event_number += 1
    return pd.DataFrame(rows)


def _with_identifier_collision(
    frame: pd.DataFrame,
    *,
    label: int | None = None,
    split: str | None = None,
) -> tuple[pd.DataFrame, tuple[int, int]]:
    original_index = int(frame.index[0])
    duplicate_index = int(frame.index.max()) + 1
    duplicate = frame.loc[[original_index]].copy()
    duplicate.index = [duplicate_index]
    if label is not None:
        duplicate.loc[duplicate_index, "label"] = label
    if split is not None:
        duplicate.loc[duplicate_index, "split"] = split
    return pd.concat([frame, duplicate]), (original_index, duplicate_index)


def test_balanced_weights_use_absolute_physical_weight_and_equal_class_totals():
    frame = pd.DataFrame(
        {"label": [0, 0, 1, 1], "physical_weight": [-2.0, 1.0, 0.25, -0.75]}
    )
    weights = class_balanced_training_weights(frame)
    assert weights.tolist() == pytest.approx([4 / 3, 2 / 3, 0.5, 1.5])
    assert weights[frame.label == 0].sum() == pytest.approx(2.0)
    assert weights[frame.label == 1].sum() == pytest.approx(2.0)
    assert weights.mean() == pytest.approx(1.0)
    assert (weights >= 0).all()


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_balanced_weights_reject_nonfinite_physical_weight(bad):
    frame = pd.DataFrame({"label": [0, 1], "physical_weight": [1.0, bad]})
    with pytest.raises(ValueError, match="physical_weight must be finite"):
        class_balanced_training_weights(frame)


def test_balanced_weights_reject_zero_absolute_class_sum():
    frame = pd.DataFrame({"label": [0, 1], "physical_weight": [0.0, 1.0]})
    with pytest.raises(ValueError, match="positive absolute physical-weight sum"):
        class_balanced_training_weights(frame)


def test_training_multipliers_preserve_class_balance(valid_frame):
    multipliers = pd.Series(1.0, index=valid_frame.index)
    zz = valid_frame["label"].eq(0)
    multipliers.loc[zz & valid_frame["m4l"].between(120, 130, inclusive="left")] = 2.0

    weights = class_balanced_training_weights(valid_frame, multipliers=multipliers)

    assert weights[zz].sum() == pytest.approx(len(valid_frame) / 2)
    assert weights[~zz].sum() == pytest.approx(len(valid_frame) / 2)
    assert weights.mean() == pytest.approx(1.0)


def test_default_weights_are_exactly_unchanged(valid_frame):
    before = class_balanced_training_weights(valid_frame)
    after = class_balanced_training_weights(valid_frame, multipliers=None)

    np.testing.assert_array_equal(after, before)


@pytest.mark.parametrize(
    ("build_multipliers", "error_type", "message"),
    [
        (lambda frame: [1.0] * len(frame), TypeError, "pandas Series"),
        (
            lambda frame: pd.Series(1.0, index=frame.index[::-1]),
            ValueError,
            "index",
        ),
        (lambda frame: pd.Series(1.0, index=frame.index[:-1]), ValueError, "index"),
        (
            lambda frame: pd.concat(
                [
                    pd.Series(1.0, index=frame.index),
                    pd.Series([1.0], index=[int(frame.index.max()) + 1]),
                ]
            ),
            ValueError,
            "index",
        ),
        (lambda frame: pd.Series(0.0, index=frame.index), ValueError, "positive"),
        (lambda frame: pd.Series(-1.0, index=frame.index), ValueError, "positive"),
        (lambda frame: pd.Series(np.nan, index=frame.index), ValueError, "finite"),
        (lambda frame: pd.Series(np.inf, index=frame.index), ValueError, "finite"),
    ],
)
def test_training_multipliers_reject_invalid_values_before_output_allocation(
    valid_frame, monkeypatch, build_multipliers, error_type, message
):
    """Removing strict validation before the output array must fail this test."""
    multipliers = build_multipliers(valid_frame)

    def output_allocation_is_a_bug(*args, **kwargs):
        raise AssertionError("output allocation must follow multiplier validation")

    monkeypatch.setattr(full_training_policy.np, "empty", output_allocation_is_a_bug)

    with pytest.raises(error_type, match=message):
        class_balanced_training_weights(valid_frame, multipliers=multipliers)


@pytest.mark.parametrize(
    "column",
    FEATURES + ["m4l", "eventNumber", "channelNumber", "split", "label", "physical_weight"],
)
def test_validate_mc_frame_requires_every_analysis_column(valid_frame, column):
    with pytest.raises(ValueError, match="missing required columns"):
        validate_mc_frame(valid_frame.drop(columns=column))


def test_validate_mc_frame_requires_exact_labels_and_splits(valid_frame):
    with pytest.raises(ValueError, match="labels must be exactly"):
        validate_mc_frame(valid_frame.assign(label=2))
    with pytest.raises(ValueError, match="unknown split"):
        validate_mc_frame(valid_frame.assign(split="data"))


def test_validate_mc_frame_accepts_complete_frame_without_mutating_it(valid_frame):
    before = valid_frame.copy(deep=True)
    assert validate_mc_frame(valid_frame) is None
    pd.testing.assert_frame_equal(valid_frame, before)


def test_validate_mc_frame_accepts_safe_identifier_collision_without_mutation(
    valid_frame,
):
    collided, _ = _with_identifier_collision(valid_frame)
    before = collided.copy(deep=True)

    assert validate_mc_frame(collided) is None

    pd.testing.assert_frame_equal(collided, before)


def test_validate_mc_frame_rejects_identifier_collision_across_labels(valid_frame):
    original_label = int(valid_frame.loc[0, "label"])
    collided, _ = _with_identifier_collision(valid_frame, label=1 - original_label)

    with pytest.raises(
        ValueError, match="identifier collision groups must not span labels"
    ):
        validate_mc_frame(collided)


def test_validate_mc_frame_rejects_identifier_collision_across_splits(valid_frame):
    original_split = str(valid_frame.loc[0, "split"])
    other_split = "validation" if original_split == "train" else "train"
    collided, _ = _with_identifier_collision(valid_frame, split=other_split)

    with pytest.raises(
        ValueError, match="identifier collision groups must not span splits"
    ):
        validate_mc_frame(collided)


def test_features_still_exclude_mass_identifiers_and_weights():
    assert "m4l" not in FEATURES
    assert set(FEATURES).isdisjoint(FORBIDDEN_FEATURES)


def test_development_fold_is_namespaced_deterministic_and_in_range():
    first = development_fold(345060, 123456, folds=5)
    assert first == development_fold(345060, 123456, folds=5)
    assert 0 <= first < 5


def test_assign_folds_excludes_test_and_preserves_row_identity(valid_frame):
    assigned = assign_development_folds(valid_frame, folds=5)
    assert set(assigned.index) == set(valid_frame[valid_frame.split != "test"].index)
    assert set(assigned.unique()) <= set(range(5))


def test_assign_folds_retains_colliding_development_rows_in_the_same_fold(valid_frame):
    collided, (original_index, duplicate_index) = _with_identifier_collision(
        valid_frame
    )

    assigned = assign_development_folds(collided, folds=5)

    assert original_index in assigned.index
    assert duplicate_index in assigned.index
    assert len(assigned) == int((collided["split"] != "test").sum())
    assert assigned.loc[original_index] == assigned.loc[duplicate_index]


def test_load_training_policy_freezes_approved_six_candidate_configuration():
    policy = load_training_policy(Path("config/full_training.yaml"))
    assert [candidate.name for candidate in candidate_specs(policy)] == [
        "depth2_child20",
        "depth2_child5",
        "depth3_child20",
        "depth3_child5",
        "depth4_child20",
        "depth4_child5",
    ]
    assert policy.folds == 5
    assert policy.working_points == {"loose": 0.5, "medium": 0.2, "tight": 0.1}


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"schema_version": "2.0"}, "schema_version"),
        ({"folds": 4}, "folds"),
        ({"n_jobs": 0}, "n_jobs"),
        ({"random_seed": 7}, "random_seed"),
        ({"working_points": {"loose": 0.5}}, "working_points"),
        ({"warnings": {"auc_gap_limit": 0.04, "ks_distance_limit": 0.10}}, "warnings"),
        ({"mass_bins_gev": [105, 110, 109]}, "mass_bins_gev"),
    ],
)
def test_load_training_policy_rejects_frozen_policy_changes(tmp_path, update, message):
    source = Path("config/full_training.yaml")
    payload = yaml.safe_load(source.read_text())
    payload.update(update)
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(payload))
    with pytest.raises(ValueError, match=message):
        load_training_policy(path)


def test_load_training_policy_rejects_duplicate_candidates_and_missing_warning(tmp_path):
    source = Path("config/full_training.yaml")
    duplicate_candidate = yaml.safe_load(source.read_text())
    duplicate_candidate["candidates"]["max_depth"].append(4)
    duplicate_path = tmp_path / "duplicate.yaml"
    duplicate_path.write_text(yaml.safe_dump(duplicate_candidate))
    with pytest.raises(ValueError, match="candidate product"):
        load_training_policy(duplicate_path)

    missing_warning = yaml.safe_load(source.read_text())
    del missing_warning["warnings"]["ks_distance_limit"]
    warning_path = tmp_path / "missing-warning.yaml"
    warning_path.write_text(yaml.safe_dump(missing_warning))
    with pytest.raises(ValueError, match="warnings"):
        load_training_policy(warning_path)


def test_load_training_policy_rejects_changed_common_parameter(tmp_path):
    payload = yaml.safe_load(Path("config/full_training.yaml").read_text())
    payload["common_parameters"]["learning_rate"] = 0.1
    path = tmp_path / "changed-common-parameter.yaml"
    path.write_text(yaml.safe_dump(payload))
    with pytest.raises(ValueError, match="common_parameters"):
        load_training_policy(path)
