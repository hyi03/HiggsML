from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.experiment_config import ExperimentOverrides, load_experiment_config
from src.experiment_runner import (
    TRAIN_ROLE,
    OutputTransaction,
    run_prediction,
    run_test_evaluation,
    run_training,
    train_experiment,
)
from src.features import FEATURES
from src.full_training_policy import development_fold


def _frame(rows_per_fold: int = 2) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    counts = {(fold, label): 0 for fold in range(5) for label in (0, 1)}
    event = 1
    while min(counts.values()) < rows_per_fold:
        for label in (0, 1):
            channel = 345060 if label else 363490
            fold = development_fold(channel, event, 5)
            if counts[(fold, label)] >= rows_per_fold:
                event += 1
                continue
            rows.append(
                {
                    **{
                        name: float(label * 10 + offset + event / 10000)
                        for offset, name in enumerate(FEATURES)
                    },
                    "m4l": float(110 + event % 40),
                    "channelNumber": channel,
                    "eventNumber": event,
                    "split": (
                        "train" if counts[(fold, label)] % 2 == 0 else "validation"
                    ),
                    "label": label,
                    "physical_weight": -2.0 if event % 7 == 0 else 1.0 + label,
                }
            )
            counts[(fold, label)] += 1
            event += 1
    for label in (0, 1):
        rows.append(
            {
                **{name: float(label * 10 + offset) for offset, name in enumerate(FEATURES)},
                "m4l": 125.0,
                "channelNumber": 345060 if label else 363490,
                "eventNumber": event,
                "split": "test",
                "label": label,
                "physical_weight": 1.0,
            }
        )
        event += 1
    return pd.DataFrame(rows)


class RecordingModel:
    def __init__(self, records: list[dict[str, object]], **parameters: object):
        self.records = records
        self.parameters = parameters
        self.best_iteration = 2

    def fit(self, x, y, **kwargs):
        self.records.append(
            {
                "indices": tuple(x.index),
                "columns": tuple(x.columns),
                "parameters": dict(self.parameters),
                "labels": tuple(y),
                **kwargs,
            }
        )
        return self

    def predict_proba(self, x):
        score = np.where(x.iloc[:, 0].to_numpy(dtype=float) > 5, 0.9, 0.1)
        return np.column_stack([1.0 - score, score])


class RecordingProgressBar:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.n = 0
        self.closed = False

    def update(self, amount):
        self.n += amount

    def set_postfix(self, values, refresh=False):
        pass

    def close(self):
        self.closed = True


def test_training_grid_never_fits_or_scores_test_and_uses_fixed_feature_order():
    config = load_experiment_config(
        None,
        ExperimentOverrides(
            feature_toggles=(("lep4_pt", False),),
            grid={"max_depth": (2, 3)},
            scalars={"n_estimators": 8, "early_stopping_rounds": 2},
        ),
    )
    frame = _frame()
    records: list[dict[str, object]] = []

    outcome = train_experiment(
        frame,
        config,
        model_factory=lambda **parameters: RecordingModel(records, **parameters),
    )

    test_indices = set(frame.index[frame["split"] == "test"])
    assert len(outcome.candidates) == 2
    assert outcome.selected.index == 0
    assert outcome.metrics["test_opened"] is False
    assert len(outcome.oof_frame) == len(frame) - len(test_indices)
    assert all(not (set(record["indices"]) & test_indices) for record in records)
    assert all(record["columns"] == config.features for record in records)
    assert "eval_set" not in records[-1]

    final_labels = np.asarray(records[-1]["labels"], dtype=int)
    final_weights = np.asarray(records[-1]["sample_weight"], dtype=float)
    assert final_weights[final_labels == 0].sum() == pytest.approx(
        final_weights[final_labels == 1].sum()
    )


