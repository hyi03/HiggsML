from __future__ import annotations

from pathlib import Path

from src.training.qualification import qualify
from src.config import load_xgboost_protocol
from tests.unit.test_refactor_training_evaluation import _oof


PROJECT = Path(__file__).resolve().parents[2]


def test_qualification_requires_every_frozen_gate() -> None:
    protocol = load_xgboost_protocol(PROJECT / "config/xgboost_protocol_v1.yaml")
    working_points = {
        name: {
            "threshold": 0.5,
            "target_background_efficiency": target,
            "achieved_background_efficiency": target,
            "signal_efficiency": target + 0.1,
        }
        for name, target in protocol.working_points.items()
    }
    ks = {name: 0.10 for name in working_points}

    result = qualify(
        _oof(), 0.80, working_points, ks, protocol.qualification,
        expected_development=_oof(),
    )
    assert result["status"] == "eligible"
    assert result["eligible"] is True

    working_points["tight"]["signal_efficiency"] = working_points["tight"]["achieved_background_efficiency"]
    rejected = qualify(
        _oof(), 0.80, working_points, ks, protocol.qualification,
        expected_development=_oof(),
    )
    assert rejected["status"] == "no_eligible_candidate"
    assert "signal_efficiency_above_background" in rejected["failed_checks"]


def test_qualification_rejects_auc_ks_and_incomplete_oof_boundaries() -> None:
    protocol = load_xgboost_protocol(PROJECT / "config/xgboost_protocol_v1.yaml")
    points = {
        name: {
            "threshold": 0.5,
            "target_background_efficiency": target,
            "achieved_background_efficiency": target,
            "signal_efficiency": 1.0,
        }
        for name, target in protocol.working_points.items()
    }
    ks = {name: 0.10 for name in points}
    incomplete = _oof().iloc[:-1].copy()
    result = qualify(
        incomplete, 0.799999, points, {**ks, "tight": 0.100001},
        protocol.qualification, expected_development=_oof(),
    )
    assert result["eligible"] is False
    assert set(result["failed_checks"]) == {
        "weighted_oof_auc", "background_mass_ks", "oof_complete_finite_unique"
    }
