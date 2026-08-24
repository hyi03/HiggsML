from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.features import FEATURES
from src.full_training_policy import assign_development_folds, development_fold
from src.decorrelation_training_run import load_decorrelation_config
from src.decorrelation_training import (
    DROP_TOP4_FEATURES,
    build_flatness_model,
    generate_flatness_oof,
)


@pytest.fixture
def production_config():
    return load_decorrelation_config(
        Path("config/decorrelation_training_drop_top4.yaml")
    )


@pytest.fixture
def development_frame():
    rows: list[dict[str, object]] = []
    event = 1
    counts = {(fold, label): 0 for fold in range(5) for label in (0, 1)}
    while min(counts.values()) < 3:
        for label in (0, 1):
            channel = 363490 if label == 0 else 345060
            event_number = event * 2 + label
            fold = development_fold(channel, event_number, folds=5)
            if counts[(fold, label)] >= 3:
                continue
            row = {name: float(event + offset) for offset, name in enumerate(FEATURES)}
            row.update(
                {
                    "m4l": 105.0 + event % 55,
                    "eventNumber": event_number,
                    "channelNumber": channel,
                    "split": "train" if event % 2 else "validation",
                    "label": label,
                    "physical_weight": (-1.0 if event % 7 == 0 else 1.0)
                    * (1.0 + label),
                }
            )
            rows.append(row)
            counts[(fold, label)] += 1
        event += 1
    frame = pd.DataFrame(rows)
    for split in ("train", "validation"):
        for label in (0, 1):
            if not ((frame["split"] == split) & (frame["label"] == label)).any():
                index = frame.index[frame["label"] == label][0]
                frame.loc[index, "split"] = split
    assigned = assign_development_folds(frame)
    per_label_folds = assigned.groupby(frame.loc[assigned.index, "label"]).nunique()
    assert per_label_folds.to_dict() == {0: 5, 1: 5}
    return frame


def test_model_exposes_mass_to_loss_but_not_to_trees(production_config):
    captured: dict[str, object] = {}

    def factory(**kwargs):
        captured.update(kwargs)
        return object()

    build_flatness_model(production_config, 1.0, model_factory=factory)

    assert captured["train_features"] == list(DROP_TOP4_FEATURES)
    assert "m4l" not in captured["train_features"]
    loss = captured["loss"]
    assert loss.uniform_features == ["m4l"]
    assert np.array_equal(loss.uniform_label, np.array([0]))
    assert loss.fl_coefficient == 1.0


def test_oof_scores_every_development_row_once_and_rebalances_each_fold(
    development_frame, production_config
):
    fitted_indices: list[tuple[int, ...]] = []

    class FakeModel:
        def fit(self, x, y, sample_weight):
            assert list(x.columns) == [*DROP_TOP4_FEATURES, "m4l"]
            fitted_indices.append(tuple(int(index) for index in x.index))
            labels = y.to_numpy(dtype=int)
            totals = [sample_weight[labels == label].sum() for label in (0, 1)]
            assert np.isclose(totals[0], totals[1])
            return self

        def predict_proba(self, x):
            score = np.linspace(0.1, 0.9, len(x))
            return np.column_stack([1.0 - score, score])

    oof = generate_flatness_oof(
        development_frame,
        production_config,
        0.5,
        model_factory=lambda **kwargs: FakeModel(),
    )

    assert oof.index.equals(development_frame.index)
    assert oof["development_fold"].between(0, 4).all()
    assert np.isfinite(oof["score_lambda_0p5"]).all()
    assert len(fitted_indices) == 5