def test_real_xgboost_training_reports_each_fold_and_final_fit_progress(tmp_path):
    root = tmp_path / "project"
    (root / "runs").mkdir(parents=True)
    source = root / "mc.csv.gz"
    _frame().to_csv(source, index=False)
    config = load_experiment_config(
        None,
        ExperimentOverrides(
            grid={
                "max_depth": (2,),
                "learning_rate": (0.2,),
                "min_child_weight": (1.0,),
            },
            scalars={
                "n_estimators": 3,
                "early_stopping_rounds": 1,
                "n_jobs": 1,
            },
        ),
    )
    bars = []

    def progress_factory(**kwargs):
        bar = RecordingProgressBar(**kwargs)
        bars.append(bar)
        return bar

    run_training(
        input_path=source,
        output_dir=root / "runs" / "training",
        config=config,
        project_root=root,
        show_progress=True,
        progress_factory=progress_factory,
    )

    assert [bar.kwargs["desc"] for bar in bars] == [
        "Candidate 1/1 fold 1/5",
        "Candidate 1/1 fold 2/5",
        "Candidate 1/1 fold 3/5",
        "Candidate 1/1 fold 4/5",
        "Candidate 1/1 fold 5/5",
        "Final model",
    ]
    assert [bar.kwargs["leave"] for bar in bars] == [False] * 5 + [True]
    assert all(0 < bar.n <= bar.kwargs["total"] for bar in bars)
    assert all(bar.closed for bar in bars)


def test_output_transaction_refuses_unknown_overwrite_and_protected_paths(tmp_path):
    root = tmp_path / "project"
    (root / "runs").mkdir(parents=True)
    (root / "src").mkdir()
    unknown = root / "runs" / "unknown"
    unknown.mkdir()
    (unknown / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="recognized"):
        with OutputTransaction(unknown, overwrite=True, project_root=root):
            pass
    assert (unknown / "keep.txt").read_text(encoding="utf-8") == "keep"

    with pytest.raises(ValueError, match="protected"):
        with OutputTransaction(root / "src" / "out", overwrite=False, project_root=root):
            pass


def test_training_refuses_existing_output_before_reading_input(tmp_path, monkeypatch):
    root = tmp_path / "project"
    output = root / "runs" / "existing"
    output.mkdir(parents=True)
    source = root / "mc.csv.gz"
    source.write_bytes(b"not read")
    reads = []
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: reads.append(args))

    with pytest.raises(FileExistsError, match="already exists"):
        run_training(
            input_path=source,
            output_dir=output,
            config=load_experiment_config(None),
            project_root=root,
        )

    assert reads == []


def test_output_transaction_atomically_replaces_only_generic_output(tmp_path):
    root = tmp_path / "project"
    target = root / "runs" / "experiment"
    target.mkdir(parents=True)
    (target / "manifest.json").write_text(
        json.dumps(
            {"schema_version": "1.0", "status": "complete", "role": TRAIN_ROLE}
        ),
        encoding="utf-8",
    )
    (target / "old.txt").write_text("old", encoding="utf-8")

    with OutputTransaction(target, overwrite=True, project_root=root) as staging:
        (staging / "new.txt").write_text("new", encoding="utf-8")

    assert not (target / "old.txt").exists()
    assert (target / "new.txt").read_text(encoding="utf-8") == "new"


def _model_run(path: Path, features: tuple[str, ...]) -> None:
    path.mkdir(parents=True)
    model = path / "model.json"
    model.write_bytes(b"fixed model")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    manifest = {
        "schema_version": "1.0",
        "status": "complete",
        "role": TRAIN_ROLE,
        "feature_profile": "base14",
        "features": list(features),
        "working_points": {"loose": {"threshold": 0.2}},
        "outputs": {
            "model.json": {
                "path": "model.json",
                "size_bytes": model.stat().st_size,
                "sha256": digest,
            }
        },
    }
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class FixedModel:
    def predict_proba(self, x):
        score = np.where(x.iloc[:, 0].to_numpy(dtype=float) > 5, 0.8, 0.2)
        return np.column_stack([1.0 - score, score])


