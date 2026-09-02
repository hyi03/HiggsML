from __future__ import annotations

from dataclasses import replace
from math import cosh, pi
from pathlib import Path

import numpy as np
import pytest

from src.domain import selection as selection_module
from src.domain.angular5 import boost, build_angular5
from src.domain.features import build_candidate_features
from src.domain.four_vectors import FourVector, delta_phi
from src.domain.reconstruction import Lepton, normalize_leptons, pair_four_leptons, reconstruct_candidate
from src.domain.selection import SelectionConfig, select_event
from src.domain.splitting import event_split
from src.domain.weights import physical_event_weight, training_weights
from src.config import InputBindingError, load_preprocess_protocol


PROJECT = Path(__file__).resolve().parents[2]


def _selection_config() -> SelectionConfig:
    protocol = load_preprocess_protocol(PROJECT / "config/preprocess_protocol_v1.yaml")
    return SelectionConfig.from_mapping(protocol.selection)


def _event() -> dict:
    pt = [40.0, 35.0, 30.0, 25.0]
    eta = [0.2, -0.2, 0.4, -0.4]
    return {
        "lep_n": 4,
        "lep_pt": pt,
        "lep_eta": eta,
        "lep_phi": [0.0, pi, 1.1, 1.1 + pi],
        "lep_e": [p * cosh(e) for p, e in zip(pt, eta)],
        "lep_charge": [-1, 1, -1, 1],
        "lep_type": [11, 11, 13, 13],
        "trigE": True,
        "trigM": False,
        "lep_isTrigMatched": [True, False, False, False],
        "lep_isTightID": [True] * 4,
        "lep_track_iso": [1.0] * 4,
        "lep_calo_iso": [1.0] * 4,
        "lep_d0sig": [1.0] * 4,
        "lep_z0": [0.1] * 4,
        "runNumber": 284500,
        "eventNumber": 123,
        "channelNumber": 345060,
    }


def test_four_vector_and_delta_phi_boundaries() -> None:
    vector = FourVector.from_pt_eta_phi_e(10.0, 0.0, 0.0, 10.0)
    assert vector.mass == 0.0
    assert delta_phi(pi, 0.0) == -pi


def test_normalization_is_stable_pt_descending() -> None:
    event = _event()
    event["lep_pt"] = [10.0, 20.0, 20.0, 5.0]
    event["lep_e"] = [10.0, 20.0, 20.0, 5.0]
    normalized = normalize_leptons(event, "GeV")

    assert normalized.pt.tolist() == [20.0, 20.0, 10.0, 5.0]
    assert normalized.charge.tolist() == [1, -1, -1, 1]


def test_selected_event_produces_finite_base14_and_angular5() -> None:
    event = _event()
    result = select_event(event, _selection_config(), "GeV")

    assert result.accepted
    assert result.candidate is not None
    base = build_candidate_features(event, result.candidate)
    angles = build_angular5(result.candidate)
    assert len(base) >= 14
    assert all(np.isfinite(list(angles.values())))
    assert all(-1.0 <= angles[name] <= 1.0 for name in tuple(angles)[:3])
    assert all(-pi <= angles[name] < pi for name in tuple(angles)[3:])


def test_selection_boundaries_are_fail_closed() -> None:
    event = _event()
    event["lep_track_iso"][0] = 0.3 * event["lep_pt"][0]

    result = select_event(event, _selection_config(), "GeV")

    assert not result.accepted
    assert result.failed_stage == "track_isolation"


@pytest.mark.parametrize(
    ("mutate", "stage"),
    [
        (lambda event: event.update(trigE=False), "trigger"),
        (lambda event: event["lep_type"].__setitem__(0, 15), "allowed_lepton_types"),
        (lambda event: event["lep_isTightID"].__setitem__(0, False), "tight_identification"),
        (lambda event: event["lep_calo_iso"].__setitem__(0, 0.3 * event["lep_pt"][0]), "calorimeter_isolation"),
        (lambda event: event["lep_d0sig"].__setitem__(0, 5.0), "transverse_impact_parameter"),
        (lambda event: event["lep_z0"].__setitem__(0, 0.5 * cosh(event["lep_eta"][0])), "longitudinal_impact_parameter"),
        (lambda event: event.update(lep_isTrigMatched=[False] * 4), "trigger_match"),
        (lambda event: event["lep_pt"].__setitem__(3, 6.999), "lepton_pt"),
        (lambda event: (event["lep_eta"].__setitem__(0, 2.47), event["lep_e"].__setitem__(0, event["lep_pt"][0] * cosh(2.47))), "lepton_eta"),
        (lambda event: event.update(lep_charge=[1, 1, -1, 1]), "zero_charge"),
        (lambda event: event.update(lep_charge=[1, 1, -1, -1]), "valid_sfos_pairing"),
    ],
)
def test_selection_stage_boundaries(mutate, stage: str) -> None:
    event = _event()
    mutate(event)

    result = select_event(event, _selection_config(), "GeV")

    assert not result.accepted
    assert result.failed_stage == stage


