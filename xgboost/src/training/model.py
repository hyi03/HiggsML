"""XGBoost model construction and frozen result records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..config import XGBoostProtocol


@dataclass(frozen=True)
class FoldResult:
    fold: int
    weighted_auc: float
    unweighted_auc: float
    best_iteration: int


@dataclass(frozen=True)
class CandidateResult:
    index: int
    parameters: Mapping[str, object]
    folds: tuple[FoldResult, ...]
    mean_weighted_auc: float
    standard_error_weighted_auc: float
    oof_scores: pd.Series


def model_parameters(
    protocol: XGBoostProtocol, *, final: bool, tree_count: int | None = None
) -> dict[str, object]:
    output: dict[str, object] = {
        **dict(protocol.candidate),
        "n_estimators": int(protocol.common["n_estimators"]),
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "random_state": int(protocol.common["random_seed"]),
        "n_jobs": int(protocol.common["n_jobs"]),
        "tree_method": str(protocol.common["tree_method"]),
    }
    if final:
        if tree_count is None or tree_count < 1:
            raise ValueError("final model requires a positive tree count")
        output["n_estimators"] = int(tree_count)
    else:
        output["early_stopping_rounds"] = int(protocol.common["early_stopping_rounds"])
    return output


def final_tree_count(result: CandidateResult) -> int:
    counts = np.asarray([fold.best_iteration + 1 for fold in result.folds], dtype=float)
    if len(counts) == 0 or not np.isfinite(counts).all():
        raise ValueError("candidate fold best iterations are invalid")
    return max(1, int(np.rint(np.median(counts))))


def positive_scores(model: Any, frame: pd.DataFrame, features: tuple[str, ...]) -> np.ndarray:
    probabilities = np.asarray(model.predict_proba(frame.loc[:, features]), dtype=float)
    if probabilities.ndim != 2 or probabilities.shape != (len(frame), 2):
        raise ValueError("classifier must return a two-column probability matrix")
    scores = probabilities[:, 1]
    if not np.isfinite(scores).all():
        raise ValueError("classifier returned NaN or infinity")
    return scores


def best_iteration(model: Any, n_estimators: int) -> int:
    value = getattr(model, "best_iteration", None)
    if not isinstance(value, (int, np.integer)) or isinstance(value, bool):
        return n_estimators - 1
    if value < 0:
        raise ValueError("classifier best_iteration must be non-negative")
    return int(value)


def default_model_factory(**parameters: object) -> Any:
    try:
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise RuntimeError("install requirements.txt before training") from exc
    except Exception as exc:
        if "libomp" in str(exc).lower():
            raise RuntimeError(
                "XGBoost requires the OpenMP runtime on macOS; install it with `brew install libomp`"
            ) from exc
        raise
    return XGBClassifier(**parameters)


def model_json_bytes(model: Any) -> bytes:
    payload = model.save_raw(raw_format="json")
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("model save_raw must return bytes")
    return bytes(payload)
