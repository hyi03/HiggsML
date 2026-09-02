"""Pure scientific behavior for the Angular19 XGBoost workflow."""

from .angular5 import ANGULAR5_FEATURES, build_angular5
from .features import FEATURES, FORBIDDEN_FEATURES, build_candidate_features
from .reconstruction import FourLeptonCandidate, normalize_leptons, reconstruct_candidate
from .selection import CutflowAccumulator, SelectionConfig, select_event
from .split import event_split
from .weights import MCNormalization, physical_event_weight, training_weights

__all__ = [
    "ANGULAR5_FEATURES",
    "FEATURES",
    "FORBIDDEN_FEATURES",
    "CutflowAccumulator",
    "FourLeptonCandidate",
    "MCNormalization",
    "SelectionConfig",
    "build_angular5",
    "build_candidate_features",
    "event_split",
    "normalize_leptons",
    "physical_event_weight",
    "reconstruct_candidate",
    "select_event",
    "training_weights",
]
