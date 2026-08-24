from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from scripts.run_decorrelation_training import build_decorrelation_artifacts
from src.decorrelation_training_run import load_decorrelation_config


def test_no_selection_artifacts_include_all_oof_audits_and_no_test():
    config = _config()
    candidate = _candidate(0.0)
    outcome = SimpleNamespace(
        selection=SimpleNamespace(results=(candidate,), selected=None),
        evidence=None,
    )

    artifacts = build_decorrelation_artifacts(outcome, config)

    assert artifacts["selection"] == {
        "schema_version": "1.0",
        "status": "no_eligible_candidate",
        "selected_candidate": None,
        "test_opened": False,
        "auc_floor": 0.80,
        "ks_limit": 0.10,
    }
    assert set(artifacts["plot_artifacts"]) == {
        "candidate_tradeoff.png",
        "working_point_ks.png",
    }
    assert artifacts["model"] is None
    assert artifacts["test_scores"] is None
    assert "score_lambda_0p0" in artifacts["oof_scores"]


def test_selected_artifacts_report_test_without_reselecting():
    config = _config()
    candidate = _candidate(1.0)
    evidence = SimpleNamespace(
        coefficient=1.0,
        model=object(),
        oof_scores=candidate.oof_scores,
        test_scores=_score_frame("score"),
        test_metrics={"weighted_auc": 0.83},
        working_points=candidate.working_points,
    )
    outcome = SimpleNamespace(
        selection=SimpleNamespace(results=(candidate,), selected=candidate),
        evidence=evidence,
    )

    artifacts = build_decorrelation_artifacts(outcome, config)

    assert artifacts["selection"]["selected_candidate"] == "lambda_1p0"
    assert artifacts["selection"]["test_opened"] is True
    assert set(artifacts["plot_artifacts"]) == {
        "candidate_tradeoff.png",
        "working_point_ks.png",
        "selected_mass_sculpting.png",
    }


def _config():
    return load_decorrelation_config(
        Path("config/decorrelation_training_drop_top4.yaml")
    )


def _candidate(coefficient):
    points = {
        "loose": {
            "threshold": 0.2,
            "target_background_efficiency": 0.5,
            "achieved_background_efficiency": 0.5,
            "signal_efficiency": 0.8,
        },
        "medium": {
            "threshold": 0.5,
            "target_background_efficiency": 0.2,
            "achieved_background_efficiency": 0.2,
            "signal_efficiency": 0.6,
        },
        "tight": {
            "threshold": 0.8,
            "target_background_efficiency": 0.1,
            "achieved_background_efficiency": 0.1,
            "signal_efficiency": 0.4,
        },
    }
    return SimpleNamespace(
        coefficient=coefficient,
        weighted_auc=0.82,
        background_score_mass_correlation=0.02,
        working_points=points,
        signal_efficiencies={"loose": 0.8, "medium": 0.6, "tight": 0.4},
        target_background_efficiencies={"loose": 0.5, "medium": 0.2, "tight": 0.1},
        zz_ks_distances={"loose": 0.05, "medium": 0.06, "tight": 0.07},
        eligibility_reasons=(),
        oof_scores=_score_frame(
            f"score_lambda_{coefficient:.1f}".replace(".", "p")
        ),
    )


def _score_frame(score_column):
    return pd.DataFrame(
        {
            "eventNumber": [1, 2, 3, 4, 5],
            "channelNumber": [363490, 363490, 363490, 345060, 345060],
            "label": [0, 0, 0, 1, 1],
            "physical_weight": [1.0, -0.5, 1.5, 1.0, 2.0],
            "m4l": [110.0, 127.0, 150.0, 124.0, 126.0],
            "development_fold": [0, 1, 2, 3, 4],
            score_column: [0.25, 0.65, 0.95, 0.7, 0.9],
        }
    )
