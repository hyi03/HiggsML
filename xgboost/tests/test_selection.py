import copy
import math
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from src.pairing import FourVector
from src.reconstruction import normalize_leptons, reconstruct_candidate
from src.selection import SELECTION_STAGES, SelectionConfig, select_event, z2_min_mass_gev


def selection_mapping(mode="fixed"):
    return {
        "require_exactly_four_leptons": True,
        "allowed_lepton_types": [11, 13],
        "lepton_pt_thresholds_gev": [20.0, 15.0, 10.0, 7.0],
        "electron_max_abs_eta": 2.47,
        "muon_max_abs_eta": 2.7,
        "require_zero_charge": True,
        "min_all_sfos_mass_gev": 5.0,
        "z1_mass_window_gev": [50.0, 106.0],
        "z2_mass": {
            "min_mode": mode,
            "fixed_min_gev": 12.0,
            "max_gev": 115.0,
            "sliding": {
                "low_m4l_gev": 140.0,
                "high_m4l_gev": 190.0,
                "low_min_gev": 12.0,
                "high_min_gev": 50.0,
            },
        },
        "m4l_window_gev": [105.0, 160.0],
    }


def passing_event():
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
        "lep_isTrigMatched": [True, True, True, True],
        "lep_isTightID": [True, True, True, True],
        "lep_track_iso": [0.1, 0.1, 0.1, 0.1],
        "lep_calo_iso": [0.1, 0.1, 0.1, 0.1],
        "lep_d0sig": [0.1, 0.1, 0.1, 0.1],
        "lep_z0": [0.1, 0.1, 0.1, 0.1],
        "eventNumber": 7,
        "runNumber": 1,
        "channelNumber": 42,
    }


def configured(mode="fixed"):
    return SelectionConfig.from_mapping(selection_mapping(mode))


def enhanced_mapping(mode="fixed"):
    mapping = selection_mapping(mode)
    mapping["lepton_quality"] = {
        "enabled": True,
        "require_event_trigger": True,
        "require_trigger_match": True,
        "require_tight_id": True,
        "track_isolation_max": 0.3,
        "calo_isolation_max": 0.3,
        "electron_d0sig_max": 5.0,
        "muon_d0sig_max": 3.0,
        "z0_sintheta_max_mm": 0.5,
    }
    return mapping


def enhanced_configured(mode="fixed"):
    return SelectionConfig.from_mapping(enhanced_mapping(mode))


def append_raw_lepton(event, *, good=True):
    values = {
        "lep_pt": 15.0,
        "lep_eta": 0.0,
        "lep_phi": 0.3,
        "lep_e": 15.0,
        "lep_charge": 1,
        "lep_type": 11,
        "lep_isTrigMatched": True,
        "lep_isTightID": True,
        "lep_track_iso": 0.1 if good else 4.5,
        "lep_calo_iso": 0.1,
        "lep_d0sig": 0.1,
        "lep_z0": 0.1,
    }
    event["lep_n"] += 1
    for field, value in values.items():
        event[field].append(value)
    return event


def assert_fails_at(event, stage, config=None):
    result = select_event(event, config or configured(), "GeV")
    assert not result.accepted
    assert result.failed_stage == stage
    return result


def test_parses_fixed_and_sliding_z2_modes():
    fixed = SelectionConfig.from_mapping(selection_mapping("fixed"))
    sliding = SelectionConfig.from_mapping(selection_mapping("sliding"))

    assert fixed.z2_min_mode == "fixed"
    assert sliding.z2_min_mode == "sliding"
    assert fixed.lepton_pt_thresholds_gev == (20.0, 15.0, 10.0, 7.0)


def test_legacy_selection_disables_quality_and_preserves_legacy_stages():
    config = configured()

    assert not config.lepton_quality.enabled
    assert config.stages == SELECTION_STAGES
    assert config.required_canonical_branches == ()


