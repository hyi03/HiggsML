from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .pairing import delta_phi, delta_r
from .reconstruction import (
    FourLeptonCandidate,
    normalize_leptons,
    reconstruct_candidate,
)

FEATURES = [
    "lep1_pt",
    "lep2_pt",
    "lep3_pt",
    "lep4_pt",
    "lep1_eta",
    "lep2_eta",
    "lep3_eta",
    "lep4_eta",
    "mZ1",
    "mZ2",
    "pt4l",
    "deltaR_Z1",
    "deltaR_Z2",
    "deltaPhi_ZZ",
]

FORBIDDEN_FEATURES = {
    "m4l",
    "channelNumber",
    "eventNumber",
    "runNumber",
    "mcWeight",
    "xsec",
    "kfac",
    "filteff",
    "sum_of_weights",
    "source_file",
    "period",
}


def build_candidate_features(
    event: Mapping[str, Any], candidate: FourLeptonCandidate
) -> dict[str, Any]:
    normalized = candidate.normalized
    pairing = candidate.pairing
    assert pairing.z1_indices is not None
    assert pairing.z2_indices is not None
    z1_leptons = [candidate.leptons[index] for index in pairing.z1_indices]
    z2_leptons = [candidate.leptons[index] for index in pairing.z2_indices]
    output: dict[str, Any] = {
        **{f"lep{i + 1}_pt": float(normalized.pt[i]) for i in range(4)},
        **{f"lep{i + 1}_eta": float(normalized.eta[i]) for i in range(4)},
        "mZ1": candidate.z1.mass,
        "mZ2": candidate.z2.mass,
        "m4l": candidate.four_lepton.mass,
        "pt4l": candidate.four_lepton.pt,
        "deltaR_Z1": delta_r(z1_leptons[0].vector, z1_leptons[1].vector),
        "deltaR_Z2": delta_r(z2_leptons[0].vector, z2_leptons[1].vector),
        "deltaPhi_ZZ": abs(delta_phi(candidate.z1.phi, candidate.z2.phi)),
        "eventNumber": int(event.get("eventNumber", -1)),
        "runNumber": int(event.get("runNumber", -1)),
        "channelNumber": int(event.get("channelNumber", 0)),
    }

    for field in ("mcWeight", "xsec", "kfac", "filteff", "sum_of_weights"):
        if field in event:
            output[field] = float(event[field])

    numeric = np.asarray(
        [output[name] for name in FEATURES] + [output["m4l"]], dtype=float
    )
    if not np.isfinite(numeric).all():
        raise ValueError("event features contain NaN or infinity")
    return output


def build_event_features(
    event: Mapping[str, Any], momentum_unit: str = "MeV"
) -> dict[str, Any] | None:
    lengths = {
        len(event[field])
        for field in (
            "lep_pt",
            "lep_eta",
            "lep_phi",
            "lep_e",
            "lep_charge",
            "lep_type",
        )
    }
    if lengths != {4}:
        return None
    candidate = reconstruct_candidate(normalize_leptons(event, momentum_unit))
    if candidate is None:
        return None
    try:
        return build_candidate_features(event, candidate)
    except ValueError:
        return None


def assert_no_feature_leakage(features: Sequence[str] = FEATURES) -> None:
    leaked = set(features) & FORBIDDEN_FEATURES
    if leaked:
        raise ValueError(f"forbidden model features: {sorted(leaked)}")
