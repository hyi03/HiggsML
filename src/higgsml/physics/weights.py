from __future__ import annotations

import numpy as np


def physical_event_weight(
    *, mc_weight: float, xsec_pb: float, k_factor: float,
    filter_efficiency: float, sum_of_weights: float, luminosity_pb: float
) -> float:
    values = np.asarray(
        [mc_weight, xsec_pb, k_factor, filter_efficiency, sum_of_weights, luminosity_pb],
        dtype=float,
    )
    if not np.isfinite(values).all() or sum_of_weights == 0:
        raise ValueError("invalid MC normalization")
    result = luminosity_pb * xsec_pb * k_factor * filter_efficiency / sum_of_weights * mc_weight
    if not np.isfinite(result):
        raise ValueError("physical weight must be finite")
    return float(result)


def training_weights(physical_weights) -> np.ndarray:
    values = np.abs(np.asarray(physical_weights, dtype=float))
    if not np.isfinite(values).all():
        raise ValueError("training weights must be finite")
    mean = values.mean()
    return values / mean if mean > 0 else np.ones_like(values)
