"""Pure, sealed development-only mass-sculpting ablation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from .full_training_evaluation import (
    build_working_points,
    weighted_pearson,
    zz_mass_diagnostics,
)
from .full_training_model import (
    ModelSelectionResult,
    cross_validate_candidates,
    final_tree_count,
    fit_final_model,
    score_model,
    validate_model_features,
)
from .full_training_policy import validate_development_frame, validate_mc_frame


_WORKING_POINT_NAMES = frozenset(("loose", "medium", "tight"))


@dataclass(frozen=True)
class FeatureProfile:
    name: str
    features: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("feature-profile name must be non-empty")
        object.__setattr__(self, "features", validate_model_features(self.features))


ABLATION_PROFILES = MappingProxyType(
    {
        "drop_top4_mass_proxies": FeatureProfile(
            "drop_top4_mass_proxies",
            (
                "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
                "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
            ),
        ),
        "shape8": FeatureProfile(
            "shape8",
            (
                "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta", "pt4l",
                "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
            ),
        ),
        "angular_eta7": FeatureProfile(
            "angular_eta7",
            (
                "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta", "deltaR_Z1",
                "deltaR_Z2", "deltaPhi_ZZ",
            ),
        ),
    }
)


@dataclass(frozen=True)
class ProfileResult:
    profile: FeatureProfile
    candidate_name: str
    final_tree_count: int
    weighted_auc: float
    score_mass_correlation: float
    working_points: Mapping[str, Mapping[str, object]]
    signal_efficiencies: Mapping[str, float]
    target_background_efficiencies: Mapping[str, float]
    zz_ks_distances: Mapping[str, float]
    eligibility_reasons: tuple[str, ...] = ()
    selection: ModelSelectionResult | None = None
    oof_scores: pd.DataFrame | None = None


@dataclass(frozen=True)
class SelectedProfileEvidence:
    profile: FeatureProfile
    model: Any
    test_scores: pd.DataFrame
    test_weighted_auc: float
    test_zz_diagnostics: Mapping[str, object]
    working_points: Mapping[str, Mapping[str, object]]


@dataclass(frozen=True)
class AblationOutcome:
    """All canonical development evidence and optional one-time test evidence."""
    development_results: Mapping[str, ProfileResult]
    selected: ProfileResult | None
    evidence: SelectedProfileEvidence | None


def evaluate_development_profile(
    frame: pd.DataFrame,
    policy,
    profile: FeatureProfile,
    *,
    model_factory=None,
) -> ProfileResult:
    """Produce OOF-only profile evidence without scoring independent test rows."""
    _validate_profile(profile)
    development = frame.loc[frame["split"] != "test"].copy()
    validate_development_frame(development)
    selection = cross_validate_candidates(
        development, policy, model_factory, features=profile.features
    )
    oof = _oof_frame(development, selection)
    points = build_working_points(oof, policy.working_points)
    diagnostics = zz_mass_diagnostics(oof, "oof_score", points, policy)
    zz = oof.loc[oof["label"] == 0]
    distances = {
        name: float(values["inclusive_to_selected_ks_distance"])
        for name, values in diagnostics["working_points"].items()
    }
    result = ProfileResult(
        profile=profile,
        candidate_name=selection.selected.candidate.name,
        final_tree_count=final_tree_count(selection.selected),
        weighted_auc=float(
            roc_auc_score(
                oof["label"],
                oof["oof_score"],
                sample_weight=np.abs(oof["physical_weight"].to_numpy(dtype=float)),
            )
        ),
        score_mass_correlation=weighted_pearson(
            zz["oof_score"], zz["m4l"], zz["physical_weight"]
        ),
        working_points=points,
        signal_efficiencies={
            name: float(point["signal_efficiency"]) for name, point in points.items()
        },
        target_background_efficiencies={
            name: float(point["target_background_efficiency"])
            for name, point in points.items()
        },
        zz_ks_distances=distances,
        selection=selection,
        oof_scores=oof,
    )
    return replace(result, eligibility_reasons=_eligibility_reasons(result, 0.80, 0.10))


def select_eligible_profile(
    results, *, auc_floor: float = 0.80, ks_limit: float = 0.10
) -> ProfileResult | None:
    """Select the highest-AUC eligible OOF profile using deterministic ties."""
    normalized = tuple(results)
    _validate_limits(auc_floor, ks_limit)
    eligible = [
        result for result in normalized
        if not _eligibility_reasons(result, float(auc_floor), float(ks_limit))
    ]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda value: (
            -float(value.weighted_auc),
            _maximum_ks(value),
            value.profile.name,
        ),
    )
def _make_select_and_score_test(canonical_profiles):
    def select_and_score_test(
        frame: pd.DataFrame,
        policy,
        *,
        model_factory=None,
    ) -> AblationOutcome:
        """Evaluate canonical profiles, then open test only for the fixed selection."""
        development_results = {
            name: evaluate_development_profile(frame, policy, profile, model_factory=model_factory)
            for name, profile in canonical_profiles
        }
        result = select_eligible_profile(development_results.values())
        if result is None:
            return AblationOutcome(_snapshot_results(development_results), None, None)
        if result.selection is None:
            raise ValueError("selected profile is missing development model selection")
        validate_mc_frame(frame)
        test = frame.loc[frame["split"] == "test"]
        if test.empty:
            raise ValueError("independent test split must not be empty")
        model = fit_final_model(
            frame, result.selection, policy, model_factory, features=result.profile.features
        )
        scores = score_model(model, test, features=result.profile.features)
        test_scores = test.loc[:, ["label", "physical_weight", "m4l"]].copy()
        test_scores["score"] = scores
        diagnostics = zz_mass_diagnostics(test_scores, "score", result.working_points, policy)
        evidence = SelectedProfileEvidence(
            profile=result.profile,
            model=model,
            test_scores=test_scores,
            test_weighted_auc=float(
                roc_auc_score(
                    test_scores["label"],
                    test_scores["score"],
                    sample_weight=np.abs(test_scores["physical_weight"].to_numpy(dtype=float)),
                )
            ),
            test_zz_diagnostics=diagnostics,
            working_points=result.working_points,
        )
        snapshots = _snapshot_results(development_results)
        return AblationOutcome(
            snapshots,
            snapshots[result.profile.name],
            _snapshot_evidence(evidence),
        )

    return select_and_score_test


select_and_score_test = _make_select_and_score_test(tuple(ABLATION_PROFILES.items()))
del _make_select_and_score_test


def _snapshot_results(results: Mapping[str, ProfileResult]) -> Mapping[str, ProfileResult]:
    return MappingProxyType({
        name: replace(
            result,
            working_points=_freeze_value(result.working_points),
            signal_efficiencies=_freeze_value(result.signal_efficiencies),
            target_background_efficiencies=_freeze_value(result.target_background_efficiencies),
            zz_ks_distances=_freeze_value(result.zz_ks_distances),
            selection=None,
            oof_scores=None if result.oof_scores is None else result.oof_scores.copy(deep=True),
        )
        for name, result in results.items()
    })


def _snapshot_evidence(evidence: SelectedProfileEvidence) -> SelectedProfileEvidence:
    return replace(
        evidence,
        test_scores=evidence.test_scores.copy(deep=True),
        test_zz_diagnostics=_freeze_value(evidence.test_zz_diagnostics),
        working_points=_freeze_value(evidence.working_points),
    )


def _freeze_value(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def _oof_frame(frame: pd.DataFrame, selection: ModelSelectionResult) -> pd.DataFrame:
    output = frame.loc[selection.oof_scores.index, ["label", "physical_weight", "m4l"]].copy()
    output["oof_score"] = selection.oof_scores.loc[output.index].to_numpy(dtype=float)
    return output


def _validate_profile(profile: FeatureProfile) -> None:
    if not isinstance(profile, FeatureProfile):
        raise ValueError("profile must be a FeatureProfile")
    validate_model_features(profile.features)


def _validate_limits(auc_floor: float, ks_limit: float) -> None:
    for value, name in ((auc_floor, "auc_floor"), (ks_limit, "ks_limit")):
        if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
            raise ValueError(f"{name} must be finite")
        if not np.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")
    if not 0.0 <= float(auc_floor) <= 1.0 or not 0.0 <= float(ks_limit) <= 1.0:
        raise ValueError("eligibility limits must be between zero and one")


def _maximum_ks(result: ProfileResult) -> float:
    values = tuple(float(value) for value in result.zz_ks_distances.values())
    return max(values) if values else float("inf")


def _eligibility_reasons(
    result: ProfileResult, auc_floor: float, ks_limit: float
) -> tuple[str, ...]:
    if not isinstance(result, ProfileResult):
        raise ValueError("profile result must be a ProfileResult")
    _validate_limits(auc_floor, ks_limit)
    reasons: list[str] = []
    working_point_keysets = (
        result.working_points,
        result.signal_efficiencies,
        result.target_background_efficiencies,
        result.zz_ks_distances,
    )
    if any(set(values) != _WORKING_POINT_NAMES for values in working_point_keysets):
        reasons.append("working_point_keyset_mismatch")
    if not np.isfinite(float(result.weighted_auc)) or result.weighted_auc < auc_floor:
        reasons.append("weighted_auc_below_floor")
    if not result.zz_ks_distances or any(
        not np.isfinite(float(value)) or float(value) > ks_limit
        for value in result.zz_ks_distances.values()
    ):
        reasons.append("zz_mass_ks_exceeds_limit")
    for name, target in result.target_background_efficiencies.items():
        efficiency = result.signal_efficiencies.get(name)
        if efficiency is None or not np.isfinite(float(efficiency)) or float(efficiency) <= float(target):
            reasons.append(f"signal_efficiency_not_above_{name}")
    return tuple(reasons)
