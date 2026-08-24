"""Artifact conversion surface for the sealed DropTop4 flatness study."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.decorrelation_training import FlatnessOutcome
from src.decorrelation_training_plots import (
    plot_candidate_tradeoff,
    plot_selected_mass_sculpting,
    plot_working_point_ks,
)
from src.decorrelation_training_run import DecorrelationConfig


_WORKING_POINTS = ("loose", "medium", "tight")
_AUDIT_COLUMNS = (
    "eventNumber",
    "channelNumber",
    "split",
    "label",
    "physical_weight",
    "m4l",
    "development_fold",
)
_IDENTITY_COLUMNS = ("channelNumber", "eventNumber", "split")
_MASS_BINS_GEV = (105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160)


def build_decorrelation_artifacts(
    outcome: FlatnessOutcome, config: DecorrelationConfig
) -> dict[str, Any]:
    """Convert one immutable domain outcome into deterministic artifact values."""
    if not isinstance(outcome, FlatnessOutcome):
        raise ValueError("decorrelation artifacts require a FlatnessOutcome")
    results = tuple(outcome.selection.results)
    if tuple(result.coefficient for result in results) != tuple(config.coefficients):
        raise ValueError("candidate results must match the frozen coefficient order")

    candidate_rows: list[dict[str, Any]] = []
    working_point_rows: list[dict[str, Any]] = []
    for result in results:
        candidate = _candidate_name(result.coefficient)
        candidate_rows.append(
            {
                "candidate": candidate,
                "coefficient": float(result.coefficient),
                "weighted_oof_auc": float(result.weighted_auc),
                "maximum_oof_zz_ks": max(
                    float(result.zz_ks_distances[name]) for name in _WORKING_POINTS
                ),
                "background_score_mass_correlation": float(
                    result.background_score_mass_correlation
                ),
                "eligible": not result.eligibility_reasons,
                "eligibility_reasons": ",".join(result.eligibility_reasons),
            }
        )
        for name in _WORKING_POINTS:
            point = result.working_points[name]
            working_point_rows.append(
                {
                    "candidate": candidate,
                    "coefficient": float(result.coefficient),
                    "working_point": name,
                    "threshold": float(point["threshold"]),
                    "target_background_efficiency": float(
                        result.target_background_efficiencies[name]
                    ),
                    "achieved_background_efficiency": float(
                        result.achieved_background_efficiencies[name]
                    ),
                    "signal_efficiency": float(result.signal_efficiencies[name]),
                    "zz_mass_ks_distance": float(result.zz_ks_distances[name]),
                }
            )

    plot_artifacts = {
        "candidate_tradeoff.png": plot_candidate_tradeoff(results),
        "working_point_ks.png": plot_working_point_ks(results),
    }
    artifacts: dict[str, Any] = {
        "candidate_results": pd.DataFrame(candidate_rows),
        "working_point_metrics": pd.DataFrame(working_point_rows),
        "oof_scores": _wide_oof_audit(results),
        "selection": {
            "schema_version": "1.0",
            "status": "no_eligible_candidate",
            "selected_candidate": None,
            "test_opened": False,
            "auc_floor": float(config.auc_floor),
            "ks_limit": float(config.ks_limit),
        },
        "plot_artifacts": plot_artifacts,
        "model": None,
        "selected_oof_scores": None,
        "test_scores": None,
        "test_metrics": None,
    }
    selected = outcome.selection.selected
    if selected is None:
        if outcome.evidence is not None:
            raise ValueError("no-selection outcome must not contain selected evidence")
        return artifacts
    if outcome.evidence is None:
        raise ValueError("selected outcome is missing frozen test evidence")

    evidence = outcome.evidence
    candidate_name = _candidate_name(selected.coefficient)
    selected_oof = selected.oof_scores.copy(deep=True).rename(
        columns={_score_column(selected.coefficient): "oof_score"}
    )
    plot_artifacts["selected_mass_sculpting.png"] = plot_selected_mass_sculpting(
        selected_oof,
        evidence.test_scores,
        selected.working_points,
        mass_bins_gev=_MASS_BINS_GEV,
    )
    artifacts.update(
        selection={
            "schema_version": "1.0",
            "status": "eligible_candidate_test_reported",
            "selected_candidate": candidate_name,
            "test_opened": True,
            "auc_floor": float(config.auc_floor),
            "ks_limit": float(config.ks_limit),
        },
        model=evidence.model,
        selected_oof_scores=selected_oof,
        test_scores=evidence.test_scores.copy(deep=True),
        test_metrics=_test_metrics(evidence),
    )
    return artifacts


def _wide_oof_audit(results) -> pd.DataFrame:
    base: pd.DataFrame | None = None
    identity_index: pd.MultiIndex | None = None
    for result in results:
        score_column = _score_column(result.coefficient)
        frame = result.oof_scores
        required = {*_AUDIT_COLUMNS, score_column}
        if not isinstance(frame, pd.DataFrame) or not required <= set(frame):
            raise ValueError("candidate OOF audit is missing identity or score columns")
        candidate = frame.loc[:, [*_AUDIT_COLUMNS, score_column]].copy(deep=True)
        if candidate.loc[:, _IDENTITY_COLUMNS].isna().any().any():
            raise ValueError("candidate OOF audit identity must not contain missing values")
        if candidate.duplicated(list(_IDENTITY_COLUMNS)).any():
            raise ValueError("candidate OOF audit identity must be unique")
        indexed = candidate.set_index(list(_IDENTITY_COLUMNS), drop=False)
        if base is None:
            base = candidate.reset_index(drop=True)
            identity_index = indexed.index
            continue
        assert identity_index is not None
        if len(indexed) != len(identity_index) or set(indexed.index) != set(
            identity_index
        ):
            raise ValueError(
                "candidate OOF audits contain contradictory OOF audit identities"
            )
        aligned = indexed.reindex(identity_index)
        expected = base.set_index(list(_IDENTITY_COLUMNS), drop=False)
        for column in _AUDIT_COLUMNS:
            if not aligned[column].equals(expected[column]):
                raise ValueError("candidate results contain contradictory OOF audit evidence")
        base[score_column] = aligned[score_column].to_numpy(copy=True)
    if base is None:
        raise ValueError("candidate results must not be empty")
    numeric = base.loc[
        :,
        [
            "eventNumber",
            "channelNumber",
            "label",
            "physical_weight",
            "m4l",
            "development_fold",
            *[_score_column(result.coefficient) for result in results],
        ],
    ].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("wide OOF audit values must be finite")
    return base


def _test_metrics(evidence) -> dict[str, Any]:
    points: dict[str, dict[str, Any]] = {}
    for name in _WORKING_POINTS:
        frozen = evidence.working_points[name]
        points[name] = {
            "threshold": float(frozen["threshold"]),
            "target_background_efficiency": float(
                frozen["target_background_efficiency"]
            ),
            "achieved_background_efficiency": float(
                evidence.test_background_efficiencies[name]
            ),
            "signal_efficiency": float(evidence.test_signal_efficiencies[name]),
        }
    return {
        "schema_version": "1.0",
        "weighted_auc": float(evidence.test_weighted_auc),
        "background_score_mass_correlation": float(
            evidence.test_background_score_mass_correlation
        ),
        "working_points": points,
        "zz_ks_distances": {
            name: (
                None
                if evidence.test_zz_ks_distances[name] is None
                else float(evidence.test_zz_ks_distances[name])
            )
            for name in _WORKING_POINTS
        },
    }


def _candidate_name(coefficient: float) -> str:
    return f"lambda_{str(float(coefficient)).replace('.', 'p')}"


def _score_column(coefficient: float) -> str:
    return f"score_lambda_{str(float(coefficient)).replace('.', 'p')}"