def test_parses_enhanced_lepton_quality_configuration():
    config = enhanced_configured()

    assert config.lepton_quality.enabled
    assert config.lepton_quality.track_isolation_max == 0.3
    assert config.required_canonical_branches == (
        "trigE",
        "trigM",
        "lep_isTrigMatched",
        "lep_isTightID",
        "lep_track_iso",
        "lep_calo_iso",
        "lep_d0sig",
        "lep_z0",
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        *[
            (
                lambda value, field=field: value["lepton_quality"].pop(field),
                field,
            )
            for field in (
                "enabled",
                "require_event_trigger",
                "require_trigger_match",
                "require_tight_id",
                "track_isolation_max",
                "calo_isolation_max",
                "electron_d0sig_max",
                "muon_d0sig_max",
                "z0_sintheta_max_mm",
            )
        ],
        *[
            (
                lambda value, field=field: value["lepton_quality"].update(
                    {field: True}
                ),
                field,
            )
            for field in (
                "track_isolation_max",
                "calo_isolation_max",
                "electron_d0sig_max",
                "muon_d0sig_max",
                "z0_sintheta_max_mm",
            )
        ],
        (lambda value: value["lepton_quality"].update(calo_isolation_max=math.inf), "calo_isolation_max"),
        (lambda value: value["lepton_quality"].update(electron_d0sig_max=0.0), "electron_d0sig_max"),
        (lambda value: value["lepton_quality"].update(muon_d0sig_max=-1.0), "muon_d0sig_max"),
        (lambda value: value["lepton_quality"].update(z0_sintheta_max_mm=math.nan), "z0_sintheta_max_mm"),
        (lambda value: value["lepton_quality"].update(track_isolation_max=1.0), "track_isolation_max"),
        (lambda value: value["lepton_quality"].update(calo_isolation_max=1.1), "calo_isolation_max"),
    ],
)
def test_rejects_invalid_enhanced_lepton_quality_configuration(mutate, message):
    mapping = enhanced_mapping()
    mutate(mapping)

    with pytest.raises((KeyError, TypeError, ValueError), match=message):
        SelectionConfig.from_mapping(mapping)


@pytest.mark.parametrize(
    ("m4l", "expected"),
    [(125.0, 12.0), (140.0, 12.0), (150.0, 19.6), (190.0, 50.0), (220.0, 50.0)],
)
def test_sliding_z2_threshold(m4l, expected):
    config = SelectionConfig.from_mapping(selection_mapping("sliding"))
    assert z2_min_mass_gev(m4l, config) == pytest.approx(expected)


def test_sliding_z2_threshold_is_continuous_at_breakpoints():
    config = SelectionConfig.from_mapping(selection_mapping("sliding"))
    epsilon = 1e-9

    assert z2_min_mass_gev(140.0 - epsilon, config) == pytest.approx(
        z2_min_mass_gev(140.0 + epsilon, config), abs=1e-8
    )
    assert z2_min_mass_gev(190.0 - epsilon, config) == pytest.approx(
        z2_min_mass_gev(190.0 + epsilon, config), abs=1e-8
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.pop("lepton_pt_thresholds_gev"), "lepton_pt_thresholds_gev"),
        (
            lambda value: value.update(require_exactly_four_leptons=False),
            "require_exactly_four_leptons",
        ),
        (
            lambda value: value.update(lepton_pt_thresholds_gev=[20, 10, 15, 7]),
            "descending",
        ),
        (lambda value: value.update(allowed_lepton_types=[11, 15]), "allowed_lepton_types"),
        (
            lambda value: value.update(z1_mass_window_gev=[106, 50]),
            "z1_mass_window_gev",
        ),
        (
            lambda value: value["z2_mass"].update(min_mode="unknown"),
            "min_mode",
        ),
        (
            lambda value: value["z2_mass"]["sliding"].update(
                high_m4l_gev=130.0
            ),
            "high_m4l_gev",
        ),
        (
            lambda value: value.update(electron_max_abs_eta=math.inf),
            "electron_max_abs_eta",
        ),
    ],
)
def test_rejects_invalid_selection_configuration(mutate, message):
    value = copy.deepcopy(selection_mapping())
    mutate(value)

    with pytest.raises((KeyError, TypeError, ValueError), match=message):
        SelectionConfig.from_mapping(value)


def test_accepts_baseline_four_lepton_event():
    result = select_event(passing_event(), configured(), "GeV")

    assert result.accepted
    assert result.failed_stage is None
    assert result.passed_stages[-1] == "selected"
    assert result.candidate is not None


def test_enhanced_selection_filters_a_bad_extra_raw_lepton_without_mutating_event():
    event = append_raw_lepton(passing_event(), good=False)
    original = copy.deepcopy(event)

    result = select_event(event, enhanced_configured(), "GeV")

    assert result.accepted
    assert event == original


def test_enhanced_selection_requires_exactly_four_good_leptons():
    assert_fails_at(
        append_raw_lepton(passing_event(), good=True),
        "exactly_four_good_leptons",
        enhanced_configured(),
    )


def test_enhanced_selection_requires_an_event_trigger():
    event = passing_event()
    event["trigE"] = False
    event["trigM"] = False

    assert_fails_at(event, "trigger", enhanced_configured())


