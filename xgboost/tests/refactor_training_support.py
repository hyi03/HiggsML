from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

from src.preprocessing.pipeline import OUTPUT_COLUMNS
from src.training.folds import development_fold


_VALID_MODEL_BYTES: bytes | None = None
_DEVELOPMENT_TEMPLATE: dict[str, bytes] | None = None


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


def test_frame(rows_per_class: int = 6) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for label, channel in ((0, 363490), (1, 345060)):
        for rank in range(rows_per_class):
            value = label * 5.0 + rank * 0.03
            row = {
                name: value + index * 0.001
                for index, name in enumerate(OUTPUT_COLUMNS[:19])
            }
            row.update(
                m4l=118.0 + label * 10.0 + rank * 0.2,
                label=label,
                split="test",
                physical_weight=(-1.0 if rank == 0 else 1.0 + rank),
                train_weight=1.0,
                channelNumber=channel,
                eventNumber=10_000 + rank,
                runNumber=1,
                mcWeight=1.0,
                xsec=0.5,
                kfac=1.0,
                filteff=1.0,
                sum_of_weights=100.0,
            )
            rows.append(row)
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def write_preprocess_run(
    root: Path,
    frame: pd.DataFrame | None = None,
    *,
    valid_test: bool = False,
) -> Path:
    run = root / "preprocess-input"
    (run / "processed").mkdir(parents=True)
    (run / "artifacts").mkdir()
    source = development_frame() if frame is None else frame
    canonical = source.to_csv(index=False, lineterminator="\n").encode("utf-8")
    compressed = gzip.compress(canonical, compresslevel=9, mtime=0)
    (run / "processed" / "development.csv.gz").write_bytes(compressed)
    if valid_test:
        held_out = test_frame()
        test_canonical = held_out.to_csv(index=False, lineterminator="\n").encode("utf-8")
        test_compressed = gzip.compress(test_canonical, compresslevel=9, mtime=0)
    else:
        held_out = None
        test_canonical = b""
        # Deliberately invalid: develop must never read it.
        test_compressed = b"forbidden held-out test"
    (run / "processed" / "test.csv.gz").write_bytes(test_compressed)
    project = Path(__file__).resolve().parents[1]
    preprocessing_protocol = project / "config/preprocessing_protocol_v1.yaml"
    preprocessing_protocol_bytes = preprocessing_protocol.read_bytes()
    manifest = {
        "schema_version": "1.0",
        "run_type": "mc_preprocessing",
        "status": "succeeded",
        "created_at_utc": "2026-09-02T00:00:00+00:00",
        "protocol": {
            "path": (
                str(preprocessing_protocol)
                if valid_test
                else "preprocessing_protocol_v1.yaml"
            ),
            "schema_version": "1.0",
            "sha256": (
                hashlib.sha256(preprocessing_protocol_bytes).hexdigest()
                if valid_test
                else "a" * 64
            ),
        },
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
                "rows": len(held_out) if held_out is not None else 1,
                "columns": list(source.columns),
                "sha256_compressed": (
                    hashlib.sha256(test_compressed).hexdigest()
                    if valid_test
                    else "e" * 64
                ),
                "sha256_canonical_csv": (
                    hashlib.sha256(test_canonical).hexdigest()
                    if valid_test
                    else "f" * 64
                ),
                "size_bytes": len(test_compressed),
            },
            "cutflow": "artifacts/cutflow.json",
            "mc_summary": "artifacts/mc_summary.json",
        },
        "counts": {
            "development": len(source),
            "test": len(held_out) if held_out is not None else 1,
            "total": len(source) + (len(held_out) if held_out is not None else 1),
        },
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


def write_eligible_development_run(root: Path) -> tuple[Path, Path]:
    frame = development_frame()
    frame["m4l"] = 125.0
    input_run = write_preprocess_run(root, frame, valid_test=True)
    runs = root / "runs"
    runs.mkdir()
    development = runs / "development"

    global _DEVELOPMENT_TEMPLATE
    if _DEVELOPMENT_TEMPLATE is not None:
        development.mkdir()
        for relative, content in _DEVELOPMENT_TEMPLATE.items():
            if relative == "artifacts/manifest.json":
                continue
            destination = development / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        manifest = json.loads(_DEVELOPMENT_TEMPLATE["artifacts/manifest.json"])
        preprocess_manifest = (input_run / "artifacts/manifest.json").read_bytes()
        manifest["upstream_run"]["path"] = str(input_run.resolve(strict=True))
        manifest["upstream_run"]["manifest"]["sha256"] = hashlib.sha256(
            preprocess_manifest
        ).hexdigest()
        manifest_path = development / "artifacts/manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return input_run, development

    from src.training.trainer import run_development

    project = Path(__file__).resolve().parents[1]
    run_development(
        input_run=input_run,
        protocol_path=project / "config/xgboost_protocol_v1.yaml",
        run_dir=development,
        model_factory=fake_factory,
    )

    global _VALID_MODEL_BYTES
    if _VALID_MODEL_BYTES is None:
        source_path = input_run / "processed/development.csv.gz"
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import pandas as pd, sys; "
                    "from xgboost import XGBClassifier; "
                    "frame=pd.read_csv(sys.argv[1]); features=list(frame.columns[:19]); "
                    "model=XGBClassifier(n_estimators=4,max_depth=1,n_jobs=1,random_state=20260826); "
                    "model.fit(frame.loc[:,features],frame['label']); model.save_model(sys.argv[2])"
                ),
                str(source_path),
                str(development / "model/model.json"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        _VALID_MODEL_BYTES = (development / "model/model.json").read_bytes()
    model_path = development / "model/model.json"
    model_path.write_bytes(_VALID_MODEL_BYTES)
    model_bytes = _VALID_MODEL_BYTES
    manifest_path = development / "artifacts/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outputs"]["model"] = {
        "path": "model/model.json",
        "sha256": hashlib.sha256(model_bytes).hexdigest(),
        "size_bytes": len(model_bytes),
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    _DEVELOPMENT_TEMPLATE = {
        path.relative_to(development).as_posix(): path.read_bytes()
        for path in development.rglob("*")
        if path.is_file()
    }
    return input_run, development
