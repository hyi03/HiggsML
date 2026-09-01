import math

from src.selection import CutflowAccumulator, SelectionConfig, select_event


ENHANCED_STAGES = (
    "read", "trigger", "allowed_lepton_types", "tight_identification",
    "track_isolation", "calorimeter_isolation",
    "transverse_impact_parameter", "longitudinal_impact_parameter",
    "exactly_four_good_leptons", "trigger_match", "lepton_pt", "lepton_eta",
    "zero_charge", "valid_sfos_pairing", "all_sfos_mass",
    "z1_mass_window", "z2_mass_window", "m4l_analysis_window", "selected",
)


def enhanced_config():
    return SelectionConfig.from_mapping(
        {
            "require_exactly_four_leptons": True,
            "allowed_lepton_types": [11, 13],
            "lepton_pt_thresholds_gev": [20.0, 15.0, 10.0, 7.0],
            "electron_max_abs_eta": 2.47,
            "muon_max_abs_eta": 2.7,
            "require_zero_charge": True,
            "min_all_sfos_mass_gev": 5.0,
            "z1_mass_window_gev": [50.0, 106.0],
            "z2_mass": {"min_mode": "fixed", "fixed_min_gev": 12.0, "max_gev": 115.0,
                        "sliding": {"low_m4l_gev": 140.0, "high_m4l_gev": 190.0,
                                    "low_min_gev": 12.0, "high_min_gev": 50.0}},
            "m4l_window_gev": [105.0, 160.0],
            "lepton_quality": {
                "enabled": True, "require_event_trigger": True,
                "require_trigger_match": True, "require_tight_id": True,
                "track_isolation_max": 0.3, "calo_isolation_max": 0.3,
                "electron_d0sig_max": 5.0, "muon_d0sig_max": 3.0,
                "z0_sintheta_max_mm": 0.5,
            },
        }
    )


def event(*, trigger=True, tight=True):
    return {
        "lep_n": 4, "lep_pt": [45.0, 45.0, 15.0, 15.0],
        "lep_eta": [0.0] * 4, "lep_phi": [0.0, math.pi, math.pi / 2, -math.pi / 2],
        "lep_e": [45.0, 45.0, 15.0, 15.0], "lep_charge": [1, -1, 1, -1],
        "lep_type": [11, 11, 13, 13], "trigE": trigger, "trigM": False,
        "lep_isTrigMatched": [True] * 4, "lep_isTightID": [tight] * 4,
        "lep_track_iso": [0.1] * 4, "lep_calo_iso": [0.1] * 4,
        "lep_d0sig": [0.1] * 4, "lep_z0": [0.1] * 4,
    }


def test_enhanced_cutflow_uses_instance_stage_order_and_prefix_weight_membership():
    config = enhanced_config()
    assert config.stages == ENHANCED_STAGES
    cutflow = CutflowAccumulator(sample_name="mc", is_data=False, stages=config.stages)
    selected = select_event(event(), config, "GeV")
    trigger_failed = select_event(event(trigger=False), config, "GeV")
    tight_failed = select_event(event(tight=False), config, "GeV")

    for result, weight in ((selected, 2.0), (trigger_failed, -1.0), (tight_failed, 0.5)):
        cutflow.record_read(weight)
        cutflow.record_selection(result, weight)
    stages = cutflow.to_dict()["stages"]

    counts = [stages[stage]["count"] for stage in ENHANCED_STAGES]
    assert counts == sorted(counts, reverse=True)
    expected_signed = {
        "read": 1.5,
        "trigger": 2.5,
        "allowed_lepton_types": 2.5,
        **{stage: 2.0 for stage in ENHANCED_STAGES[3:]},
    }
    expected_absolute = {
        "read": 3.5,
        "trigger": 2.5,
        "allowed_lepton_types": 2.5,
        **{stage: 2.0 for stage in ENHANCED_STAGES[3:]},
    }
    assert {
        stage: stages[stage]["signed_weighted_yield"]
        for stage in ENHANCED_STAGES
    } == expected_signed
    assert {
        stage: stages[stage]["absolute_weighted_yield"]
        for stage in ENHANCED_STAGES
    } == expected_absolute
