"""Canonical five-angle H -> ZZ* -> 4l observables."""

from __future__ import annotations

from math import atan2, isfinite, pi, sqrt
from typing import Iterable

from .pairing import FourVector
from .reconstruction import FourLeptonCandidate


ANGULAR5_FEATURES: tuple[str, ...] = (
    "cos_theta_star",
    "cos_theta_1",
    "cos_theta_2",
    "phi_decay_planes",
    "phi_production_plane",
)

_COSINE_TOLERANCE = 1e-12


def _finite_vector(vector: FourVector, name: str) -> None:
    if not all(isfinite(value) for value in (vector.energy, vector.px, vector.py, vector.pz)):
        raise ValueError(f"{name} must be finite")


def _spatial(vector: FourVector) -> tuple[float, float, float]:
    return (vector.px, vector.py, vector.pz)


def _dot(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    return sum(left * right for left, right in zip(first, second))


def _cross(
    first: tuple[float, float, float], second: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _unit(vector: tuple[float, float, float], name: str) -> tuple[float, float, float]:
    if not all(isfinite(value) for value in vector):
        raise ValueError(f"{name} must be finite")
    norm = sqrt(_dot(vector, vector))
    if not isfinite(norm) or norm == 0.0:
        raise ValueError(f"{name} has zero norm")
    return tuple(value / norm for value in vector)


def _clip_cosine(value: float, name: str) -> float:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < -1.0 - _COSINE_TOLERANCE or value > 1.0 + _COSINE_TOLERANCE:
        raise ValueError(f"{name} is outside [-1, 1]")
    return min(1.0, max(-1.0, value))


def _signed_angle(
    axis: tuple[float, float, float],
    first: tuple[float, float, float],
    second: tuple[float, float, float],
    name: str,
) -> float:
    angle = atan2(_dot(axis, _cross(first, second)), _dot(first, second))
    if not isfinite(angle):
        raise ValueError(f"{name} must be finite")
    return (angle + pi) % (2.0 * pi) - pi


def _rest_frame_beta(vector: FourVector, name: str) -> tuple[float, float, float]:
    _finite_vector(vector, name)
    if vector.energy == 0.0:
        raise ValueError(f"{name} has zero energy")
    return (vector.px / vector.energy, vector.py / vector.energy, vector.pz / vector.energy)


def _negative_positive_leptons(candidate: FourLeptonCandidate, indices: tuple[int, int], name: str):
    if len(indices) != 2 or any(index < 0 or index >= len(candidate.leptons) for index in indices):
        raise ValueError(f"{name} has invalid indices")
    first, second = (candidate.leptons[index] for index in indices)
    if {first.charge, second.charge} != {-1, 1}:
        raise ValueError(f"{name} must contain negative and positive charges")
    negative = first if first.charge == -1 else second
    positive = first if first.charge == 1 else second
    return negative.vector, positive.vector


def lorentz_boost(vector: FourVector, beta: Iterable[float]) -> FourVector:
    """Boost ``vector`` by ``beta`` using the frozen Angular5 convention."""
    _finite_vector(vector, "vector")
    components = tuple(float(value) for value in beta)
    if len(components) != 3:
        raise ValueError("beta must have exactly three components")
    if not all(isfinite(value) for value in components):
        raise ValueError("beta must be finite")

    beta2 = _dot(components, components)
    if beta2 >= 1.0:
        raise ValueError("beta magnitude must be less than one")
    if beta2 == 0.0:
        return FourVector(vector.energy, vector.px, vector.py, vector.pz)

    gamma = 1.0 / sqrt(1.0 - beta2)
    momentum = _spatial(vector)
    beta_dot_momentum = _dot(components, momentum)
    factor = ((gamma - 1.0) * beta_dot_momentum / beta2) - gamma * vector.energy
    boosted_momentum = tuple(
        component + factor * beta_component
        for component, beta_component in zip(momentum, components)
    )
    boosted = FourVector(
        gamma * (vector.energy - beta_dot_momentum),
        *boosted_momentum,
    )
    _finite_vector(boosted, "boosted vector")
    return boosted


def build_angular5(candidate: FourLeptonCandidate) -> dict[str, float]:
    """Calculate the frozen canonical Angular5 observables for a reconstructed event."""
    if candidate.pairing.z1_indices is None or candidate.pairing.z2_indices is None:
        raise ValueError("candidate requires two Z pairings")

    l1_minus, l1_plus = _negative_positive_leptons(
        candidate, candidate.pairing.z1_indices, "Z1"
    )
    l2_minus, l2_plus = _negative_positive_leptons(
        candidate, candidate.pairing.z2_indices, "Z2"
    )
    for name, vector in (
        ("l1-", l1_minus),
        ("l1+", l1_plus),
        ("l2-", l2_minus),
        ("l2+", l2_plus),
        ("Z1", candidate.z1),
        ("Z2", candidate.z2),
        ("X", candidate.four_lepton),
    ):
        _finite_vector(vector, name)

    x_beta = _rest_frame_beta(candidate.four_lepton, "X")
    z1_x = lorentz_boost(candidate.z1, x_beta)
    z2_x = lorentz_boost(candidate.z2, x_beta)
    l1_minus_x = lorentz_boost(l1_minus, x_beta)
    l1_plus_x = lorentz_boost(l1_plus, x_beta)
    l2_minus_x = lorentz_boost(l2_minus, x_beta)
    l2_plus_x = lorentz_boost(l2_plus, x_beta)
    beam_x = lorentz_boost(FourVector(1.0, 0.0, 0.0, 1.0), x_beta)

    z1_axis_x = _unit(_spatial(z1_x), "Z1 X-frame axis")
    beam_axis_x = _unit(_spatial(beam_x), "beam X-frame axis")

    z1_beta = _rest_frame_beta(candidate.z1, "Z1")
    l1_minus_z1 = lorentz_boost(l1_minus, z1_beta)
    z2_z1 = lorentz_boost(candidate.z2, z1_beta)

    z2_beta = _rest_frame_beta(candidate.z2, "Z2")
    l2_minus_z2 = lorentz_boost(l2_minus, z2_beta)
    z1_z2 = lorentz_boost(candidate.z1, z2_beta)

    n1 = _unit(_cross(_spatial(l1_minus_x), _spatial(l1_plus_x)), "Z1 decay plane")
    n2 = _unit(_cross(_spatial(l2_minus_x), _spatial(l2_plus_x)), "Z2 decay plane")
    n_production = _unit(_cross(beam_axis_x, z1_axis_x), "production plane")

    angles = {
        "cos_theta_star": _clip_cosine(
            _dot(z1_axis_x, beam_axis_x), "cos_theta_star"
        ),
        "cos_theta_1": _clip_cosine(
            _dot(
                _unit(_spatial(l1_minus_z1), "l1- Z1-frame axis"),
                tuple(-value for value in _unit(_spatial(z2_z1), "Z2 Z1-frame axis")),
            ),
            "cos_theta_1",
        ),
        "cos_theta_2": _clip_cosine(
            _dot(
                _unit(_spatial(l2_minus_z2), "l2- Z2-frame axis"),
                tuple(-value for value in _unit(_spatial(z1_z2), "Z1 Z2-frame axis")),
            ),
            "cos_theta_2",
        ),
        "phi_decay_planes": _signed_angle(z1_axis_x, n1, n2, "phi_decay_planes"),
        "phi_production_plane": _signed_angle(
            z1_axis_x, n_production, n1, "phi_production_plane"
        ),
    }
    if tuple(angles) != ANGULAR5_FEATURES or not all(isfinite(value) for value in angles.values()):
        raise ValueError("Angular5 outputs must be finite")
    return angles
