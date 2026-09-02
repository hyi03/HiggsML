from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

from src.config import load_xgboost_protocol
from src.experiment_config import ExperimentConfig
from src.experiment_runner import train_experiment
from src.training.trainer import build_development_evidence
from src.training.model import CandidateResult, FoldResult, final_tree_count
from tests.refactor_training_support import development_frame, fake_factory


PROJECT = Path(__file__).resolve().parents[2]


def test_migrated_oof_fold_candidate_and_final_tree_match_legacy() -> None:
    protocol = load_xgboost_protocol(PROJECT / "config/xgboost_protocol_v1.yaml")
    config = ExperimentConfig(
        feature_profile="angular19",
        features=protocol.features,
        grid={name: (value,) for name, value in protocol.candidate.items()},
        n_estimators=protocol.common["n_estimators"],
        early_stopping_rounds=protocol.common["early_stopping_rounds"],
        random_seed=protocol.common["random_seed"],
        n_jobs=protocol.common["n_jobs"],
        tree_method=protocol.common["tree_method"],
        folds=protocol.common["folds"],
        working_points=protocol.working_points,
    )
    frame = development_frame()
    test_rows = frame.iloc[[0, -1]].copy()
    test_rows["split"] = "test"
    test_rows["eventNumber"] = [9_000_001, 9_000_002]
    legacy_frame = pd.concat([frame, test_rows], ignore_index=True)

    legacy = train_experiment(legacy_frame, config, model_factory=fake_factory)
    migrated = build_development_evidence(frame, protocol, model_factory=fake_factory)

    np.testing.assert_array_equal(
        migrated.oof_frame["development_fold"], legacy.oof_frame["development_fold"]
    )
    np.testing.assert_allclose(
        migrated.oof_frame["oof_score"], legacy.oof_frame["oof_score"], rtol=1e-12, atol=1e-12
    )
    assert migrated.selected.mean_weighted_auc == legacy.selected.mean_weighted_auc
    assert migrated.final_parameters == legacy.final_parameters


def test_final_tree_count_uses_numpy_half_to_even() -> None:
    candidate = CandidateResult(
        index=0,
        parameters={},
        folds=tuple(
            FoldResult(index, 0.9, 0.9, best_iteration)
            for index, best_iteration in enumerate((1, 2, 2, 3))
        ),
        mean_weighted_auc=0.9,
        standard_error_weighted_auc=0.0,
        oof_scores=pd.Series(dtype=float),
    )
    # best_iteration + 1 -> [2, 3, 3, 4], median 3.0; use a direct .5 case too.
    assert final_tree_count(candidate) == 3
    half = CandidateResult(
        index=0,
        parameters={},
        folds=(FoldResult(0, 0.9, 0.9, 1), FoldResult(1, 0.9, 0.9, 2)),
        mean_weighted_auc=0.9,
        standard_error_weighted_auc=0.0,
        oof_scores=pd.Series(dtype=float),
    )
    assert final_tree_count(half) == 2
