from __future__ import annotations

import hashlib
import inspect
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

import src.mass_sculpting_ablation as ablation
from src.features import FEATURES, FORBIDDEN_FEATURES
from src.full_training_policy import development_fold, load_training_policy
from src.mass_sculpting_ablation import (
    ABLATION_PROFILES,
    FeatureProfile,
    ProfileResult,
    evaluate_development_profile,
    select_and_score_test,
    select_eligible_profile,
)


def _literal_result(
    name: str,
    *,
    auc: float = 0.81,
    ks: float = 0.05,
    signal: float = 0.8,
    target: float = 0.5,
) -> ProfileResult:
    return ProfileResult(
        profile=FeatureProfile(name, ("lep1_eta",)),
        candidate_name="depth2_child20",
        final_tree_count=3,
        weighted_auc=auc,
        score_mass_correlation=0.0,
        working_points={
            "loose": {"threshold": 0.5},
            "medium": {"threshold": 0.6},
            "tight": {"threshold": 0.7},
        },
        signal_efficiencies={"loose": signal, "medium": signal, "tight": signal},
        target_background_efficiencies={"loose": target, "medium": target, "tight": target},
        zz_ks_distances={"loose": ks, "medium": ks, "tight": ks},
    )


def test_ablation_profiles_are_exact_safe_feature_tuples():
    """Changing a profile to a mass proxy or different ordered tuple must fail."""
    assert ABLATION_PROFILES["drop_top4_mass_proxies"].features == (
        "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
        "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
    )
    assert ABLATION_PROFILES["shape8"].features == (
        "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta", "pt4l",
        "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
    )
    assert ABLATION_PROFILES["angular_eta7"].features == (
        "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta", "deltaR_Z1",
        "deltaR_Z2", "deltaPhi_ZZ",
    )
    for profile in ABLATION_PROFILES.values():
        assert profile.features
        assert len(profile.features) == len(set(profile.features))
        assert set(profile.features) <= set(FEATURES)
        assert "m4l" not in profile.features
        assert not set(profile.features) & FORBIDDEN_FEATURES


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (_literal_result("ks_at_limit", ks=0.1000), "ks_at_limit"),
        (_literal_result("ks_above_limit", ks=0.1001), None),
        (_literal_result("auc_at_floor", auc=0.8000), "auc_at_floor"),
        (_literal_result("auc_below_floor", auc=0.7999), None),
        (_literal_result("signal_equal_target", signal=0.5), None),
    ],
)
def test_eligibility_uses_literal_strict_boundaries(result, expected):
    """Changing <= KS, < AUC, or <= signal logic must fail this table."""
    selected = select_eligible_profile([result], auc_floor=0.80, ks_limit=0.10)

    if expected is None:
        assert selected is None
    else:
        assert selected is not None
        assert selected.profile.name == expected


def test_eligible_profile_prefers_auc_then_smaller_ks_then_name():
    """Dropping a deterministic tie-break would make study selection unstable."""
    highest_auc = _literal_result("highest", auc=0.83, ks=0.09)
    assert select_eligible_profile(
        [_literal_result("lower", auc=0.82), highest_auc]
    ) is highest_auc

    smaller_ks = _literal_result("zeta", auc=0.82, ks=0.03)
    larger_ks = _literal_result("alpha", auc=0.82, ks=0.04)
    assert select_eligible_profile([larger_ks, smaller_ks]) is smaller_ks

    alpha = _literal_result("alpha", auc=0.82, ks=0.03)
    assert select_eligible_profile([smaller_ks, alpha]) is alpha


def test_eligibility_returns_none_when_every_profile_fails_a_gate():
    """Selecting a failed profile would open independent test data unlawfully."""
    assert select_eligible_profile([
        _literal_result("low_auc", auc=0.79),
        _literal_result("high_ks", ks=0.11),
        _literal_result("low_signal", signal=0.49),
    ]) is None


@pytest.mark.parametrize(
    "malformed",
    [
        lambda result: replace(
            result, working_points={"loose": {"threshold": 0.5}, "medium": {}}
        ),
        lambda result: replace(result, signal_efficiencies={"loose": 0.8, "medium": 0.8}),
        lambda result: replace(
            result,
            target_background_efficiencies={
                "loose": 0.5, "medium": 0.5, "tight": 0.5, "extra": 0.5,
            },
        ),
        lambda result: replace(result, zz_ks_distances={"loose": 0.05, "medium": 0.05}),
    ],
)
def test_eligibility_rejects_noncanonical_working_point_keysets(malformed):
    """Dropping exact loose/medium/tight agreement could select incomplete evidence."""
    assert select_eligible_profile([malformed(_literal_result("candidate"))]) is None


