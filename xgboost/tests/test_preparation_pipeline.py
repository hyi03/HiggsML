import math

import numpy as np

from src.pipeline import prepare_sample
from src.selection import SelectionConfig
from src.weights import MCNormalization


def enhanced_config():
    mapping = {
        "require_exactly_four_leptons": True, "allowed_lepton_types": [11, 13],
        "lepton_pt_thresholds_gev": [20.0, 15.0, 10.0, 7.0],
        "electron_max_abs_eta": 2.47, "muon_max_abs_eta": 2.7,
        "require_zero_charge": True, "min_all_sfos_mass_gev": 5.0,
        "z1_mass_window_gev": [50.0, 106.0],
        "z2_mass": {"min_mode": "fixed", "fixed_min_gev": 12.0, "max_gev": 115.0,
                    "sliding": {"low_m4l_gev": 140.0, "high_m4l_gev": 190.0,
                                "low_min_gev": 12.0, "high_min_gev": 50.0}},
        "m4l_window_gev": [105.0, 160.0],
        "lepton_quality": {"enabled": True, "require_event_trigger": True,
                           "require_trigger_match": True, "require_tight_id": True,
                           "track_isolation_max": 0.3, "calo_isolation_max": 0.3,
                           "electron_d0sig_max": 5.0, "muon_d0sig_max": 3.0,
                           "z0_sintheta_max_mm": 0.5},
    }
    return SelectionConfig.from_mapping(mapping)


def event():
    return {
        "lep_n": 4, "lep_pt": [45000.0, 45000.0, 15000.0, 15000.0], "lep_eta": [0.0] * 4,
        "lep_phi": [0.0, math.pi, math.pi / 2, -math.pi / 2],
        "lep_e": [45000.0, 45000.0, 15000.0, 15000.0], "lep_charge": [1, -1, 1, -1],
        "lep_type": [11, 11, 13, 13], "trigE": True, "trigM": False,
        "lep_isTrigMatched": [True] * 4, "lep_isTightID": [True] * 4,
        "lep_track_iso": [0.1] * 4, "lep_calo_iso": [0.1] * 4,
        "lep_d0sig": [0.1] * 4, "lep_z0": [0.1] * 4,
        "eventNumber": 1, "runNumber": 1, "channelNumber": 363490, "mcWeight": 2.0,
    }


def test_prepare_sample_resolves_profile_and_uses_external_normalization(monkeypatch):
    calls = []

    def fake_iter_events(*args, **kwargs):
        calls.append(kwargs)
        return iter([event()])

    monkeypatch.setattr("src.pipeline.iter_events", fake_iter_events)
    normalization = MCNormalization(1.2564, 1.0, 1.0, 7538705.808)
    prepared = prepare_sample(
        "unused.root", sample_name="zz_363490", selection=enhanced_config(),
        tree_name="mini", momentum_unit="MeV", is_data=False, label=0,
        expected_channels=[363490], input_profile="open_data_2020",
        normalization_override=normalization,
    )

    assert calls[0]["profile"].name == "open_data_2020"
    assert calls[0]["extra_canonical_branches"] == enhanced_config().required_canonical_branches
    assert prepared.normalization == normalization
    assert prepared.cutflow["stages"]["selected"]["count"] == 1


def test_prepare_sample_writes_external_normalization_to_audit_columns(monkeypatch):
    """Changing the audit values back to raw open-data fields must fail this test."""
    monkeypatch.setattr("src.pipeline.iter_events", lambda *args, **kwargs: iter([event()]))
    normalization = MCNormalization(1.2564, 1.0, 1.0, 7538705.808)

    prepared = prepare_sample(
        "unused.root", sample_name="zz_363490", selection=enhanced_config(),
        tree_name="mini", momentum_unit="MeV", is_data=False, label=0,
        expected_channels=[363490], input_profile="open_data_2020",
        normalization_override=normalization,
    )

    audit_columns = ["xsec", "kfac", "filteff", "sum_of_weights"]
    audit_values = prepared.frame.loc[0, audit_columns].to_numpy(dtype=float)
    assert audit_values.tolist() == [1.2564, 1.0, 1.0, 7538705.808]
    assert np.isfinite(audit_values).all()
