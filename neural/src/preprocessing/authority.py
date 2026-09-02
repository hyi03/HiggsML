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
STRING_COLUMNS = {"split", "source_sample"}
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


def _verify_hash(repository: Path, relative_path: str, expected: str) -> Path:
    path = repository / relative_path
    if not path.is_file():
        raise AuthorityGateError(f"authoritative lineage artifact is absent: {relative_path}")
    actual = sha256_file(path)
    if actual != expected:
        raise AuthorityGateError(f"authoritative lineage hash mismatch: {relative_path}")
    return path


def verify_lineage(repository: Path, golden: dict[str, Any]) -> dict[str, Path]:
    fields = {
        "identity_manifest": ("identity_manifest_path", "identity_manifest_sha256"),
        "identity_table": ("identity_table_path", "identity_table_sha256"),
        "enrichment_manifest": (
            "enrichment_manifest_path", "enrichment_manifest_sha256"
        ),
        "baseline_manifest": ("baseline_manifest_path", "baseline_manifest_sha256"),
        "table": ("table_path", "table_sha256"),
    }
    return {
        name: _verify_hash(repository, golden[path_key], golden[hash_key])
        for name, (path_key, hash_key) in fields.items()
    }


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


def _find_cutflow_descriptor(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        path = value.get("path")
        if isinstance(path, str) and path.replace("\\", "/").endswith(
            "artifacts/cutflow.json"
        ):
            return value
        for child in value.values():
            found = _find_cutflow_descriptor(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_cutflow_descriptor(child)
            if found is not None:
                return found
    return None


def bound_legacy_cutflow(baseline_manifest: Path) -> Path:
    manifest = json.loads(baseline_manifest.read_text(encoding="utf-8"))
    descriptor = _find_cutflow_descriptor(manifest.get("outputs"))
    if descriptor is None:
        raise AuthorityGateError("baseline manifest does not bind a cutflow output")
    run_dir = baseline_manifest.parent.parent.resolve()
    candidate = (run_dir / descriptor["path"]).resolve()
    try:
        candidate.relative_to(run_dir)
    except ValueError as error:
        raise AuthorityGateError("baseline cutflow path escapes its run") from error
    expected_hash = descriptor.get("sha256")
    if not isinstance(expected_hash, str) or sha256_file(candidate) != expected_hash:
        raise AuthorityGateError("baseline cutflow is not hash-bound by its manifest")
    return candidate


def compare_cutflows(
    new_cutflow: dict[str, Any],
    legacy_cutflow: dict[str, Any],
    *,
    rtol: float,
    atol: float,
) -> None:
    for sample in ("higgs_345060", "zz_363490"):
        left = new_cutflow["samples"][sample]
        right = legacy_cutflow["samples"][sample]
        for stage in STAGES:
            left_stage, right_stage = left["stages"][stage], right["stages"][stage]
            if int(left_stage["count"]) != int(right_stage["count"]):
                raise AuthorityGateError(f"cutflow count mismatch: {sample}/{stage}")
            for field in FLOAT_CUTFLOW_FIELDS:
                values = np.asarray([left_stage[field], right_stage[field]], dtype=float)
                if not np.isfinite(values).all() or not np.isclose(
                    values[0], values[1], rtol=rtol, atol=atol, equal_nan=False
                ):
                    raise AuthorityGateError(
                        f"cutflow float mismatch: {sample}/{stage}/{field}"
                    )


def _verify_counts(summary: dict[str, Any], golden: dict[str, Any]) -> None:
    expected = golden["expected_counts"]
    for sample in ("higgs_345060", "zz_363490"):
        actual = summary["samples"][sample]
        wanted = expected[sample]
        observed = {
            "read": actual["read_count"], "selected": actual["selected_count"],
            **actual["split_counts"],
        }
        if observed != wanted:
            raise AuthorityGateError(f"authority counts mismatch: {sample}")
    totals = summary["totals"]
    observed_total = {
        "read": totals["read_count"], "selected": totals["selected_count"],
        **totals["split_counts"],
    }
    if observed_total != expected["total"]:
        raise AuthorityGateError("authority total counts mismatch")
    identity = summary["identity"]
    duplicates = golden["expected_legacy_duplicates"]
    if (
        identity["legacy_duplicate_groups"] != duplicates["groups"]
        or identity["legacy_duplicate_rows"] != duplicates["rows"]
    ):
        raise AuthorityGateError("legacy duplicate facts mismatch")


def run_authority_gate(
    *, repository_root: str | Path, new_run_dir: str | Path, evidence_path: str | Path
) -> dict[str, Any]:
    """Run the pre-registered full-data gate and write a new immutable evidence file."""
    require_authority_platform()
    repository = Path(repository_root).resolve()
    run = Path(new_run_dir).resolve()
    protocol = load_preprocess_protocol(
        repository / "neural/config/preprocess_protocol_v1.yaml"
    )
    golden = protocol.raw["golden"]
    lineage = verify_lineage(repository, golden)
    rows = compare_tables(
        run / "processed/mc_events.csv.gz", lineage["table"], protocol.output_columns,
        rtol=protocol.float_rtol, atol=protocol.float_atol,
    )
    summary = json.loads(
        (run / "artifacts/mc_summary.json").read_text(encoding="utf-8")
    )
    _verify_counts(summary, golden)
    new_cutflow = json.loads(
        (run / "artifacts/cutflow.json").read_text(encoding="utf-8")
    )
    legacy_cutflow_path = bound_legacy_cutflow(lineage["baseline_manifest"])
    legacy_cutflow = json.loads(legacy_cutflow_path.read_text(encoding="utf-8"))
    compare_cutflows(
        new_cutflow, legacy_cutflow, rtol=protocol.float_rtol,
        atol=protocol.float_atol,
    )
    evidence = {
        "schema_version": "1.0", "status": "passed",
        "gate": "higgsml-preprocess-v1-osx-arm64", "rows_compared": rows,
        "new_run_dir": str(run),
        "lineage_sha256": {
            name: sha256_file(path) for name, path in lineage.items()
        },
        "predicates": {
            "structural": "exact", "float_rtol": protocol.float_rtol,
            "float_atol": protocol.float_atol, "equal_nan": False,
        },
    }
    destination = Path(evidence_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(json_bytes(evidence))
    return evidence
