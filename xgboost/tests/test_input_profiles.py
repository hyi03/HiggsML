import pytest

from src.input_profiles import InputProfile, resolve_input_profile


def test_open_data_2020_profile_maps_old_names_to_canonical_names():
    profile = resolve_input_profile("open_data_2020")

    assert profile.tree_name == "mini"
    assert profile.momentum_unit == "MeV"
    assert profile.branches["lep_e"] == "lep_E"
    assert profile.branches["lep_isTrigMatched"] == "lep_trigMatched"
    assert profile.branches["lep_track_iso"] == "lep_ptcone30"
    assert profile.branches["lep_calo_iso"] == "lep_etcone20"
    assert profile.branches["lep_d0sig"] == "lep_tracksigd0pvunbiased"
    assert profile.normalization_in_events is False


def test_release22_profile_maps_new_names_to_same_canonical_names():
    profile = resolve_input_profile("release22")

    assert profile.tree_name == "analysis"
    assert profile.momentum_unit == "GeV"
    assert profile.branches["lep_e"] == "lep_e"
    assert profile.branches["lep_isTrigMatched"] == "lep_isTrigMatched"
    assert profile.branches["lep_track_iso"] == "lep_ptvarcone30"
    assert profile.branches["lep_calo_iso"] == "lep_topoetcone20"
    assert profile.branches["lep_d0sig"] == "lep_d0sig"
    assert profile.normalization_in_events is True


def test_unknown_profile_and_duplicate_source_branches_are_rejected():
    with pytest.raises(ValueError, match="unknown input profile"):
        resolve_input_profile("not-a-profile")

    with pytest.raises(ValueError, match="duplicate physical branch mappings"):
        InputProfile(
            name="invalid",
            tree_name="tree",
            momentum_unit="GeV",
            branches={"first": "source", "second": "source"},
            normalization_in_events=False,
        )
