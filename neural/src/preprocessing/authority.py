from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.artifacts.manifest import json_bytes, sha256_file
from src.config import InputBindingError, load_preprocess_protocol
from src.domain.selection import STAGES


INTEGER_COLUMNS = {"label", "source_entry", "runNumber", "eventNumber", "channelNumber"}
STRING_COLUMNS = {"split", "source_sample", "source_file_id", "event_group_id"}
FLOAT_CUTFLOW_FIELDS = (
    "efficiency_previous", "efficiency_read", "signed_weighted_yield",
    "absolute_weighted_yield",
)


class AuthorityGateError(InputBindingError):
    """Raised when the locked ARM64 authority gate cannot prove equivalence."""


def require_authority_platform() -> None:
    if platform.system() != "Darwin" or platform.machine().lower() not in {
        "arm64", "aarch64"
    }:
        raise AuthorityGateError(
            "authoritative_gate_not_run: native osx-arm64 is required"
        )


def compare_tables(
    new_table: Path,
    golden_table: Path,
    ordered_columns: tuple[str, ...],
    *,
    rtol: float,
    atol: float,
) -> int:
    new = pd.read_csv(new_table)
    golden = pd.read_csv(golden_table)
    if tuple(new.columns) != ordered_columns:
        raise AuthorityGateError("new table columns/order differ from the sealed schema")
    missing = set(ordered_columns) - set(golden.columns)
    if missing:
        raise AuthorityGateError(f"golden table lacks compared columns: {sorted(missing)}")
    golden = golden.loc[:, ordered_columns]
    if len(new) != len(golden):
        raise AuthorityGateError("table row count differs from golden")
    for column in ordered_columns:
        if column in INTEGER_COLUMNS:
            left = new[column].to_numpy()
            right = golden[column].to_numpy()
            if not np.array_equal(left, right):
                raise AuthorityGateError(f"exact integer mismatch: {column}")
        elif column in STRING_COLUMNS:
            if new[column].isna().any() or golden[column].isna().any():
                raise AuthorityGateError(f"missing enum value: {column}")
            if not np.array_equal(
                new[column].astype(str).to_numpy(), golden[column].astype(str).to_numpy()
            ):
                raise AuthorityGateError(f"exact enum mismatch: {column}")
        else:
            left = new[column].to_numpy(dtype=float)
            right = golden[column].to_numpy(dtype=float)
            if not np.isfinite(left).all() or not np.isfinite(right).all():
                raise AuthorityGateError(f"non-finite compared float: {column}")
            if not np.isclose(
                left, right, rtol=rtol, atol=atol, equal_nan=False
            ).all():
                raise AuthorityGateError(f"float tolerance mismatch: {column}")
    return len(new)


def run_authority_gate(*, repository_root: str | Path, new_run_dir: str | Path,
                       evidence_path: str | Path, dataset: str) -> dict[str, Any]:
    """Compare only development features against a pre-registered same-dataset reference.

    No full test-feature comparison is exposed by this development gate.
    """
    from src.dataset_binding import dataset_context, _resource
    from src.training.development_reader import _read_manifest, _output_records, _bound_input_run
    require_authority_platform()
    context = dataset_context(dataset)
    registry = json.loads(_resource("validation/registry.json"))
    if dataset not in registry:
        raise AuthorityGateError("authoritative_gate_not_run: no independently registered reference for dataset")
    reference = registry[dataset]
    root = Path(repository_root).resolve() / "neural/runs"
    run = _bound_input_run(new_run_dir, root)
    golden_run = _bound_input_run(root / reference["run"], root)
    left, _ = _read_manifest(run)
    right, right_sha = _read_manifest(golden_run)
    if (run == golden_run or right_sha != reference["manifest_sha256"]
            or left["dataset_binding"] != context.snapshot() or right["dataset_binding"] != context.snapshot()):
        raise AuthorityGateError("authority reference lineage mismatch")
    _output_records(run, left)
    _output_records(golden_run, right)
    rows = compare_tables(run/"processed/development_events.csv.gz",
                          golden_run/"processed/development_events.csv.gz",
                          tuple(left["schema"]["ordered_columns"]), rtol=1e-12, atol=1e-12)
    if left["counts"] != right["counts"]:
        raise AuthorityGateError("authority counts mismatch")
    evidence = {"schema_version":"authority-development-v2", "status":"passed",
                "dataset_binding":context.snapshot(), "rows_compared":rows,
                "reference_manifest_sha256":right_sha, "test_features_compared":False}
    destination=Path(evidence_path)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open("xb") as stream:stream.write(json_bytes(evidence))
    return evidence