def test_predict_uses_manifest_features_and_rejects_test_rows(tmp_path, monkeypatch):
    import src.experiment_runner as runner

    root = tmp_path / "project"
    model_dir = root / "runs" / "model"
    _model_run(model_dir, ("lep1_pt", "lep2_pt"))
    monkeypatch.setattr(runner, "_load_model", lambda path: FixedModel())
    source = root / "prediction.csv.gz"
    pd.DataFrame({"lep2_pt": [2.0], "lep1_pt": [10.0], "split": ["validation"]}).to_csv(
        source, index=False
    )

    output = root / "runs" / "prediction"
    run_prediction(
        input_path=source,
        model_dir=model_dir,
        output_dir=output,
        project_root=root,
    )
    scored = pd.read_csv(output / "predictions.csv.gz")
    assert scored["xgb_score"].tolist() == pytest.approx([0.8])

    pd.DataFrame({"lep1_pt": [1.0], "lep2_pt": [2.0], "split": ["test"]}).to_csv(
        source, index=False
    )
    with pytest.raises(ValueError, match="evaluate-test"):
        run_prediction(
            input_path=source,
            model_dir=model_dir,
            output_dir=root / "runs" / "refused",
            project_root=root,
        )


def test_predict_rejects_manifest_feature_leakage(tmp_path):
    root = tmp_path / "project"
    model_dir = root / "runs" / "model"
    _model_run(model_dir, ("m4l",))
    source = root / "prediction.csv.gz"
    pd.DataFrame({"m4l": [125.0]}).to_csv(source, index=False)

    with pytest.raises(ValueError, match="ordered profile subset"):
        run_prediction(
            input_path=source,
            model_dir=model_dir,
            output_dir=root / "runs" / "refused",
            project_root=root,
        )


def test_evaluate_test_scores_only_test_rows(tmp_path, monkeypatch):
    import src.experiment_runner as runner

    root = tmp_path / "project"
    model_dir = root / "runs" / "model"
    _model_run(model_dir, tuple(FEATURES))
    monkeypatch.setattr(runner, "_load_model", lambda path: FixedModel())
    monkeypatch.setattr(runner, "_save_test_plots", lambda *args: None)
    source = root / "mc.csv.gz"
    frame = _frame()
    frame.to_csv(source, index=False)
    output = root / "runs" / "test-evaluation"

    run_test_evaluation(
        input_path=source,
        model_dir=model_dir,
        output_dir=output,
        project_root=root,
    )

    scored = pd.read_csv(output / "test_scores.csv.gz")
    assert set(scored["split"]) == {"test"}
    assert len(scored) == 2
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["weighted_auc"] == pytest.approx(1.0)


def test_real_xgboost_train_predict_and_test_evaluation_end_to_end(tmp_path):
    root = tmp_path / "project"
    (root / "runs").mkdir(parents=True)
    source = root / "mc.csv.gz"
    frame = _frame(rows_per_fold=3)
    frame.to_csv(source, index=False)
    config = load_experiment_config(
        None,
        ExperimentOverrides(
            grid={
                "max_depth": (2,),
                "learning_rate": (0.2,),
                "min_child_weight": (1.0,),
            },
            scalars={
                "n_estimators": 6,
                "early_stopping_rounds": 2,
                "n_jobs": 1,
            },
        ),
    )
    training = root / "runs" / "training"

    run_training(
        input_path=source,
        output_dir=training,
        config=config,
        project_root=root,
    )

    assert (training / "model.json").stat().st_size > 0
    training_manifest = json.loads(
        (training / "manifest.json").read_text(encoding="utf-8")
    )
    assert training_manifest["test_opened"] is False
    assert training_manifest["features"] == list(FEATURES)

    prediction_input = root / "prediction.csv.gz"
    frame.loc[frame["split"] == "validation"].to_csv(prediction_input, index=False)
    prediction = root / "runs" / "prediction"
    run_prediction(
        input_path=prediction_input,
        model_dir=training,
        output_dir=prediction,
        project_root=root,
    )
    assert np.isfinite(
        pd.read_csv(prediction / "predictions.csv.gz")["xgb_score"]
    ).all()

    evaluation = root / "runs" / "evaluation"
    run_test_evaluation(
        input_path=source,
        model_dir=training,
        output_dir=evaluation,
        project_root=root,
    )
    assert len(pd.read_csv(evaluation / "test_scores.csv.gz")) == 2
