from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, log, pi, sin, sinh, sqrt
from typing import Sequence


Z_MASS_GEV = 91.1876


@dataclass(frozen=True)
class FourVector:
    energy: float
    px: float
    py: float
    pz: float

    @classmethod
    def from_pt_eta_phi_e(
        cls, pt: float, eta: float, phi: float, energy: float
    ) -> "FourVector":
        return cls(
            float(energy),
            float(pt) * cos(float(phi)),
            float(pt) * sin(float(phi)),
            float(pt) * sinh(float(eta)),
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
        return sqrt(max(0.0, self.energy**2 - self.px**2 - self.py**2 - self.pz**2))

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


def sum_vectors(vectors: Sequence[FourVector]) -> FourVector:
    total = FourVector(0.0, 0.0, 0.0, 0.0)
    for vector in vectors:
        total = total + vector
    return total


def delta_phi(first: float, second: float) -> float:
    return (float(first) - float(second) + pi) % (2 * pi) - pi


def delta_r(first: FourVector, second: FourVector) -> float:
    return hypot(first.eta - second.eta, delta_phi(first.phi, second.phi))
