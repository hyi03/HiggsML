from __future__ import annotations

import json
from pathlib import Path

from .features import FEATURES, assert_no_feature_leakage
from .progress import TrainingProgress
from .validation import evaluate_scored_events


OVERFITTING_FIELDS = [
    "train_auc",
    "validation_auc",
    "test_auc",
    "train_test_auc_gap",
    "validation_test_auc_gap",
    "signal_ks_distance",
    "background_ks_distance",
    "auc_gap_limit",
    "ks_distance_limit",
    "overfitting_warning",
    "overfitting_warning_reasons",
]


def build_training_progress(parameters: dict, progress_factory=None) -> TrainingProgress:
    total_rounds = int(parameters["n_estimators"])
    if progress_factory is None:
        return TrainingProgress(total_rounds)
    return TrainingProgress(total_rounds, progress_factory=progress_factory)


def persist_validation_reports(metrics: dict, output_dir: str | Path) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    overfitting = {field: metrics[field] for field in OVERFITTING_FIELDS}
    (output_dir / "overfitting_check.json").write_text(
        json.dumps(overfitting, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def train_xgboost(frame, output_dir: str | Path, parameters: dict | None = None):
    try:
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise RuntimeError("install requirements.txt before training") from exc
    except Exception as exc:
        if "libomp" in str(exc).lower():
            raise RuntimeError(
                "XGBoost requires the OpenMP runtime on macOS; "
                "install it with `brew install libomp`, then retry"
            ) from exc
        raise

    assert_no_feature_leakage()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    parameters = parameters or {}
    defaults = {
        "n_estimators": 300,
        "max_depth": 3,
        "learning_rate": 0.05,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 2.0,
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "random_state": 42,
        "n_jobs": 1,
    }
    defaults.update(parameters)
    progress = build_training_progress(defaults)
    defaults["callbacks"] = [progress]
    model = XGBClassifier(**defaults)

    train = frame[frame["split"] == "train"]
    validation = frame[frame["split"] == "validation"]
    test = frame[frame["split"] == "test"]
    try:
        model.fit(
            train[FEATURES],
            train["label"],
            sample_weight=train["train_weight"],
            eval_set=[(validation[FEATURES], validation["label"])],
            verbose=False,
        )
    finally:
        progress.close()
    model.save_model(output_dir / "xgboost_demo.json")
    evaluated = frame.copy()
    evaluated["xgb_score"] = model.predict_proba(evaluated[FEATURES])[:, 1]
    validation_metrics = evaluate_scored_events(evaluated)
    metrics = {
        "features": FEATURES,
        "train_events": int(len(train)),
        "validation_events": int(len(validation)),
        "test_events": int(len(test)),
        **validation_metrics,
    }
    persist_validation_reports(metrics, output_dir)
    return model, evaluated, metrics
