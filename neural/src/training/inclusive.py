"""Fit-only scientific state for the sealed inclusive protocol."""
from dataclasses import dataclass

import numpy as np

from src.config import InputBindingError


class InsufficientStatistics(ValueError):
    """Declared scientific terminal state, never a debug fallback."""


@dataclass(frozen=True)
class MassBinning:
    boundaries: tuple[float, ...]

    def __post_init__(self):
        values = np.asarray(self.boundaries, dtype=np.float64)
        if values.shape != (10,) or not np.isfinite(values).all() or not np.all(np.diff(values) > 0):
            raise InputBindingError("inclusive mass boundaries must be ten increasing finite values")

    @classmethod
    def fit(cls, masses, physical_weights):
        masses = np.asarray(masses, dtype=np.float64)
        weights = np.abs(np.asarray(physical_weights, dtype=np.float64))
        if masses.ndim != 1 or masses.shape != weights.shape or not np.isfinite(masses).all() or not np.isfinite(weights).all():
            raise InputBindingError("invalid inclusive bin fitting data")
        positive = weights > 0
        if not positive.any():
            raise InsufficientStatistics("background has no positive absolute weight")
        # Sorting by mass and then weight makes duplicate aggregation independent of row order.
        order = np.lexsort((weights[positive], masses[positive]))
        values, starts = np.unique(masses[positive][order], return_index=True)
        sums = np.add.reduceat(weights[positive][order], starts)
        cumulative = np.cumsum(sums, dtype=np.float64)
        if not np.isfinite(cumulative).all():
            raise InputBindingError("background cumulative weight is not finite")
        positions = np.searchsorted(cumulative, cumulative[-1] * (np.arange(1, 11) / 11), side="left")
        boundaries = values[positions]
        if not np.all(np.diff(boundaries) > 0):
            raise InsufficientStatistics("weighted quantiles have repeated mass boundaries")
        result = cls(tuple(float(value) for value in boundaries))
        totals = np.bincount(result.indices(masses), weights=weights, minlength=11)
        if np.any(totals <= 0):
            raise InsufficientStatistics("weighted quantiles contain an empty effective bin")
        return result

    def indices(self, masses):
        values = np.asarray(masses, dtype=np.float64)
        if values.ndim != 1 or not np.isfinite(values).all():
            raise InputBindingError("mass bin assignment requires a finite vector")
        return np.searchsorted(self.boundaries, values, side="left").astype(np.int64)

    def to_dict(self):
        return {"algorithm": "background_abs_weight_quantiles", "version": 1,
                "bins": 11, "closure": "right", "edges_gev": [None, *self.boundaries, None]}

    @classmethod
    def from_dict(cls, raw):
        if not isinstance(raw, dict) or set(raw) != {"algorithm", "version", "bins", "closure", "edges_gev"}:
            raise InputBindingError("mass binning schema changed")
        edges = raw.get("edges_gev")
        if not isinstance(edges, list) or len(edges) != 12 or edges[0] is not None or edges[-1] is not None or any(type(x) is not float for x in edges[1:-1]):
            raise InputBindingError("mass binning edges changed")
        result = cls(tuple(edges[1:-1]))
        if raw != result.to_dict() or type(raw["version"]) is not int or type(raw["bins"]) is not int:
            raise InputBindingError("mass binning algorithm changed")
        return result


def fit_scientific_state(frame):
    means = {}
    for label in (0, 1):
        weights = np.abs(frame.loc[frame.label == label, "physical_weight"].to_numpy(dtype=np.float64))
        if not len(weights) or not np.isfinite(weights).all() or weights.sum() <= 0:
            raise InsufficientStatistics(f"class {label} has no positive absolute weight")
        means[str(label)] = float(weights.mean(dtype=np.float64))
    background = frame.loc[frame.label == 0]
    binning = MassBinning.fit(background.m4l, background.physical_weight)
    return {"schema_version": "inclusive-fit-state-v1", "mass_binning": binning.to_dict(),
            "weight_normalization": {"algorithm": "fit_class_mean_absolute", "version": 1, "class_means": means}}


def validate_scientific_state(raw):
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "mass_binning", "weight_normalization"} or raw["schema_version"] != "inclusive-fit-state-v1":
        raise InputBindingError("inclusive fitting state changed")
    MassBinning.from_dict(raw["mass_binning"])
    norm = raw["weight_normalization"]
    if not isinstance(norm, dict) or set(norm) != {"algorithm", "version", "class_means"} or norm["algorithm"] != "fit_class_mean_absolute" or type(norm["version"]) is not int or norm["version"] != 1:
        raise InputBindingError("inclusive weight normalization changed")
    means = norm["class_means"]
    if not isinstance(means, dict) or set(means) != {"0", "1"} or any(type(v) is not float or not np.isfinite(v) or v <= 0 for v in means.values()):
        raise InputBindingError("inclusive class means changed")
    return raw


def optimizer_weights(frame, state):
    validate_scientific_state(state)
    means = state["weight_normalization"]["class_means"]
    return np.abs(frame.physical_weight.to_numpy(dtype=np.float64)) / np.asarray([means[str(int(label))] for label in frame.label])
