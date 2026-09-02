from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

from src.config import InputBindingError

from .four_vectors import delta_phi, delta_r
from .reconstruction import FourLeptonCandidate


BASE14 = (
    "lep1_pt", "lep2_pt", "lep3_pt", "lep4_pt",
    "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta",
    "mZ1", "mZ2", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
)


def build_candidate_features(event: Mapping[str, Any], candidate: FourLeptonCandidate) -> dict[str, Any]:
    if candidate.pairing.z1_indices is None or candidate.pairing.z2_indices is None:
        raise InputBindingError("candidate pairing indices are missing")
    z1_leptons = [candidate.leptons[index] for index in candidate.pairing.z1_indices]
    z2_leptons = [candidate.leptons[index] for index in candidate.pairing.z2_indices]
    result: dict[str, Any] = {
        **{f"lep{index + 1}_pt": float(candidate.normalized.pt[index]) for index in range(4)},
        **{f"lep{index + 1}_eta": float(candidate.normalized.eta[index]) for index in range(4)},
        "mZ1": candidate.z1.mass,
        "mZ2": candidate.z2.mass,
        "pt4l": candidate.four_lepton.pt,
        "deltaR_Z1": delta_r(z1_leptons[0].vector, z1_leptons[1].vector),
        "deltaR_Z2": delta_r(z2_leptons[0].vector, z2_leptons[1].vector),
        "deltaPhi_ZZ": abs(delta_phi(candidate.z1.phi, candidate.z2.phi)),
        "m4l": candidate.four_lepton.mass,
        "runNumber": int(event["runNumber"]),
        "eventNumber": int(event["eventNumber"]),
        "channelNumber": int(event["channelNumber"]),
    }
    if not all(isfinite(float(result[name])) for name in (*BASE14, "m4l")):
        raise ValueError("features must be finite")
    return result