def _sealed_frame() -> pd.DataFrame:
    rows = []
    covered = {0: set(), 1: set()}
    event = 1
    while any(len(folds) < 5 for folds in covered.values()):
        label = event % 2
        channel = 345060 if label else 363490
        fold = development_fold(channel, event)
        if fold not in covered[label]:
            covered[label].add(fold)
            rows.append({
                **{feature: 0.9 if label else 0.1 for feature in FEATURES},
                "m4l": 106.0 + 5.0 * fold,
                "eventNumber": event,
                "channelNumber": channel,
                "split": "train" if event % 3 else "validation",
                "label": label,
                "physical_weight": 1.0,
            })
        event += 1
    for label in (0, 1):
        rows.append({
            **{feature: 0.99 if label else 0.01 for feature in FEATURES},
            "m4l": 999.0,
            "eventNumber": event,
            "channelNumber": 345060 if label else 363490,
            "split": "test",
            "label": label,
            "physical_weight": 1.0,
        })
        event += 1
    return pd.DataFrame(rows)


class _RecordingModel:
    def __init__(self, split_by_index: dict[int, str], records: list[set[str]]) -> None:
        self._splits = split_by_index
        self._records = records
        self.best_iteration = 2

    def fit(self, x, y, *, sample_weight, eval_set=None, sample_weight_eval_set=None, verbose=None):
        self._records.append({self._splits[index] for index in x.index})
        if eval_set is not None:
            self._records.append({self._splits[index] for index in eval_set[0][0].index})
        return self

    def predict_proba(self, x):
        self._records.append({self._splits[index] for index in x.index})
        score = x.iloc[:, 0].to_numpy(dtype=float)
        return np.column_stack([1.0 - score, score])


def _profile_result(profile: FeatureProfile, **kwargs) -> ProfileResult:
    return replace(_literal_result(profile.name, **kwargs), profile=profile)


def _no_eligible_profile_mapping() -> dict[str, ProfileResult]:
    return {
        name: _profile_result(profile, auc=0.79)
        for name, profile in ABLATION_PROFILES.items()
    }


def test_test_opening_has_only_fixed_internal_selection_api():
    """Reintroducing caller-supplied selection or tuning knobs would break the seal."""
    signature = inspect.signature(select_and_score_test)
    assert tuple(signature.parameters) == ("frame", "policy", "model_factory")
    assert signature.parameters["model_factory"].kind is inspect.Parameter.KEYWORD_ONLY
    assert not hasattr(ablation, "fit_and_score_selected")
    assert not hasattr(ablation, "SelectedProfile")
    assert not hasattr(ablation, "_SelectionCertificate")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"auc_floor": 0.0},
        {"ks_limit": 1.0},
        {"results_by_profile": _no_eligible_profile_mapping()},
    ],
)
def test_test_opening_rejects_tuning_or_borrowed_results_before_factory_access(kwargs):
    """Allowing threshold tuning or borrowed selections reopens test-selection control."""
    frame = _sealed_frame()
    policy = load_training_policy("config/full_training.yaml")
    records: list[set[str]] = []
    factory = lambda **_: _RecordingModel(frame["split"].to_dict(), records)

    with pytest.raises(TypeError):
        select_and_score_test(
            frame,
            policy,
            _no_eligible_profile_mapping(),
            model_factory=factory,
            **kwargs,
        )
    assert not records


def _unselectable_frame() -> pd.DataFrame:
    frame = _sealed_frame()
    for feature in FEATURES:
        frame[feature] = 0.5
    return frame


def test_test_opening_returns_all_results_and_skips_test_when_none_eligible():
    """Touching test after internally finding no eligible profile would be a bug."""
    frame = _unselectable_frame()
    policy = load_training_policy("config/full_training.yaml")
    records: list[set[str]] = []
    factory = lambda **_: _RecordingModel(frame["split"].to_dict(), records)

    outcome = select_and_score_test(frame, policy, model_factory=factory)
    assert tuple(outcome.development_results) == tuple(ABLATION_PROFILES)
    assert outcome.selected is None
    assert outcome.evidence is None
    assert records
    assert all("test" not in splits for splits in records)