def test_enhanced_selection_requires_a_matched_final_lepton():
    event = passing_event()
    event["lep_isTrigMatched"] = [False] * 4

    assert_fails_at(event, "trigger_match", enhanced_configured())


@pytest.mark.parametrize(
    ("field", "index", "limit", "stage"),
    [
        ("lep_track_iso", 0, 0.3 * 45.0, "track_isolation"),
        ("lep_calo_iso", 0, 0.3 * 45.0, "calorimeter_isolation"),
        ("lep_d0sig", 0, 5.0, "transverse_impact_parameter"),
        ("lep_d0sig", 2, 3.0, "transverse_impact_parameter"),
        ("lep_z0", 0, 0.5, "longitudinal_impact_parameter"),
    ],
)
def test_enhanced_quality_limits_are_strict(field, index, limit, stage):
    event = passing_event()
    event[field][index] = limit - 1e-6
    assert select_event(event, enhanced_configured(), "GeV").accepted

    event[field][index] = limit
    assert_fails_at(event, stage, enhanced_configured())


@pytest.mark.parametrize(
    ("field", "index", "value", "stage"),
    [
        ("lep_track_iso", 0, math.nan, "track_isolation"),
        ("lep_calo_iso", 0, math.inf, "calorimeter_isolation"),
        ("lep_pt", 0, math.nan, "track_isolation"),
        ("lep_pt", 0, math.inf, "track_isolation"),
        ("lep_pt", 0, 0.0, "track_isolation"),
        ("lep_pt", 0, -1.0, "track_isolation"),
    ],
)
def test_enhanced_quality_rejects_nonfinite_iso_and_nonpositive_pt(field, index, value, stage):
    event = passing_event()
    event[field][index] = value

    assert_fails_at(event, stage, enhanced_configured())


def test_enhanced_selection_rejects_inconsistent_quality_array_lengths():
    event = passing_event()
    event["lep_z0"] = event["lep_z0"][:3]

    assert not select_event(event, enhanced_configured(), "GeV").accepted


@pytest.mark.parametrize("count", [3, 5])
def test_requires_exactly_four_leptons(count):
    event = passing_event()
    event["lep_n"] = count
    for field in ("lep_pt", "lep_eta", "lep_phi", "lep_e", "lep_charge", "lep_type"):
        event[field] = event[field][:count] if count < 4 else event[field] + [event[field][-1]]

    result = assert_fails_at(event, "exactly_four_leptons")
    assert result.passed_stages == ()


def test_rejects_inconsistent_lepton_array_lengths_at_exactly_four_stage():
    event = passing_event()
    event["lep_eta"] = event["lep_eta"][:3]
    assert_fails_at(event, "exactly_four_leptons")


def test_rejects_unsupported_lepton_flavour():
    event = passing_event()
    event["lep_type"][3] = 15
    assert_fails_at(event, "allowed_lepton_types")


@pytest.mark.parametrize(
    ("index", "threshold"), [(0, 20.0), (1, 15.0), (2, 10.0), (3, 7.0)]
)
def test_ordered_pt_boundaries_include_equality(index, threshold):
    event = passing_event()
    event["lep_pt"] = [20.0, 15.0, 10.0, 7.0]
    event["lep_e"] = [45.0, 45.0, 15.0, 15.0]
    equal = select_event(event, configured(), "GeV")
    assert "lepton_pt" in equal.passed_stages

    event["lep_pt"][index] = threshold + 1e-6
    above = select_event(event, configured(), "GeV")
    assert "lepton_pt" in above.passed_stages

    event["lep_pt"][index] = threshold - 1e-6
    assert_fails_at(event, "lepton_pt")


@pytest.mark.parametrize(
    ("flavour", "limit"), [(11, 2.47), (13, 2.7)]
)
def test_eta_boundaries_are_strict(flavour, limit):
    event = passing_event()
    index = event["lep_type"].index(flavour)
    event["lep_eta"][index] = limit - 1e-6
    below = select_event(event, configured(), "GeV")
    assert "lepton_eta" in below.passed_stages

    event["lep_eta"][index] = limit
    assert_fails_at(event, "lepton_eta")

    event["lep_eta"][index] = limit + 1e-6
    assert_fails_at(event, "lepton_eta")


def test_requires_zero_total_charge():
    event = passing_event()
    event["lep_charge"][3] = 1
    assert_fails_at(event, "zero_charge")


def test_requires_two_non_overlapping_sfos_pairs():
    event = passing_event()
    event["lep_type"] = [11, 11, 11, 13]
    assert_fails_at(event, "valid_sfos_pairing")


