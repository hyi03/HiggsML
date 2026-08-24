"""Run and publish the sealed MC-only KNN-flatness study."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.decorrelation_training import FlatnessOutcome
from src.decorrelation_training_plots import (
    plot_candidate_tradeoff,
    plot_selected_mass_sculpting,
    plot_working_point_ks,
)
from src.decorrelation_training_run import DecorrelationConfig


def build_decorrelation_artifacts(
    outcome: FlatnessOutcome, config: DecorrelationConfig
) -> dict[str, Any]:
    results = tuple(outcome.selection.results)
    if not results:
        candidate_results = pd.DataFrame()
        working_point_metrics = pd.DataFrame()
        oof_scores = pd.DataFrame()
        plot_artifacts = {}
    else:
        candidate_results = pd.DataFrame(
            [_candidate_row(result) for result in results]
        )
        working_point_metrics = pd.DataFrame(
            [
                _working_point_row(result, name)
                for result in results
                for name in ("loose", "medium", "tight")
            ]
        )
        oof_scores = _wide_oof_scores(results)
        plot_artifacts = {
            "candidate_tradeoff.png": plot_candidate_tradeoff(results),
            "working_point_ks.png": plot_working_point_ks(results),
        }

    selected = outcome.selection.selected
    if selected is None:
        return {
            "candidate_results": candidate_results,
            "working_point_metrics": working_point_metrics,
            "selection": {
                "schema_version": "1.0",
                "status": "no_eligible_candidate",
                "selected_candidate": None,
                "test_opened": False,
                "auc_floor": config.auc_floor,
                "ks_limit": config.ks_limit,
            },
            "oof_scores": oof_scores,
            "plot_artifacts": plot_artifacts,
            "model": None,
            "selected_oof_scores": None,
            "test_scores": None,
            "test_metrics": None,
        }

    evidence = outcome.evidence
    if evidence is None or float(evidence.coefficient) != float(selected.coefficient):
        raise ValueError("selected flatness outcome is missing matching test evidence")
    selected_oof = evidence.oof_scores.copy(deep=True)
    score_column = _score_column(selected.coefficient)
    if score_column not in selected_oof:
        raise ValueError("selected OOF evidence is missing its candidate score")
    selected_oof = selected_oof.rename(columns={score_column: "oof_score"})
    plot_artifacts["selected_mass_sculpting.png"] = plot_selected_mass_sculpting(
        selected_oof,
        evidence.test_scores,
        selected.working_points,
        mass_bins_gev=config.mass_bins_gev,
    )
    return {
        "candidate_results": candidate_results,
        "working_point_metrics": working_point_metrics,
        "selection": {
            "schema_version": "1.0",
            "status": "eligible_candidate_test_scored",
            "selected_candidate": _candidate_name(selected.coefficient),
            "test_opened": True,
            "auc_floor": config.auc_floor,
            "ks_limit": config.ks_limit,
            "selection_basis": "development_oof_only",
        },
        "oof_scores": oof_scores,
        "plot_artifacts": plot_artifacts,
        "model": evidence.model,
        "selected_oof_scores": selected_oof,
        "test_scores": evidence.test_scores.copy(deep=True),
        "test_metrics": dict(evidence.test_metrics),
    }


def _candidate_row(result) -> dict[str, Any]:
    return {
        "candidate": _candidate_name(result.coefficient),
        "flatness_coefficient": float(result.coefficient),
        "weighted_oof_auc": float(result.weighted_auc),
        "maximum_oof_zz_ks": max(float(value) for value in result.zz_ks_distances.values()),
        "oof_zz_score_mass_correlation": float(
            result.background_score_mass_correlation
        ),
        "eligible": not result.eligibility_reasons,
        "eligibility_reasons": ",".join(result.eligibility_reasons),
    }


def _working_point_row(result, name: str) -> dict[str, Any]:
    point = result.working_points[name]
    return {
        "candidate": _candidate_name(result.coefficient),
        "flatness_coefficient": float(result.coefficient),
        "working_point": name,
        "threshold": float(point["threshold"]),
        "target_background_efficiency": float(
            result.target_background_efficiencies[name]
        ),
        "achieved_background_efficiency": float(
            point["achieved_background_efficiency"]
        ),
        "signal_efficiency": float(result.signal_efficiencies[name]),
        "oof_zz_mass_ks": float(result.zz_ks_distances[name]),
    }


def _wide_oof_scores(results) -> pd.DataFrame:
    first = results[0].oof_scores.copy(deep=True)
    score_columns = [column for column in first if column.startswith("score_lambda_")]
    if len(score_columns) != 1:
        raise ValueError("each candidate must contain exactly one OOF score column")
    base_columns = [column for column in first if column not in score_columns]
    output = first.loc[:, base_columns].copy()
    output[score_columns[0]] = first[score_columns[0]].to_numpy(dtype=float)
    for result in results[1:]:
        audit = result.oof_scores
        candidate_scores = [
            column for column in audit if column.startswith("score_lambda_")
        ]
        if len(candidate_scores) != 1 or not audit.index.equals(first.index):
            raise ValueError("candidate OOF audits do not share the same rows")
        pd.testing.assert_frame_equal(
            audit.loc[:, base_columns], first.loc[:, base_columns]
        )
        output[candidate_scores[0]] = audit[candidate_scores[0]].to_numpy(dtype=float)
    return output


def _candidate_name(coefficient: float) -> str:
    return f"lambda_{float(coefficient):.1f}".replace(".", "p")


def _score_column(coefficient: float) -> str:
    return f"score_{_candidate_name(coefficient)}"
