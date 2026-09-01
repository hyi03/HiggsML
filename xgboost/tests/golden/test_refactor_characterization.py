from __future__ import annotations

import hashlib
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from src.angular5 import ANGULAR5_FEATURES, build_angular5
from src.config import load_preprocessing_protocol
from src.experiment_config import ANGULAR19_PROFILE, ExperimentOverrides, load_experiment_config
from src.experiment_runner import _final_tree_count, train_experiment
from src.features import FEATURES, FORBIDDEN_FEATURES, build_event_features
from src.full_training_evaluation import build_working_points
from src.full_training_policy import (
    assign_development_folds,
    class_balanced_training_weights,
)
from src.mass_bin_reweighting import _eligibility_reasons
from src.reconstruction import normalize_leptons, reconstruct_candidate
from src.selection import CutflowAccumulator, SelectionConfig, select_event
from src.split import event_split
from src.validation import _auc_metrics, weighted_ks_distance


EXPECTED_BASE14 = (
    "lep1_pt", "lep2_pt", "lep3_pt", "lep4_pt",
    "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta",
    "mZ1", "mZ2", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
)
EXPECTED_ANGULAR5 = (
    "cos_theta_star", "cos_theta_1", "cos_theta_2",
    "phi_decay_planes", "phi_production_plane",
)
RTOL = 1e-12
ATOL = 1e-12


def _passing_event() -> dict[str, object]:
    return {
        "lep_n": 4,
        "lep_pt": [45.0, 45.0, 15.0, 15.0],
        "lep_eta": [0.0, 0.0, 0.0, 0.0],
        "lep_phi": [0.0, math.pi, math.pi / 2, -math.pi / 2],
        "lep_e": [45.0, 45.0, 15.0, 15.0],
        "lep_charge": [1, -1, 1, -1],
        "lep_type": [11, 11, 13, 13],
        "trigE": True,
        "trigM": False,
        "lep_isTrigMatched": [True] * 4,
        "lep_isTightID": [True] * 4,
        "lep_track_iso": [0.1] * 4,
        "lep_calo_iso": [0.1] * 4,
        "lep_d0sig": [0.1] * 4,
        "lep_z0": [0.1] * 4,
        "eventNumber": 7,
        "runNumber": 1,
        "channelNumber": 345060,
    }


def test_angular19_and_forbidden_feature_contract_is_frozen() -> None:
    assert tuple(FEATURES) == EXPECTED_BASE14
    assert ANGULAR5_FEATURES == EXPECTED_ANGULAR5
    assert ANGULAR19_PROFILE == EXPECTED_BASE14 + EXPECTED_ANGULAR5
    assert len(ANGULAR19_PROFILE) == 19
    assert not (set(ANGULAR19_PROFILE) & FORBIDDEN_FEATURES)


def test_default_training_authority_is_frozen() -> None:
    config = load_experiment_config("config/experiment_training.yaml")
    assert config.grid == {
        "learning_rate": (0.05,),
        "max_depth": (3,),
        "min_child_weight": (5.0,),
        "subsample": (0.8,),
        "colsample_bytree": (0.8,),
        "reg_alpha": (0.1,),
        "reg_lambda": (2.0,),
    }
    assert (config.n_estimators, config.early_stopping_rounds) == (1000, 50)
    assert (config.random_seed, config.n_jobs, config.tree_method, config.folds) == (
        42, 1, "hist", 5
    )
    assert config.working_points == {"loose": 0.5, "medium": 0.2, "tight": 0.1}


def test_selection_reconstruction_features_and_cutflow_are_frozen() -> None:
    protocol = load_preprocessing_protocol("config/preprocessing_protocol_v1.yaml")
    config = SelectionConfig.from_mapping(protocol.raw["selection"])
    event = _passing_event()
    result = select_event(event, config, "GeV")
    assert result.accepted is True
    assert result.failed_stage is None
    assert result.passed_stages == (
        "trigger",
        "allowed_lepton_types",
        "tight_identification",
        "track_isolation",
        "calorimeter_isolation",
        "transverse_impact_parameter",
        "longitudinal_impact_parameter",
        "exactly_four_good_leptons",
        "trigger_match",
        "lepton_pt",
        "lepton_eta",
        "zero_charge",
        "valid_sfos_pairing",
        "all_sfos_mass",
        "z1_mass_window",
        "z2_mass_window",
        "m4l_analysis_window",
        "selected",
    )
    accumulator = CutflowAccumulator(
        sample_name="higgs", is_data=False, stages=("read", *result.passed_stages)
    )
    accumulator.record_read(2.0)
    accumulator.record_selection(result, 2.0)
    cutflow = accumulator.to_dict()
    assert tuple(cutflow["stages"]) == ("read", *result.passed_stages)
    assert all(stage["count"] == 1 for stage in cutflow["stages"].values())
    assert all(
        stage["signed_weighted_yield"] == 2.0
        and stage["absolute_weighted_yield"] == 2.0
        for stage in cutflow["stages"].values()
    )

    features = build_event_features(event, "GeV")
    assert features == {
        "lep1_pt": 45.0,
        "lep2_pt": 45.0,
        "lep3_pt": 15.0,
        "lep4_pt": 15.0,
        "lep1_eta": 0.0,
        "lep2_eta": 0.0,
        "lep3_eta": 0.0,
        "lep4_eta": 0.0,
        "mZ1": 90.0,
        "mZ2": 30.0,
        "m4l": 120.0,
        "pt4l": 5.809009821810581e-15,
        "deltaR_Z1": math.pi,
        "deltaR_Z2": math.pi,
        "deltaPhi_ZZ": math.pi / 2,
        "eventNumber": 7,
        "runNumber": 1,
        "channelNumber": 345060,
    }
    candidate = reconstruct_candidate(normalize_leptons(event, "GeV"))
    assert candidate is not None
    assert candidate.pairing.z1_indices == (0, 1)
    assert candidate.pairing.z2_indices == (2, 3)
    assert (candidate.z1.mass, candidate.z2.mass, candidate.four_lepton.mass) == (
        90.0,
        30.0,
        120.0,
    )
    assert build_angular5(candidate) == {
        "cos_theta_star": -2.1648901405887326e-17,
        "cos_theta_1": 0.7071067811865476,
        "cos_theta_2": 0.7071067811865475,
        "phi_decay_planes": -math.pi,
        "phi_production_plane": -math.pi / 2,
    }