def test_all_possible_sfos_pairs_must_exceed_five_gev():
    event = passing_event()
    event["lep_type"] = [11, 11, 11, 11]
    event["lep_phi"] = [0.0, math.pi, math.pi, 0.0]
    assert_fails_at(event, "all_sfos_mass")


def candidate_with_masses(*, z1=90.0, z2=30.0, m4l=120.0):
    candidate = reconstruct_candidate(normalize_leptons(passing_event(), "GeV"))
    assert candidate is not None
    return replace(
        candidate,
        z1=FourVector(z1, 0.0, 0.0, 0.0),
        z2=FourVector(z2, 0.0, 0.0, 0.0),
        four_lepton=FourVector(m4l, 0.0, 0.0, 0.0),
    )


@pytest.mark.parametrize(
    ("mass", "accepted"), [(4.999, False), (5.0, False), (5.001, True)]
)
def test_all_sfos_mass_boundary_is_strict(monkeypatch, mass, accepted):
    candidate = replace(candidate_with_masses(), all_sfos_masses=(mass, 30.0))
    monkeypatch.setattr(
        "src.selection.reconstruct_candidate", lambda normalized: candidate
    )
    result = select_event(passing_event(), configured(), "GeV")
    assert ("all_sfos_mass" in result.passed_stages) is accepted


@pytest.mark.parametrize(
    ("mass", "accepted"),
    [
        (49.999, False),
        (50.0, False),
        (50.001, True),
        (105.999, True),
        (106.0, False),
        (106.001, False),
    ],
)
def test_z1_mass_window_is_open(monkeypatch, mass, accepted):
    monkeypatch.setattr(
        "src.selection.reconstruct_candidate", lambda normalized: candidate_with_masses(z1=mass)
    )
    result = select_event(passing_event(), configured(), "GeV")
    assert result.accepted is accepted
    assert result.failed_stage == (None if accepted else "z1_mass_window")


@pytest.mark.parametrize(
    ("mass", "accepted"),
    [
        (11.999, False),
        (12.0, False),
        (12.001, True),
        (114.999, True),
        (115.0, False),
        (115.001, False),
    ],
)
def test_fixed_z2_mass_window_is_open(monkeypatch, mass, accepted):
    monkeypatch.setattr(
        "src.selection.reconstruct_candidate", lambda normalized: candidate_with_masses(z2=mass)
    )
    result = select_event(passing_event(), configured(), "GeV")
    assert result.accepted is accepted
    assert result.failed_stage == (None if accepted else "z2_mass_window")


def test_sliding_z2_lower_boundary_is_strict(monkeypatch):
    monkeypatch.setattr(
        "src.selection.reconstruct_candidate",
        lambda normalized: candidate_with_masses(z2=19.6, m4l=150.0),
    )
    assert_fails_at(passing_event(), "z2_mass_window", configured("sliding"))

    monkeypatch.setattr(
        "src.selection.reconstruct_candidate",
        lambda normalized: candidate_with_masses(z2=19.601, m4l=150.0),
    )
    assert select_event(passing_event(), configured("sliding"), "GeV").accepted


@pytest.mark.parametrize(
    ("mass", "accepted"), [(104.999, False), (105.0, True), (159.999, True), (160.0, False)]
)
def test_m4l_window_is_lower_inclusive_upper_exclusive(monkeypatch, mass, accepted):
    monkeypatch.setattr(
        "src.selection.reconstruct_candidate", lambda normalized: candidate_with_masses(m4l=mass)
    )
    result = select_event(passing_event(), configured(), "GeV")
    assert result.accepted is accepted
    assert result.failed_stage == (None if accepted else "m4l_analysis_window")


def test_configuration_change_changes_selection_result():
    event = passing_event()
    assert select_event(event, configured(), "GeV").accepted

    value = selection_mapping()
    value["lepton_pt_thresholds_gev"] = [50.0, 15.0, 10.0, 7.0]
    assert_fails_at(event, "lepton_pt", SelectionConfig.from_mapping(value))


def test_demo_yaml_contains_valid_selection_configuration():
    config = yaml.safe_load(Path("config/demo.yaml").read_text(encoding="utf-8"))
    parsed = SelectionConfig.from_mapping(config["selection"])
    assert parsed.z2_min_mode == "fixed"


def test_unsupported_momentum_unit_is_a_configuration_error():
    with pytest.raises(ValueError, match="unsupported momentum unit: invalid"):
        select_event(passing_event(), configured(), "invalid")
