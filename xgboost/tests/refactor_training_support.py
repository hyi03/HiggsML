from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.full_training_policy import development_fold
from src.preprocessing.pipeline import OUTPUT_COLUMNS


def development_frame(rows_per_class_fold: int = 3) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for label, channel in ((0, 363490), (1, 345060)):
        found = {fold: 0 for fold in range(5)}
        event = 1
        while any(count < rows_per_class_fold for count in found.values()):
            fold = development_fold(channel, event, 5)
            if found[fold] < rows_per_class_fold:
                rank = found[fold]
                value = label * 5.0 + fold * 0.2 + rank * 0.03
                row = {name: value + index * 0.001 for index, name in enumerate(OUTPUT_COLUMNS[:19])}
                row.update(
                    m4l=125.0 + fold * 0.1,
                    label=label,
                    split="train" if rank % 2 == 0 else "validation",
                    physical_weight=(-1.0 if rank == 0 else 1.0 + rank),
                    train_weight=1.0,
                    channelNumber=channel,
                    eventNumber=event,
                    runNumber=1,
                    mcWeight=1.0,
                    xsec=0.5,
                    kfac=1.0,
                    filteff=1.0,
                    sum_of_weights=100.0,
                )
                rows.append(row)
                found[fold] += 1
            event += 1
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def write_preprocess_run(root: Path, frame: pd.DataFrame | None = None) -> Path:
    run = root / "preprocess-input"
    (run / "processed").mkdir(parents=True)
    (run / "artifacts").mkdir()
    source = development_frame() if frame is None else frame
    canonical = source.to_csv(index=False, lineterminator="\n").encode("utf-8")
    compressed = gzip.compress(canonical, compresslevel=9, mtime=0)
    (run / "processed" / "development.csv.gz").write_bytes(compressed)
    # Deliberately invalid: develop must never read it.
    (run / "processed" / "test.csv.gz").write_bytes(b"forbidden held-out test")
    manifest = {
        "schema_version": "1.0",
        "run_type": "mc_preprocessing",
        "status": "succeeded",
        "created_at_utc": "2026-09-02T00:00:00+00:00",
        "protocol": {"path": "preprocessing_protocol_v1.yaml", "schema_version": "1.0", "sha256": "a" * 64},
        "run_config": {"path": "local.yaml", "sha256": "b" * 64},
        "code": {"commit": "c" * 40, "worktree_dirty": False, "sha256": "d" * 64},
        "software": {"python": "3.12"},
        "luminosity_pb": 10_000.0,
        "inputs": {},
        "outputs": {
            "development": {
                "path": "processed/development.csv.gz",
                "rows": len(source),
                "columns": list(source.columns),
                "sha256_compressed": hashlib.sha256(compressed).hexdigest(),
                "sha256_canonical_csv": hashlib.sha256(canonical).hexdigest(),
                "size_bytes": len(compressed),
            },
            "test": {
                "path": "processed/test.csv.gz",
                "rows": 1,
                "columns": list(source.columns),
                "sha256_compressed": "e" * 64,
                "sha256_canonical_csv": "f" * 64,
                "size_bytes": len(b"forbidden held-out test"),
            },
            "cutflow": "artifacts/cutflow.json",
            "mc_summary": "artifacts/mc_summary.json",
        },
        "counts": {"development": len(source), "test": 1, "total": len(source) + 1},
        "schema": {
            "model_features": list(OUTPUT_COLUMNS[:19]),
            "columns": list(OUTPUT_COLUMNS),
            "forbidden_model_features": [
                "m4l", "label", "split", "physical_weight", "train_weight",
                "channelNumber", "eventNumber", "runNumber", "mcWeight",
                "xsec", "kfac", "filteff", "sum_of_weights",
            ],
        },
    }
    (run / "artifacts" / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    return run


class FakeClassifier:
    def __init__(self, **parameters: object) -> None:
        self.parameters = parameters
        self.best_iteration = 3
        self.fit_weight: np.ndarray | None = None

    def fit(self, features, labels, *, sample_weight, **kwargs):
        self.fit_weight = np.asarray(sample_weight, dtype=float)
        return self

    def predict_proba(self, features):
        first = np.asarray(features.iloc[:, 0], dtype=float)
        score = 1.0 / (1.0 + np.exp(-(first - 2.5)))
        return np.column_stack((1.0 - score, score))

    def save_raw(self, *, raw_format: str):
        assert raw_format == "json"
        return b'{"fake":"xgboost-json"}'


def fake_factory(**parameters: object) -> FakeClassifier:
    return FakeClassifier(**parameters)
