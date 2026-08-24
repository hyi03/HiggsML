"""Development-only KNN-flatness training primitives."""

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


def _default_model_factory(**kwargs):
    from hep_ml.gradientboosting import UGradientBoostingClassifier

    return UGradientBoostingClassifier(**kwargs)


def _score_column(coefficient: float) -> str:
    return f"score_lambda_{coefficient:.1f}".replace(".", "p")


def build_flatness_model(
    config: DecorrelationConfig,
    coefficient: float,
    model_factory: Callable[..., Any] | None = None,
):
    from hep_ml.losses import KnnFlatnessLossFunction

    normalized = float(coefficient)
    if normalized not in config.coefficients:
        raise ValueError("flatness coefficient is not a frozen candidate")
    if tuple(config.features) != DROP_TOP4_FEATURES:
        raise ValueError("decorrelation features do not match DropTop4")

    loss = KnnFlatnessLossFunction(
        uniform_features=[config.flatness["uniform_feature"]],
        uniform_label=[config.flatness["uniform_label"]],
        n_neighbours=config.flatness["n_neighbours"],
        max_groups=config.flatness["max_groups"],
        power=config.flatness["power"],
        fl_coefficient=normalized,
        allow_wrong_signs=config.flatness["allow_wrong_signs"],
        random_state=config.model["random_seed"],
    )
    factory = model_factory or _default_model_factory
    return factory(
        loss=loss,
        n_estimators=config.model["n_estimators"],
        learning_rate=config.model["learning_rate"],
        max_depth=config.model["max_depth"],
        min_samples_leaf=config.model["min_samples_leaf"],
        subsample=config.model["subsample"],
        train_features=list(DROP_TOP4_FEATURES),
        random_state=config.model["random_seed"],
    )


def generate_flatness_oof(
    development: pd.DataFrame,
    config: DecorrelationConfig,
    coefficient: float,
    model_factory: Callable[..., Any] | None = None,
) -> pd.DataFrame:
    validate_development_frame(development)
    folds = assign_development_folds(development, folds=config.folds)
    score_column = _score_column(float(coefficient))
    scores = pd.Series(np.nan, index=development.index, dtype=float)
    model_columns = [*DROP_TOP4_FEATURES, "m4l"]

    for fold in range(config.folds):
        fit_mask = folds != fold
        evaluation_mask = folds == fold
        fitting = development.loc[fit_mask]
        evaluation = development.loc[evaluation_mask]
        weights = class_balanced_training_weights(fitting)
        model = build_flatness_model(
            config, coefficient, model_factory=model_factory
        )
        model.fit(
            fitting.loc[:, model_columns],
            fitting["label"],
            sample_weight=weights,
        )
        probabilities = np.asarray(
            model.predict_proba(evaluation.loc[:, model_columns]), dtype=float
        )
        if probabilities.shape != (len(evaluation), 2):
            raise ValueError("flatness model probabilities have an invalid shape")
        fold_scores = probabilities[:, 1]
        if not np.isfinite(fold_scores).all():
            raise ValueError("flatness model produced non-finite OOF scores")
        scores.loc[evaluation.index] = fold_scores

    if scores.isna().any() or not np.isfinite(scores.to_numpy()).all():
        raise RuntimeError("every development row must receive one finite OOF score")

    audit_columns = [
        "eventNumber",
        "channelNumber",
        "label",
        "split",
        "physical_weight",
        "m4l",
    ]
    output = development.loc[:, audit_columns].copy()
    output["development_fold"] = folds
    output[score_column] = scores
    return output.loc[development.index]