def test_canonical_identity_split_and_fold_values_are_frozen() -> None:
    assert event_split(0, 345060) == "train"
    assert event_split(10, 345060) == "validation"
    assert event_split(21, 345060) == "test"


def test_weight_fold_and_final_tree_rules_are_frozen() -> None:
    frame = pd.DataFrame(
        {
            "channelNumber": [345060, 345060, 363490, 363490],
            "eventNumber": [1, 2, 3, 4],
            "split": ["train", "validation", "train", "validation"],
            "label": [1, 1, 0, 0],
            "physical_weight": [-2.0, 1.0, 4.0, -2.0],
        }
    )
    for name in EXPECTED_BASE14:
        frame[name] = 0.0
    frame["m4l"] = 125.0
    weights = class_balanced_training_weights(frame)
    np.testing.assert_array_equal(weights, np.array([4 / 3, 2 / 3, 4 / 3, 2 / 3]))
    rows: list[dict[str, object]] = []
    found = {0: set(), 1: set()}
    event_number = 1
    while any(len(values) < 5 for values in found.values()):
        channel_number = 345060 if event_number % 2 else 363490
        payload = f"task4b-fold:{channel_number}:{event_number}".encode()
        fold = int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big") % 5
        label = event_number % 2
        if fold not in found[label]:
            found[label].add(fold)
            rows.append(
                {
                    **{feature: float(event_number) for feature in EXPECTED_BASE14},
                    "m4l": 125.0,
                    "eventNumber": event_number,
                    "channelNumber": channel_number,
                    "split": "train" if event_number % 3 else "validation",
                    "label": label,
                    "physical_weight": -1.0 if label else 1.0,
                }
            )
        event_number += 1
    fold_frame = pd.DataFrame(rows)
    folds = assign_development_folds(fold_frame, folds=5)
    expected_folds = [
        int.from_bytes(
            hashlib.blake2b(
                f"task4b-fold:{int(channel)}:{int(event)}".encode(), digest_size=8
            ).digest(),
            "big",
        )
        % 5
        for channel, event in zip(
            fold_frame["channelNumber"], fold_frame["eventNumber"], strict=True
        )
    ]
    assert folds.tolist() == expected_folds
    result = SimpleNamespace(
        folds=tuple(SimpleNamespace(best_iteration=value) for value in (2, 4, 8, 10, 12))
    )
    assert _final_tree_count(result) == 9


def test_working_points_metrics_ks_and_qualification_are_frozen() -> None:
    frame = pd.DataFrame(
        {
            "label": [0, 0, 0, 0, 1, 1, 1, 1],
            "oof_score": [0.9, 0.7, 0.4, 0.1, 0.95, 0.8, 0.6, 0.2],
            "physical_weight": [1.0, -1.0, 1.0, -1.0, 1.0, 1.0, -1.0, -1.0],
        }
    )
    points = build_working_points(
        frame, {"loose": 0.5, "medium": 0.2, "tight": 0.1}
    )
    assert {
        name: (
            value["threshold"],
            value["achieved_background_efficiency"],
            value["signal_efficiency"],
        )
        for name, value in points.items()
    } == {
        "loose": (0.7, 0.5, 0.5),
        "medium": (0.9, 0.25, 0.25),
        "tight": (0.9, 0.25, 0.25),
    }
    scored = frame.rename(columns={"oof_score": "xgb_score"})
    scored["split"] = "validation"
    assert _auc_metrics(scored, "validation") == (0.625, 0.625)
    assert weighted_ks_distance([1.0, 2.0], [1.0, 2.0], [1.0, -1.0], [2.0, -2.0]) == 0.0
    policy = SimpleNamespace(auc_floor=0.8, ks_limit=0.1)
    assert _eligibility_reasons(
        weighted_auc=0.8,
        zz_ks_distances={"loose": 0.1, "medium": 0.1, "tight": 0.1},
        signal_efficiencies={"loose": 0.6, "medium": 0.3, "tight": 0.2},
        achieved_zz_efficiencies={"loose": 0.5, "medium": 0.2, "tight": 0.1},
        policy=policy,
    ) == ()
    assert _eligibility_reasons(
        weighted_auc=0.79,
        zz_ks_distances={"loose": 0.11, "medium": 0.1, "tight": None},
        signal_efficiencies={"loose": 0.5, "medium": 0.2, "tight": 0.1},
        achieved_zz_efficiencies={"loose": 0.5, "medium": 0.2, "tight": 0.1},
        policy=policy,
    ) == (
        "weighted_auc_below_floor",
        "loose_zz_ks_above_limit",
        "tight_zz_ks_unavailable",
        "loose_signal_efficiency_not_strictly_greater",
        "medium_signal_efficiency_not_strictly_greater",
        "tight_signal_efficiency_not_strictly_greater",
    )


