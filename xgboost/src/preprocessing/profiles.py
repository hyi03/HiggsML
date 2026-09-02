"""Frozen MC ROOT input profiles."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class InputProfile:
    name: str
    tree_name: str
    momentum_unit: str
    branches: Mapping[str, str]
    normalization_in_events: bool

    def __post_init__(self) -> None:
        branches = dict(self.branches)
        if len(set(branches.values())) != len(branches):
            raise ValueError("duplicate physical branch mappings")
        object.__setattr__(self, "branches", MappingProxyType(branches))


_OPEN_DATA_2020 = InputProfile(
    name="open_data_2020",
    tree_name="mini",
    momentum_unit="MeV",
    branches={
        "runNumber": "runNumber",
        "eventNumber": "eventNumber",
        "channelNumber": "channelNumber",
        "lep_n": "lep_n",
        "lep_pt": "lep_pt",
        "lep_eta": "lep_eta",
        "lep_phi": "lep_phi",
        "lep_e": "lep_E",
        "lep_charge": "lep_charge",
        "lep_type": "lep_type",
        "trigE": "trigE",
        "trigM": "trigM",
        "lep_isTrigMatched": "lep_trigMatched",
        "lep_isTightID": "lep_isTightID",
        "lep_track_iso": "lep_ptcone30",
        "lep_calo_iso": "lep_etcone20",
        "lep_d0sig": "lep_tracksigd0pvunbiased",
        "lep_z0": "lep_z0",
        "mcWeight": "mcWeight",
    },
    normalization_in_events=False,
)

_RELEASE22 = InputProfile(
    name="release22",
    tree_name="analysis",
    momentum_unit="GeV",
    branches={
        "runNumber": "runNumber",
        "eventNumber": "eventNumber",
        "channelNumber": "channelNumber",
        "lep_n": "lep_n",
        "lep_pt": "lep_pt",
        "lep_eta": "lep_eta",
        "lep_phi": "lep_phi",
        "lep_e": "lep_e",
        "lep_charge": "lep_charge",
        "lep_type": "lep_type",
        "trigE": "trigE",
        "trigM": "trigM",
        "lep_isTrigMatched": "lep_isTrigMatched",
        "lep_isTightID": "lep_isTightID",
        "lep_track_iso": "lep_ptvarcone30",
        "lep_calo_iso": "lep_topoetcone20",
        "lep_d0sig": "lep_d0sig",
        "lep_z0": "lep_z0",
        "mcWeight": "mcWeight",
        "xsec": "xsec",
        "kfac": "kfac",
        "filteff": "filteff",
        "sum_of_weights": "sum_of_weights",
    },
    normalization_in_events=True,
)

_PROFILES = {
    _OPEN_DATA_2020.name: _OPEN_DATA_2020,
    _RELEASE22.name: _RELEASE22,
}


def resolve_input_profile(name: str) -> InputProfile:
    try:
        return _PROFILES[name]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unknown input profile: {name}") from exc
