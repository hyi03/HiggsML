from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.full_training_evaluation import build_working_points as legacy_points
from src.training.evaluation import background_mass_ks, build_working_points


def _oof() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "channelNumber": [363490] * 4 + [345060] * 4,
            "eventNumber": list(range(8)),
            "split": ["train", "validation"] * 4,
            "label": [0] * 4 + [1] * 4,
            "physical_weight": [-1.0, 2.0, 3.0, 4.0] + [1.0] * 4,
            "m4l": [120.0, 121.0, 122.0, 123.0] + [125.0] * 4,
            "development_fold": [0, 1, 2, 3, 0, 1, 2, 3],
            "oof_score": [0.9, 0.8, 0.8, 0.1, 0.99, 0.98, 0.97, 0.96],
        }
    )


def test_working_points_match_legacy_and_retain_complete_score_tie() -> None:
    targets = {"loose": 0.5, "medium": 0.2, "tight": 0.1}
    expected = legacy_points(_oof(), targets)
    actual = build_working_points(_oof(), targets)

    assert actual == expected
    assert actual["loose"]["threshold"] == 0.8
    assert actual["loose"]["achieved_background_efficiency"] == 0.6


def test_background_mass_ks_passes_signed_weights_to_abs_weight_semantics() -> None:
    points = build_working_points(_oof(), {"loose": 0.5, "medium": 0.2, "tight": 0.1})
    result = background_mass_ks(_oof(), points)
    assert set(result) == {"loose", "medium", "tight"}
    assert all(value is not None and np.isfinite(value) for value in result.values())


def test_working_points_reject_missing_zz() -> None:
    with pytest.raises(ValueError, match="contain ZZ"):
        build_working_points(
            _oof().loc[_oof()["label"] == 1].assign(label=1),
            {"loose": 0.5, "medium": 0.2, "tight": 0.1},
        )
