from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from .decorrelation_training_run import DecorrelationConfig
from .full_training_policy import (
    assign_development_folds,
    class_balanced_training_weights,
    validate_development_frame,
)


DROP_TOP4_FEATURES = (
    "lep1_pt",
    "lep2_pt",
    "lep1_eta",
    "lep2_eta",
    "lep3_eta",
    "lep4_eta",
    "pt4l",
    "deltaR_Z1",
    "deltaR_Z2",
    "deltaPhi_ZZ",
)

ModelFactory = Callable[..., Any]


def _default_model_factory(**kwargs):
    try:
        from hep_ml.gradientboosting import UGradientBoostingClassifier
    except ImportError as exc:
        raise RuntimeError("install requirements.txt before training") from exc
    return UGradientBoostingClassifier(**kwargs)


def build_flatness_model(
    config: DecorrelationConfig,
    coefficient: float,
    model_factory: ModelFactory | None = None,
) -> Any:
    if coefficient not in config.coefficients:
        raise ValueError("coefficient must match an approved flatness value")
    if config.features != DROP_TOP4_FEATURES:
        raise ValueError("decorrelation config must retain the approved DropTop4 features")
    try:
        from hep_ml.losses import KnnFlatnessLossFunction
    except ImportError as exc:
        raise RuntimeError("install requirements.txt before training") from exc
    loss = KnnFlatnessLossFunction(
        uniform_features=[str(config.flatness["uniform_feature"])],
        uniform_label=[int(config.flatness["uniform_label"])],
        n_neighbours=int(config.flatness["n_neighbours"]),
        max_groups=int(config.flatness["max_groups"]),
        power=float(config.flatness["power"]),
        fl_coefficient=float(coefficient),
        allow_wrong_signs=bool(config.flatness["allow_wrong_signs"]),
    )
    factory = _default_model_factory if model_factory is None else model_factory
    return factory(
        loss=loss,
        n_estimators=300,
        learning_rate=0.05,
        max_depth=3,
        min_samples_leaf=50,
        subsample=0.8,
        train_features=list(DROP_TOP4_FEATURES),
        random_state=42,
    )


def generate_flatness_oof(
    development: pd.DataFrame,
    config: DecorrelationConfig,
    coefficient: float,
    model_factory: ModelFactory | None = None,
) -> pd.DataFrame:
    if not development.index.is_unique:
        raise ValueError("out-of-fold scoring requires a unique DataFrame index")
    validate_development_frame(development)
    development_folds = assign_development_folds(development, folds=config.folds)
    fitting_columns = [*DROP_TOP4_FEATURES, "m4l"]
    score_column = _score_column_name(coefficient)
    scores = pd.Series(np.nan, index=development_folds.index, dtype=float, name=score_column)

    for fold in range(config.folds):
        fitting = development.loc[development_folds != fold]
        evaluation = development.loc[development_folds == fold]
        if fitting.empty or evaluation.empty:
            raise ValueError(f"development fold {fold} has no fitting or evaluation rows")
        model = build_flatness_model(
            config, coefficient, model_factory=model_factory
        )
        weights = class_balanced_training_weights(fitting)
        model.fit(
            fitting.loc[:, fitting_columns],
            fitting["label"],
            sample_weight=weights,
        )
        fold_scores = _positive_class_probabilities(model.predict_proba(evaluation.loc[:, fitting_columns]))
        if len(fold_scores) != len(evaluation):
            raise ValueError("classifier returned the wrong number of evaluation scores")
        if scores.loc[evaluation.index].notna().any():
            raise ValueError("out-of-fold predictions overlap")
        scores.loc[evaluation.index] = fold_scores

    if scores.isna().any() or not scores.index.equals(development_folds.index):
        raise ValueError(
            "out-of-fold predictions must cover every development event exactly once"
        )
    columns = [
        "eventNumber",
        "channelNumber",
        "split",
        "label",
        "physical_weight",
        "m4l",
    ]
    output = development.loc[development_folds.index, columns].copy(deep=True)
    output["development_fold"] = development_folds.loc[output.index].to_numpy(dtype=int)
    output[score_column] = scores.loc[output.index].to_numpy(dtype=float)
    return output


def _positive_class_probabilities(predicted: object) -> np.ndarray:
    values = np.asarray(predicted, dtype=float)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("classifier predict_proba must return two class probabilities")
    if not np.isfinite(values).all():
        raise ValueError("classifier returned non-finite evaluation scores")
    scores = values[:, 1]
    return scores


def _score_column_name(coefficient: float) -> str:
    return f"score_lambda_{str(float(coefficient)).replace('.', 'p')}"
