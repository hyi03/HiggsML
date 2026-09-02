"""Pure MC normalization and event-weight calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np


@dataclass(frozen=True)
class MCNormalization:
    xsec_pb: float
    k_factor: float
    filter_efficiency: float
    sum_of_weights: float

    def __post_init__(self) -> None:
        for field in (
            "xsec_pb",
            "k_factor",
            "filter_efficiency",
            "sum_of_weights",
        ):
            try:
                value = float(getattr(self, field))
            except (TypeError, ValueError) as exc:
                raise ValueError("MC normalization values must be finite") from exc
            object.__setattr__(self, field, value)
        values = np.asarray(
            [
                self.xsec_pb,
                self.k_factor,
                self.filter_efficiency,
                self.sum_of_weights,
            ],
            dtype=float,
        )
        if not np.isfinite(values).all():
            raise ValueError("MC normalization values must be finite")
        if self.xsec_pb < 0:
            raise ValueError("xsec_pb must be non-negative")
        if self.k_factor <= 0:
            raise ValueError("k_factor must be strictly positive")
        if not 0 <= self.filter_efficiency <= 1:
            raise ValueError("filter_efficiency must be in the closed interval [0, 1]")
        if self.sum_of_weights == 0:
            raise ValueError("sum_of_weights must be non-zero")

    @classmethod
    def from_event(cls, event: Mapping[str, Any]) -> "MCNormalization":
        return cls(
            xsec_pb=float(event["xsec"]),
            k_factor=float(event["kfac"]),
            filter_efficiency=float(event["filteff"]),
            sum_of_weights=float(event["sum_of_weights"]),
        )

    @property
    def effective_cross_section_pb(self) -> float:
        return self.xsec_pb * self.k_factor * self.filter_efficiency

    def assert_matches(
        self,
        event: Mapping[str, Any],
        *,
        rtol: float = 1e-12,
        atol: float = 0.0,
    ) -> None:
        other = MCNormalization.from_event(event)
        for field in (
            "xsec_pb",
            "k_factor",
            "filter_efficiency",
            "sum_of_weights",
        ):
            if not np.isclose(
                getattr(self, field), getattr(other, field), rtol=rtol, atol=atol
            ):
                raise ValueError(f"{field} changed within one MC sample")


def physical_event_weights(
    mc_weight,
    xsec_pb,
    k_factor,
    filter_efficiency,
    sum_of_weights,
    luminosity_pb: float,
    scale_factors=1.0,
) -> np.ndarray:
    mc_weight = np.asarray(mc_weight, dtype=float)
    denominator = np.asarray(sum_of_weights, dtype=float)
    if np.any(denominator == 0):
        raise ValueError("sum_of_weights contains zero")
    weights = (
        float(luminosity_pb)
        * np.asarray(xsec_pb, dtype=float)
        * np.asarray(k_factor, dtype=float)
        * np.asarray(filter_efficiency, dtype=float)
        / denominator
        * mc_weight
        * np.asarray(scale_factors, dtype=float)
    )
    if not np.isfinite(weights).all():
        raise ValueError("physical weights contain NaN or infinity")
    return weights


def physical_event_weight(
    event: Mapping[str, Any],
    luminosity_pb: float,
    *,
    normalization: MCNormalization | None = None,
    require_event_normalization: bool = True,
) -> float:
    required_fields = {"xsec", "kfac", "filteff", "sum_of_weights"}
    event_fields = required_fields & set(event)
    if require_event_normalization and event_fields != required_fields:
        raise KeyError("MC event normalization fields are incomplete")
    if event_fields and event_fields != required_fields:
        raise KeyError("MC event normalization fields are incomplete")
    resolved = normalization or MCNormalization.from_event(event)
    if event_fields:
        resolved.assert_matches(event)
    value = physical_event_weights(
        event["mcWeight"],
        resolved.xsec_pb,
        resolved.k_factor,
        resolved.filter_efficiency,
        resolved.sum_of_weights,
        luminosity_pb,
    )
    return float(np.asarray(value))


def training_weights(physical_weights) -> np.ndarray:
    """Return finite, non-negative weights accepted by XGBoost.

    Signed physical weights remain available for yields. The training copy uses
    |w| because XGBoost does not accept negative sample weights.
    """
    weights = np.abs(np.asarray(physical_weights, dtype=float))
    if not np.isfinite(weights).all():
        raise ValueError("training weights contain NaN or infinity")
    mean = weights.mean()
    return weights / mean if mean > 0 else np.ones_like(weights)


def weight_summary(weights) -> dict[str, float | int]:
    values = np.asarray(weights, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("weights contain NaN or infinity")
    return {
        "events": int(values.size),
        "negative_events": int(np.count_nonzero(values < 0)),
        "sum_weights": float(values.sum()),
        "sum_abs_weights": float(np.abs(values).sum()),
    }
