from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from .pairing import (
    FourVector,
    Lepton,
    PairingResult,
    all_sfos_pair_masses,
    pair_four_leptons,
    sum_vectors,
)


@dataclass(frozen=True)
class NormalizedLeptons:
    pt: np.ndarray
    eta: np.ndarray
    phi: np.ndarray
    energy: np.ndarray
    charge: np.ndarray
    flavour: np.ndarray


@dataclass(frozen=True)
class FourLeptonCandidate:
    normalized: NormalizedLeptons
    leptons: tuple[Lepton, Lepton, Lepton, Lepton]
    pairing: PairingResult
    z1: FourVector
    z2: FourVector
    four_lepton: FourVector
    all_sfos_masses: tuple[float, ...]


def _as_gev(values, momentum_unit: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    unit = momentum_unit.lower()
    if unit == "mev":
        return array / 1000.0
    if unit == "gev":
        return array
    raise ValueError(f"unsupported momentum unit: {momentum_unit}")


def normalize_leptons(
    event: Mapping[str, Any], momentum_unit: str
) -> NormalizedLeptons:
    pt = _as_gev(event["lep_pt"], momentum_unit)
    eta = np.asarray(event["lep_eta"], dtype=float)
    phi = np.asarray(event["lep_phi"], dtype=float)
    energy = _as_gev(event["lep_e"], momentum_unit)
    charge = np.asarray(event["lep_charge"], dtype=int)
    flavour = np.asarray(event["lep_type"], dtype=int)

    lengths = {len(pt), len(eta), len(phi), len(energy), len(charge), len(flavour)}
    if len(lengths) != 1:
        raise ValueError("inconsistent lepton array lengths")

    order = np.argsort(-pt, kind="stable")
    return NormalizedLeptons(
        pt=pt[order],
        eta=eta[order],
        phi=phi[order],
        energy=energy[order],
        charge=charge[order],
        flavour=flavour[order],
    )


def reconstruct_candidate(
    normalized: NormalizedLeptons,
) -> FourLeptonCandidate | None:
    if len(normalized.pt) != 4:
        return None

    leptons = tuple(
        Lepton(
            FourVector.from_pt_eta_phi_e(
                normalized.pt[index],
                normalized.eta[index],
                normalized.phi[index],
                normalized.energy[index],
            ),
            int(normalized.charge[index]),
            int(normalized.flavour[index]),
        )
        for index in range(4)
    )
    pairing = pair_four_leptons(leptons)
    if not pairing.valid or pairing.z1_indices is None or pairing.z2_indices is None:
        return None

    z1 = sum_vectors([leptons[index].vector for index in pairing.z1_indices])
    z2 = sum_vectors([leptons[index].vector for index in pairing.z2_indices])
    return FourLeptonCandidate(
        normalized=normalized,
        leptons=leptons,
        pairing=pairing,
        z1=z1,
        z2=z2,
        four_lepton=z1 + z2,
        all_sfos_masses=all_sfos_pair_masses(leptons),
    )