def test_tiny_real_xgboost_integration_keeps_test_closed_when_auc_fails():
    """The real classifier stack must honor the same no-eligible terminal branch."""
    outcome = select_and_score_test(
        _sealed_frame(), load_training_policy("config/full_training.yaml")
    )
    assert tuple(outcome.development_results) == tuple(ABLATION_PROFILES)
    assert all(
        np.isfinite(result.weighted_auc)
        for result in outcome.development_results.values()
    )
    assert outcome.selected is None
    assert outcome.evidence is None


def test_no_eligible_selection_ignores_poisoned_test_analysis_values():
    """Test-only feature/mass/weight poison must not affect development selection."""
    frame = _unselectable_frame()
    test_rows = frame["split"] == "test"
    frame.loc[test_rows, [*FEATURES, "m4l", "physical_weight"]] = np.nan
    policy = load_training_policy("config/full_training.yaml")
    records: list[set[str]] = []
    factory = lambda **_: _RecordingModel(frame["split"].to_dict(), records)

    outcome = select_and_score_test(frame, policy, model_factory=factory)

    assert outcome.selected is None
    assert outcome.evidence is None
    assert records
    assert all("test" not in splits for splits in records)


def test_test_opening_evaluates_canonical_profiles_then_scores_one_selected_once():
    """Internal selection must evaluate all profiles before exactly one test prediction."""
    frame = _sealed_frame()
    policy = load_training_policy("config/full_training.yaml")
    records: list[set[str]] = []
    factory = lambda **_: _RecordingModel(frame["split"].to_dict(), records)

    outcome = select_and_score_test(frame, policy, model_factory=factory)

    assert tuple(outcome.development_results) == tuple(ABLATION_PROFILES)
    assert tuple(result.profile for result in outcome.development_results.values()) == tuple(
        ABLATION_PROFILES.values()
    )
    assert outcome.selected is not None
    assert outcome.evidence is not None
    assert len(outcome.evidence.test_scores) == 2
    assert records.count({"test"}) == 1
    assert all(splits == {"test"} for splits in records if "test" in splits)


@pytest.mark.parametrize(
    "replacement",
    [
        lambda canonical: {"only_one": canonical[0][1]},
        lambda canonical: {
            name: FeatureProfile(name, tuple(reversed(profile.features)))
            for name, profile in canonical
        },
    ],
)
def test_test_opening_uses_definition_time_canonical_profiles_not_public_global(
    monkeypatch, replacement,
):
    """Monkeypatching the public profile mapping must not change the sealed study."""
    canonical = tuple(ABLATION_PROFILES.items())
    seen: list[FeatureProfile] = []

    def fake_evaluate(frame, policy, profile, *, model_factory=None):
        seen.append(profile)
        return _profile_result(profile, auc=0.79)

    monkeypatch.setattr(ablation, "evaluate_development_profile", fake_evaluate)
    monkeypatch.setattr(ablation, "ABLATION_PROFILES", replacement(canonical))

    outcome = select_and_score_test(object(), object())

    assert seen == [profile for _, profile in canonical]
    assert tuple(outcome.development_results) == tuple(name for name, _ in canonical)
    assert outcome.selected is None
    assert outcome.evidence is None


def test_outcome_deep_snapshots_development_maps_and_oof_frame(monkeypatch):
    """Mutating an evaluator-owned result after return must not rewrite outcome evidence."""
    created: dict[str, ProfileResult] = {}

    def fake_evaluate(frame, policy, profile, *, model_factory=None):
        result = replace(
            _profile_result(profile, auc=0.79),
            oof_scores=pd.DataFrame({"oof_score": [0.25]}),
        )
        created[profile.name] = result
        return result

    monkeypatch.setattr(ablation, "evaluate_development_profile", fake_evaluate)

    outcome = select_and_score_test(object(), object())
    created["shape8"].working_points["loose"]["threshold"] = 99.0
    created["shape8"].oof_scores.loc[0, "oof_score"] = 99.0

    snapshot = outcome.development_results["shape8"]
    assert snapshot.working_points["loose"]["threshold"] == 0.5
    assert snapshot.oof_scores.loc[0, "oof_score"] == 0.25
