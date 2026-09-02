"""Pure four-vector and SFOS-pairing domain logic."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import atan2, cos, cosh, hypot, log, pi, sin, sinh, sqrt
from typing import Sequence

Z_MASS_GEV = 91.1876


@dataclass(frozen=True)
class FourVector:
    """Cartesian four-vector using GeV."""

    energy: float
    px: float
    py: float
    pz: float

    @classmethod
    def from_pt_eta_phi_e(
        cls, pt: float, eta: float, phi: float, energy: float
    ) -> "FourVector":
        return cls(
            energy=float(energy),
            px=float(pt) * cos(float(phi)),
            py=float(pt) * sin(float(phi)),
            pz=float(pt) * sinh(float(eta)),
        )

    def __add__(self, other: "FourVector") -> "FourVector":
        return FourVector(
            self.energy + other.energy,
            self.px + other.px,
            self.py + other.py,
            self.pz + other.pz,
        )

    @property
    def mass(self) -> float:
        mass2 = self.energy**2 - self.px**2 - self.py**2 - self.pz**2
        return sqrt(max(0.0, mass2))

    @property
    def pt(self) -> float:
        return hypot(self.px, self.py)

    @property
    def phi(self) -> float:
        return atan2(self.py, self.px)

    @property
    def eta(self) -> float:
        momentum = sqrt(self.px**2 + self.py**2 + self.pz**2)
        if momentum == abs(self.pz):
            return float("inf") if self.pz >= 0 else float("-inf")
        return 0.5 * log((momentum + self.pz) / (momentum - self.pz))


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
    reason: str | None = None


def sum_vectors(vectors: Sequence[FourVector]) -> FourVector:
    total = FourVector(0.0, 0.0, 0.0, 0.0)
    for vector in vectors:
        total = total + vector
    return total


def invariant_mass(vectors: Sequence[FourVector]) -> float:
    return sum_vectors(vectors).mass


def is_sfos(first: Lepton, second: Lepton) -> bool:
    return (
        abs(int(first.flavour)) == abs(int(second.flavour))
        and int(first.charge) * int(second.charge) == -1
    )


def all_sfos_pair_masses(leptons: Sequence[Lepton]) -> tuple[float, ...]:
    """Return every SFOS invariant mass in deterministic index order."""
    return tuple(
        invariant_mass([leptons[first].vector, leptons[second].vector])
        for first, second in combinations(range(len(leptons)), 2)
        if is_sfos(leptons[first], leptons[second])
    )


def pair_four_leptons(
    leptons: Sequence[Lepton], z_mass: float = Z_MASS_GEV
) -> PairingResult:
    if len(leptons) != 4:
        return PairingResult(False, reason="expected exactly four leptons")

    partitions = [
        ((0, 1), (2, 3)),
        ((0, 2), (1, 3)),
        ((0, 3), (1, 2)),
    ]
    candidates: list[
        tuple[float, tuple[int, int], tuple[int, int]]
    ] = []

    for first_pair, second_pair in partitions:
        if not is_sfos(leptons[first_pair[0]], leptons[first_pair[1]]):
            continue
        if not is_sfos(leptons[second_pair[0]], leptons[second_pair[1]]):
            continue
        first_mass = invariant_mass([leptons[index].vector for index in first_pair])
        second_mass = invariant_mass([leptons[index].vector for index in second_pair])
        if abs(first_mass - z_mass) <= abs(second_mass - z_mass):
            z1, z2, distance = first_pair, second_pair, abs(first_mass - z_mass)
        else:
            z1, z2, distance = second_pair, first_pair, abs(second_mass - z_mass)
        candidates.append((distance, z1, z2))

    if not candidates:
        return PairingResult(False, reason="no two-SFOS pairing")

    _, z1, z2 = min(candidates, key=lambda item: (item[0], item[1], item[2]))
    return PairingResult(True, z1, z2)


def delta_phi(phi1: float, phi2: float) -> float:
    """Signed Δφ in [-π, π)."""
    return (float(phi1) - float(phi2) + pi) % (2 * pi) - pi


def delta_r(first: FourVector, second: FourVector) -> float:
    return hypot(first.eta - second.eta, delta_phi(first.phi, second.phi))