def test_exactly_four_good_leptons_rejects_five() -> None:
    event = _event()
    event["lep_n"] = 5
    for name in (
        "lep_pt", "lep_eta", "lep_phi", "lep_e", "lep_charge", "lep_type",
        "lep_isTrigMatched", "lep_isTightID", "lep_track_iso", "lep_calo_iso",
        "lep_d0sig", "lep_z0",
    ):
        event[name].append(event[name][-1])

    result = select_event(event, _selection_config(), "GeV")

    assert result.failed_stage == "exactly_four_good_leptons"


@pytest.mark.parametrize(
    ("change", "stage"),
    [
        (lambda candidate: replace(candidate, all_sfos_masses=(5.0,)), "all_sfos_mass"),
        (lambda candidate: replace(candidate, z1=FourVector(50.0, 0.0, 0.0, 0.0)), "z1_mass_window"),
        (lambda candidate: replace(candidate, z2=FourVector(12.0, 0.0, 0.0, 0.0)), "z2_mass_window"),
        (lambda candidate: replace(candidate, four_lepton=FourVector(160.0, 0.0, 0.0, 0.0)), "m4l_analysis_window"),
    ],
)
def test_reconstructed_mass_boundaries(
    monkeypatch: pytest.MonkeyPatch, change, stage: str
) -> None:
    event = _event()
    normalized = normalize_leptons(event, "GeV")
    candidate = reconstruct_candidate(normalized)
    assert candidate is not None
    monkeypatch.setattr(
        selection_module, "reconstruct_candidate", lambda _: change(candidate)
    )

    result = select_event(event, _selection_config(), "GeV")

    assert not result.accepted
    assert result.failed_stage == stage


@pytest.mark.parametrize(
    ("field", "value"),
    [("lep_pt", float("inf")), ("lep_eta", float("nan")), ("lep_d0sig", float("nan"))],
)
def test_non_finite_lepton_values_raise_input_binding(
    field: str, value: float
) -> None:
    event = _event()
    event[field][0] = value

    with pytest.raises(InputBindingError, match="finite"):
        select_event(event, _selection_config(), "GeV")


def test_lepton_array_shape_mismatch_raises_input_binding() -> None:
    event = _event()
    event["lep_pt"] = event["lep_pt"][:-1]

    with pytest.raises(InputBindingError, match="lep_n"):
        select_event(event, _selection_config(), "GeV")


def test_pairing_equal_distance_prefers_first_pair() -> None:
    leptons = (
        Lepton(FourVector(50.0, 50.0, 0.0, 0.0), -1, 11),
        Lepton(FourVector(50.0, -50.0, 0.0, 0.0), 1, 11),
        Lepton(FourVector(50.0, 0.0, 50.0, 0.0), -1, 13),
        Lepton(FourVector(50.0, 0.0, -50.0, 0.0), 1, 13),
    )

    pairing = pair_four_leptons(leptons)

    assert pairing.z1_indices == (0, 1)
    assert pairing.z2_indices == (2, 3)


def test_angular5_degenerate_boost_fails_closed() -> None:
    with pytest.raises(ValueError, match="Lorentz"):
        boost(FourVector(1.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0))


def test_weights_preserve_sign_and_normalize_absolute_mean() -> None:
    physical = physical_event_weight(
        mc_weight=-2.0,
        xsec_pb=1.0,
        k_factor=1.0,
        filter_efficiency=0.5,
        sum_of_weights=10.0,
        luminosity_pb=100.0,
    )
    assert physical == -10.0
    assert training_weights(np.array([-2.0, 1.0])).tolist() == pytest.approx(
        [4 / 3, 2 / 3]
    )


def test_split_matches_frozen_blake2b_contract() -> None:
    assert event_split(123, 345060) == "train"
    assert event_split(1001, 345060) == "test"
    assert event_split(1001, 363490) == "train"