class _DeterministicClassifier:
    def __init__(self, records: list[tuple[int, ...]], **parameters: object) -> None:
        self.records = records
        self.parameters = parameters
        self.best_iteration = 2

    def fit(self, x, y, **kwargs):
        self.records.append(tuple(x.index))
        return self

    def predict_proba(self, x):
        score = np.where(x.iloc[:, 0].to_numpy(dtype=float) > 5.0, 0.9, 0.1)
        return np.column_stack([1.0 - score, score])


def test_oof_coverage_candidate_selection_and_test_blinding_are_frozen() -> None:
    config = load_experiment_config(
        None,
        ExperimentOverrides(
            feature_profile="angular19",
            grid={"max_depth": (2, 3)},
            scalars={"n_estimators": 8, "early_stopping_rounds": 2},
        ),
    )
    rows: list[dict[str, object]] = []
    seen = {(fold, label): 0 for fold in range(5) for label in (0, 1)}
    event_number = 1
    while min(seen.values()) < 1:
        for label in (0, 1):
            channel = 345060 if label else 363490
            payload = f"task4b-fold:{channel}:{event_number}".encode()
            fold = int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big") % 5
            if seen[(fold, label)]:
                event_number += 1
                continue
            rows.append(
                {
                    **{
                        name: float(label * 10 + offset + event_number / 10000)
                        for offset, name in enumerate(ANGULAR19_PROFILE)
                    },
                    "m4l": 125.0,
                    "channelNumber": channel,
                    "eventNumber": event_number,
                    "split": "train" if fold % 2 == 0 else "validation",
                    "label": label,
                    "physical_weight": 1.0 + label,
                }
            )
            seen[(fold, label)] += 1
            event_number += 1
    for label in (0, 1):
        rows.append(
            {
                **{
                    name: float(label * 10 + offset)
                    for offset, name in enumerate(ANGULAR19_PROFILE)
                },
                "m4l": 125.0,
                "channelNumber": 345060 if label else 363490,
                "eventNumber": event_number,
                "split": "test",
                "label": label,
                "physical_weight": 1.0,
            }
        )
        event_number += 1
    frame = pd.DataFrame(rows)
    records: list[tuple[int, ...]] = []
    outcome = train_experiment(
        frame,
        config,
        model_factory=lambda **parameters: _DeterministicClassifier(records, **parameters),
    )
    development = frame.loc[frame["split"] != "test"]
    test_indices = set(frame.index[frame["split"] == "test"])
    assert outcome.selected.index == 0
    assert len(outcome.candidates) == 2
    assert outcome.metrics["test_opened"] is False
    assert outcome.oof_frame.index.tolist() == development.index.tolist()
    assert outcome.oof_frame["oof_score"].tolist() == [
        0.9 if label == 1 else 0.1 for label in development["label"]
    ]
    assert all(not (set(indices) & test_indices) for indices in records)


def test_xgboost_save_load_prediction_round_trip_is_frozen(tmp_path: Path) -> None:
    base = np.arange(20, dtype=float)
    features = pd.DataFrame(
        {
            name: base * (index + 1) / 100.0
            for index, name in enumerate(ANGULAR19_PROFILE)
        }
    )
    labels = np.array([0] * 10 + [1] * 10)
    model = XGBClassifier(
        n_estimators=5,
        max_depth=2,
        learning_rate=0.1,
        min_child_weight=1,
        subsample=1.0,
        colsample_bytree=1.0,
        reg_alpha=0.0,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=1,
        tree_method="hist",
        eval_metric="logloss",
    )
    model.fit(features, labels, verbose=False)
    predictions = model.predict_proba(features)[:, 1]
    expected = np.array(
        [0.34737616777420044] * 10 + [0.6526238322257996] * 10
    )
    np.testing.assert_allclose(predictions, expected, rtol=RTOL, atol=ATOL)
    model_path = tmp_path / "model.json"
    model.save_model(model_path)
    loaded = XGBClassifier()
    loaded.load_model(model_path)
    np.testing.assert_allclose(
        loaded.predict_proba(features)[:, 1], predictions, rtol=RTOL, atol=ATOL
    )
