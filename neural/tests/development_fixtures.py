from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import pandas as pd

from src.artifacts.manifest import sha256_file, write_json
from src.preprocessing.outputs import canonical_csv_bytes
from src.training.config import INPUT_COLUMNS
from src.training.dataset import FEATURE_COLUMNS
from src.training.folds import fold_index_for_identity
from tests.training_fixtures import synthetic_development_frame


def development_with_test_rows() -> pd.DataFrame:
    base = synthetic_development_frame()
    copies = []
    used_identities: set[tuple[str, int]] = set()
    for repeat in range(5):
        current = base.copy(deep=True)
        assigned_entries: list[int] = []
        for row in current.itertuples(index=False):
            sample = str(row.source_sample)
            candidate = repeat * 1_000_000 + int(row.source_entry) * 10
            while (
                (sample, candidate) in used_identities
                or fold_index_for_identity(sample, candidate) != repeat
            ):
                candidate += 1
            used_identities.add((sample, candidate))
            assigned_entries.append(candidate)
        current["source_entry"] = assigned_entries
        current["runNumber"] = 1_000 + current["source_entry"]
        current["eventNumber"] = 2_000 + current["source_entry"]
        copies.append(current)
    development = pd.concat(copies, ignore_index=True)
    for index, feature in enumerate(FEATURE_COLUMNS):
        development[feature] = (
            development["label"].astype("float64") * 10.0 + index / 100.0
        )
    held_out = pd.concat(
        [
            development.loc[development["label"] == 0].iloc[:3],
            development.loc[development["label"] == 1].iloc[:3],
        ],
        ignore_index=True,
    ).copy(deep=True)
    held_out["split"] = "test"
    held_out["source_entry"] = held_out["source_entry"] + 100_000
    held_out["runNumber"] = held_out["runNumber"] + 100_000
    held_out["eventNumber"] = held_out["eventNumber"] + 100_000
    return pd.concat([development, held_out], ignore_index=True)[list(INPUT_COLUMNS)]


def write_synthetic_preprocess_run(
    allowed_root: Path, *, poison_test_feature: bool = False
) -> tuple[Path, pd.DataFrame]:
    run = allowed_root / "preprocess-synthetic"
    (run / "processed").mkdir(parents=True)
    (run / "artifacts").mkdir()
    frame = development_with_test_rows()
    payload = canonical_csv_bytes(
        frame,
        INPUT_COLUMNS,
        integer_columns={"label", "source_entry", "runNumber", "eventNumber", "channelNumber"},
        string_columns={"split", "source_sample"},
        string_enums={
            "split": {"train", "validation", "test"},
            "source_sample": {"higgs_345060", "zz_363490"},
        },
    )
    if poison_test_feature:
        lines = payload.splitlines(keepends=True)
        split_index = INPUT_COLUMNS.index("split")
        for index, line in enumerate(lines[1:], start=1):
            tokens = line.rstrip(b"\n").split(b",")
            if tokens[split_index] == b"test":
                tokens[0] = b"this-test-feature-must-never-be-decoded"
                lines[index] = b",".join(tokens) + b"\n"
                break
        payload = b"".join(lines)
    compressed = gzip.compress(payload, compresslevel=9, mtime=0)
    table = run / "processed" / "mc_events.csv.gz"
    table.write_bytes(compressed)
    (run / "config.yaml").write_text("schema_version: fixture\n", encoding="utf-8")
    write_json(run / "artifacts" / "cutflow.json", {"schema_version": "fixture"})
    write_json(run / "artifacts" / "mc_summary.json", {"schema_version": "fixture"})

    outputs = []
    for relative in (
        "config.yaml",
        "processed/mc_events.csv.gz",
        "artifacts/cutflow.json",
        "artifacts/mc_summary.json",
    ):
        path = run / relative
        outputs.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "row_count": len(frame) if relative == "processed/mc_events.csv.gz" else None,
                "canonical_content_sha256": hashlib.sha256(payload).hexdigest()
                if relative == "processed/mc_events.csv.gz"
                else None,
            }
        )
    write_json(
        run / "artifacts" / "manifest.json",
        {
            "schema_version": "1.0",
            "status": "success",
            "run_type": "preprocess",
            "protocol_id": "higgsml-preprocess-v1",
            "started_at_utc": "2026-09-02T00:00:00Z",
            "completed_at_utc": "2026-09-02T00:00:01Z",
            "inputs": [],
            "configuration": {
                "protocol_path": "config/preprocess_protocol_v1.yaml",
                "protocol_sha256": "1" * 64,
                "run_config_path": "config/preprocess_synthetic.yaml",
                "run_config_sha256": "2" * 64,
                "chunk_size_events": 64,
                "full_read": True,
            },
            "outputs": outputs,
            "schema": {
                "ordered_columns": list(INPUT_COLUMNS),
                "dtypes": {name: str(frame[name].dtype) for name in INPUT_COLUMNS},
            },
            "counts": {
                "totals": {
                    "selected_count": len(frame),
                    "split_counts": {
                        name: int((frame["split"] == name).sum())
                        for name in ("train", "validation", "test")
                    },
                }
            },
            "software": {},
            "platform": {},
            "determinism": {},
            "performance": {},
        },
    )
    return run, frame
