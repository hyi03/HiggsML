from __future__ import annotations

from math import atan2, isfinite, pi, sqrt

from .four_vectors import FourVector
from .reconstruction import FourLeptonCandidate


ANGULAR5 = ("cos_theta_star", "cos_theta_1", "cos_theta_2", "phi_decay_planes", "phi_production_plane")


def _spatial(vector: FourVector) -> tuple[float, float, float]:
    return vector.px, vector.py, vector.pz


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _unit(vector, name: str):
    norm = sqrt(_dot(vector, vector))
    if not isfinite(norm) or norm == 0:
        raise ValueError(f"{name} has zero or invalid norm")
    return tuple(value / norm for value in vector)


def _clip(value: float) -> float:
    if not isfinite(value) or value < -1 - 1e-12 or value > 1 + 1e-12:
        raise ValueError("cosine outside tolerance")
    return min(1.0, max(-1.0, value))


def _angle(axis, first, second) -> float:
    return (atan2(_dot(axis, _cross(first, second)), _dot(first, second)) + pi) % (2 * pi) - pi


def boost(vector: FourVector, beta) -> FourVector:
    beta = tuple(float(value) for value in beta)
    beta2 = _dot(beta, beta)
    if beta2 >= 1 or not all(isfinite(value) for value in (*beta, vector.energy, vector.px, vector.py, vector.pz)):
        raise ValueError("invalid Lorentz boost")
    if beta2 == 0:
        return vector
    gamma = 1 / sqrt(1 - beta2)
    momentum = _spatial(vector)
    product = _dot(beta, momentum)
    factor = (gamma - 1) * product / beta2 - gamma * vector.energy
    boosted = tuple(component + factor * direction for component, direction in zip(momentum, beta))
    return FourVector(gamma * (vector.energy - product), *boosted)


def _rest_beta(vector: FourVector):
    if vector.energy == 0:
        raise ValueError("zero energy")
    return vector.px / vector.energy, vector.py / vector.energy, vector.pz / vector.energy


def _charge_order(candidate: FourLeptonCandidate, indices: tuple[int, int]):
    first, second = (candidate.leptons[index] for index in indices)
    if {first.charge, second.charge} != {-1, 1}:
        raise ValueError("Z pair must contain opposite unit charges")
    negative = first if first.charge == -1 else second
    positive = second if first.charge == -1 else first
    return negative.vector, positive.vector


def build_angular5(candidate: FourLeptonCandidate) -> dict[str, float]:
    z1_indices, z2_indices = candidate.pairing.z1_indices, candidate.pairing.z2_indices
    if z1_indices is None or z2_indices is None:
        raise ValueError("missing Z pairing")
    l1m, l1p = _charge_order(candidate, z1_indices)
    l2m, l2p = _charge_order(candidate, z2_indices)
    x_beta = _rest_beta(candidate.four_lepton)
    z1x, z2x = boost(candidate.z1, x_beta), boost(candidate.z2, x_beta)
    l1mx, l1px = boost(l1m, x_beta), boost(l1p, x_beta)
    l2mx, l2px = boost(l2m, x_beta), boost(l2p, x_beta)
    beamx = boost(FourVector(1, 0, 0, 1), x_beta)
    z1axis, beamaxis = _unit(_spatial(z1x), "z1 axis"), _unit(_spatial(beamx), "beam axis")
    l1z1, z2z1 = boost(l1m, _rest_beta(candidate.z1)), boost(candidate.z2, _rest_beta(candidate.z1))
    l2z2, z1z2 = boost(l2m, _rest_beta(candidate.z2)), boost(candidate.z1, _rest_beta(candidate.z2))
    n1 = _unit(_cross(_spatial(l1mx), _spatial(l1px)), "z1 decay plane")
    n2 = _unit(_cross(_spatial(l2mx), _spatial(l2px)), "z2 decay plane")
    production = _unit(_cross(beamaxis, z1axis), "production plane")
    result = {
        "cos_theta_star": _clip(_dot(z1axis, beamaxis)),
        "cos_theta_1": _clip(_dot(_unit(_spatial(l1z1), "l1"), tuple(-v for v in _unit(_spatial(z2z1), "z2")))),
        "cos_theta_2": _clip(_dot(_unit(_spatial(l2z2), "l2"), tuple(-v for v in _unit(_spatial(z1z2), "z1")))),
        "phi_decay_planes": _angle(z1axis, n1, n2),
        "phi_production_plane": _angle(z1axis, production, n1),
    }
    if tuple(result) != ANGULAR5 or not all(isfinite(value) for value in result.values()):
        raise ValueError("invalid Angular5 outputs")
    return result
