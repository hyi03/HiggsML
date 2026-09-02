from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Mapping, Sequence

import numpy as np

from .four_vectors import FourVector, Z_MASS_GEV, sum_vectors


@dataclass(frozen=True)
class NormalizedLeptons:
    pt: np.ndarray
    eta: np.ndarray
    phi: np.ndarray
    energy: np.ndarray
    charge: np.ndarray
    flavour: np.ndarray


@dataclass(frozen=True)
class Lepton:
    vector: FourVector
    charge: int
    flavour: int


@dataclass(frozen=True)
class PairingResult:
    valid: bool
    z1_indices: tuple[int, int] | None = None
    z2_indices: tuple[int, int] | None = None


@dataclass(frozen=True)
class FourLeptonCandidate:
    normalized: NormalizedLeptons
    leptons: tuple[Lepton, Lepton, Lepton, Lepton]
    pairing: PairingResult
    z1: FourVector
    z2: FourVector
    four_lepton: FourVector
    all_sfos_masses: tuple[float, ...]


def normalize_leptons(event: Mapping[str, Any], momentum_unit: str) -> NormalizedLeptons:
    scale = {"gev": 1.0, "mev": 0.001}.get(str(momentum_unit).lower())
    if scale is None:
        raise ValueError(f"unsupported momentum unit: {momentum_unit}")
    pt = np.asarray(event["lep_pt"], dtype=float) * scale
    eta = np.asarray(event["lep_eta"], dtype=float)
    phi = np.asarray(event["lep_phi"], dtype=float)
    energy = np.asarray(event["lep_e"], dtype=float) * scale
    charge = np.asarray(event["lep_charge"], dtype=int)
    flavour = np.asarray(event["lep_type"], dtype=int)
    if len({len(item) for item in (pt, eta, phi, energy, charge, flavour)}) != 1:
        raise ValueError("inconsistent lepton array lengths")
    if not np.isfinite(np.concatenate((pt, eta, phi, energy))).all():
        raise ValueError("lepton arrays must be finite")
    order = np.argsort(-pt, kind="stable")
    return NormalizedLeptons(pt[order], eta[order], phi[order], energy[order], charge[order], flavour[order])


def is_sfos(first: Lepton, second: Lepton) -> bool:
    return abs(first.flavour) == abs(second.flavour) and first.charge * second.charge == -1


def _mass(leptons: Sequence[Lepton], indices: tuple[int, int]) -> float:
    return sum_vectors([leptons[index].vector for index in indices]).mass


def pair_four_leptons(leptons: Sequence[Lepton]) -> PairingResult:
    if len(leptons) != 4:
        return PairingResult(False)
    candidates: list[tuple[float, tuple[int, int], tuple[int, int]]] = []
    for first, second in (((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))):
        if not is_sfos(leptons[first[0]], leptons[first[1]]) or not is_sfos(
            leptons[second[0]], leptons[second[1]]
        ):
            continue
        first_distance = abs(_mass(leptons, first) - Z_MASS_GEV)
        second_distance = abs(_mass(leptons, second) - Z_MASS_GEV)
        if first_distance <= second_distance:
            candidates.append((first_distance, first, second))
        else:
            candidates.append((second_distance, second, first))
    if not candidates:
        return PairingResult(False)
    _, z1, z2 = min(candidates, key=lambda item: (item[0], item[1], item[2]))
    return PairingResult(True, z1, z2)


def reconstruct_candidate(normalized: NormalizedLeptons) -> FourLeptonCandidate | None:
    if len(normalized.pt) != 4:
        return None
    leptons = tuple(
        Lepton(
            FourVector.from_pt_eta_phi_e(
                normalized.pt[index], normalized.eta[index], normalized.phi[index], normalized.energy[index]
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
    all_masses = tuple(
        sum_vectors([leptons[a].vector, leptons[b].vector]).mass
        for a, b in combinations(range(4), 2)
        if is_sfos(leptons[a], leptons[b])
    )
    return FourLeptonCandidate(normalized, leptons, pairing, z1, z2, z1 + z2, all_masses)
