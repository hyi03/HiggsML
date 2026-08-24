from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from numbers import Integral
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

import numpy as np
import pandas as pd

from .weights import MCNormalization


SUMMARY_SCHEMA_VERSION = "1.0"
MANIFEST_SCHEMA_VERSION = "1.1"

_DISTRIBUTIONS = {
    "numpy": "numpy",
    "pandas": "pandas",
    "pyyaml": "PyYAML",
    "uproot": "uproot",
    "xgboost": "xgboost",
    "scikit-learn": "scikit-learn",
    "hep_ml": "hep-ml",
}
_GIT_SHA_PATTERN = re.compile(r"[0-9a-fA-F]{40}")


@dataclass(frozen=True)
class SampleSummaryInput:
    sample_name: str
    kind: Literal["data", "mc"]
    frame: pd.DataFrame
    cutflow: Mapping[str, Any]
    period: str | None = None
    expected_dsids: tuple[int, ...] = ()
    label: int | None = None


@dataclass(frozen=True)
class MCNormalizationInput:
    sample_name: str
    normalization: MCNormalization
    dsids: tuple[int, ...]
    luminosity_pb: float


def _cutflow_count(sample: SampleSummaryInput, stage: str) -> int:
    if sample.cutflow.get("sample_name") != sample.sample_name:
        raise ValueError(f"{sample.sample_name}: cutflow sample_name does not match")
    if sample.cutflow.get("kind") != sample.kind:
        raise ValueError(f"{sample.sample_name}: cutflow kind does not match")
    try:
        value = sample.cutflow["stages"][stage]["count"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"{sample.sample_name}: cutflow is missing the {stage!r} stage count"
        ) from exc
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise ValueError(
            f"{sample.sample_name}: {stage} count must be a non-negative integer"
        )
    return int(value)


def _validated_counts(sample: SampleSummaryInput) -> tuple[int, int]:
    read_events = _cutflow_count(sample, "read")
    selected_events = _cutflow_count(sample, "selected")
    if selected_events != len(sample.frame):
        raise ValueError(
            f"{sample.sample_name}: selected cutflow count does not match frame length"
        )
    if read_events < selected_events:
        raise ValueError(
            f"{sample.sample_name}: read_events cannot be below selected_events"
        )
    return read_events, selected_events


def _data_entry(sample: SampleSummaryInput) -> dict[str, Any]:
    read_events, selected_events = _validated_counts(sample)
    if not sample.period:
        raise ValueError(f"{sample.sample_name}: data period is required")
    identity_columns = ("runNumber", "eventNumber")
    missing = [column for column in identity_columns if column not in sample.frame]
    if missing:
        raise ValueError(
            f"{sample.sample_name}: data frame is missing {', '.join(missing)}"
        )
    if sample.frame.loc[:, identity_columns].isna().any().any():
        raise ValueError(f"{sample.sample_name}: run/event identity must not be missing")
    unique_events = int(
        sample.frame.loc[:, identity_columns].drop_duplicates().shape[0]
    )
    return {
        "period": sample.period,
        "read_events": read_events,
        "selected_events": selected_events,
        "unique_run_event_pairs": unique_events,
        "duplicate_run_event_pairs": selected_events - unique_events,
    }


def _integer_dsids(values: Sequence[Any], sample_name: str) -> set[int]:
    result: set[int] = set()
    for value in values:
        if isinstance(value, bool):
            raise ValueError(f"{sample_name}: channelNumber must contain integers")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{sample_name}: channelNumber must contain integers"
            ) from exc
        if not np.isfinite(number) or not number.is_integer():
            raise ValueError(f"{sample_name}: channelNumber must contain integers")
        result.add(int(number))
    return result


def _mc_normalization_entries(
    samples: Sequence[MCNormalizationInput],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for sample in sorted(samples, key=lambda value: value.sample_name):
        if sample.sample_name in output:
            raise ValueError("duplicate MC normalization sample_name")
        dsids = sorted(_integer_dsids(sample.dsids, sample.sample_name))
        if not dsids:
            raise ValueError(f"{sample.sample_name}: dsids must not be empty")
        try:
            luminosity_pb = float(sample.luminosity_pb)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{sample.sample_name}: luminosity_pb must be finite and positive"
            ) from exc
        if not np.isfinite(luminosity_pb) or luminosity_pb <= 0:
            raise ValueError(
                f"{sample.sample_name}: luminosity_pb must be finite and positive"
            )
        normalization = sample.normalization
        output[sample.sample_name] = {
            "dsids": dsids,
            "luminosity_pb": luminosity_pb,
            "xsec_pb": normalization.xsec_pb,
            "k_factor": normalization.k_factor,
            "filter_efficiency": normalization.filter_efficiency,
            "sum_of_weights": normalization.sum_of_weights,
            "effective_cross_section_pb": (
                normalization.effective_cross_section_pb
            ),
        }
    return output


def _sample_processing_entries(
    samples: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    required = {
        "input_profile",
        "tree_name",
        "momentum_unit",
        "normalization_source",
    }
    output: dict[str, dict[str, Any]] = {}
    for sample_name in sorted(samples):
        value = samples[sample_name]
        if not isinstance(sample_name, str) or not sample_name:
            raise ValueError("sample processing names must be non-empty strings")
        if not isinstance(value, Mapping) or set(value) != required:
            raise ValueError("sample processing keys must be exactly input provenance fields")
        profile = value["input_profile"]
        tree_name = value["tree_name"]
        momentum_unit = value["momentum_unit"]
        source = value["normalization_source"]
        if not all(isinstance(item, str) and item for item in (profile, tree_name, momentum_unit)):
            raise ValueError("sample input profile, tree name, and momentum unit must be non-empty strings")
        if momentum_unit not in {"MeV", "GeV"}:
            raise ValueError("sample momentum unit must be MeV or GeV")
        if source not in {None, "root", "official_metadata"}:
            raise ValueError("unknown sample normalization source")
        output[sample_name] = {
            "input_profile": profile,
            "tree_name": tree_name,
            "momentum_unit": momentum_unit,
            "normalization_source": source,
        }
    return output


def _mc_entry(sample: SampleSummaryInput) -> dict[str, Any]:
    read_events, selected_events = _validated_counts(sample)
    if "physical_weight" not in sample.frame:
        raise ValueError(f"{sample.sample_name}: MC frame is missing physical_weight")
    if "channelNumber" not in sample.frame:
        raise ValueError(f"{sample.sample_name}: MC frame is missing channelNumber")

    expected_dsids = _integer_dsids(sample.expected_dsids, sample.sample_name)
    if not expected_dsids:
        raise ValueError(f"{sample.sample_name}: expected_dsids must not be empty")
    observed_dsids = _integer_dsids(
        sample.frame["channelNumber"].tolist(), sample.sample_name
    )
    unexpected = observed_dsids - expected_dsids
    if unexpected:
        raise ValueError(
            f"{sample.sample_name}: observed unconfigured DSID(s): {sorted(unexpected)}"
        )
    if sample.label is None:
        raise ValueError(f"{sample.sample_name}: MC label is required")

    weights = sample.frame["physical_weight"].to_numpy(dtype=float)
    if not np.isfinite(weights).all():
        raise ValueError(f"{sample.sample_name}: physical_weight must be finite")
    negative_events = int(np.count_nonzero(weights < 0))
    return {
        "dsids": sorted(expected_dsids),
        "label": int(sample.label),
        "read_events": read_events,
        "selected_events": selected_events,
        "signed_sum_physical_weights": float(weights.sum()),
        "absolute_sum_physical_weights": float(np.abs(weights).sum()),
        "negative_weight_events": negative_events,
        "negative_weight_fraction": (
            negative_events / selected_events if selected_events else 0.0
        ),
    }


def build_data_summary(
    samples: Sequence[SampleSummaryInput],
) -> dict[str, Any]:
    names = [sample.sample_name for sample in samples]
    if len(names) != len(set(names)):
        raise ValueError("duplicate sample_name in summary inputs")

    data: dict[str, Any] = {}
    mc: dict[str, Any] = {}
    for sample in sorted(samples, key=lambda value: value.sample_name):
        if sample.kind == "data":
            data[sample.sample_name] = _data_entry(sample)
        elif sample.kind == "mc":
            mc[sample.sample_name] = _mc_entry(sample)
        else:
            raise ValueError(
                f"{sample.sample_name}: kind must be either 'data' or 'mc'"
            )
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "data": data,
        "mc": mc,
    }


def write_json(payload: Mapping[str, Any], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def software_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for output_name, distribution in _DISTRIBUTIONS.items():
        try:
            versions[output_name] = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            versions[output_name] = "unavailable"
    return versions


def discover_git_commit(cwd: str | Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unavailable"
    commit = completed.stdout.strip()
    if completed.returncode != 0 or _GIT_SHA_PATTERN.fullmatch(commit) is None:
        return "unavailable"
    return commit.lower()


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _validated_timestamp(value: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("created_at_utc must be an ISO-8601 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(
            "created_at_utc must be an ISO-8601 UTC timestamp ending in Z"
        ) from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("created_at_utc must be an ISO-8601 UTC timestamp ending in Z")
    return value


def _validated_git_commit(value: str) -> str:
    if value == "unavailable":
        return value
    if _GIT_SHA_PATTERN.fullmatch(value) is None:
        raise ValueError("git_commit must be a 40-character hexadecimal SHA or unavailable")
    return value.lower()


def build_run_manifest(
    *,
    config_path: str | Path,
    config_snapshot_path: str | Path | None,
    input_paths: Mapping[str, str | Path],
    processing: Mapping[str, Any],
    sample_processing: Mapping[str, Mapping[str, Any]] | None = None,
    mc_normalizations: Sequence[MCNormalizationInput],
    output_locations: Mapping[str, str | Path | None],
    created_at_utc: str | None = None,
    versions: Mapping[str, str] | None = None,
    git_commit: str | None = None,
    git_cwd: str | Path = ".",
    cutflow_schema_version: str = "1.0",
) -> dict[str, Any]:
    config_source = Path(config_path)
    inputs: dict[str, Any] = {}
    for sample_name in sorted(input_paths):
        source = Path(input_paths[sample_name])
        inputs[sample_name] = {
            "path": str(source),
            "size_bytes": source.stat().st_size,
            "sha256": sha256_file(source),
        }

    timestamp = _validated_timestamp(created_at_utc or _utc_timestamp())
    resolved_versions = dict(versions) if versions is not None else software_versions()
    resolved_commit = (
        git_commit if git_commit is not None else discover_git_commit(git_cwd)
    )
    processing_payload = dict(processing)
    if sample_processing is not None:
        processing_payload["samples"] = _sample_processing_entries(sample_processing)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "created_at_utc": timestamp,
        "software": resolved_versions,
        "config": {
            "path": str(config_source),
            "snapshot_path": (
                None if config_snapshot_path is None else str(config_snapshot_path)
            ),
            "sha256": sha256_file(config_source),
        },
        "inputs": inputs,
        "processing": processing_payload,
        "mc_normalization": _mc_normalization_entries(mc_normalizations),
        "git": {"commit": _validated_git_commit(resolved_commit)},
        "outputs": {
            "locations": {
                name: None if path is None else str(path)
                for name, path in output_locations.items()
            },
            "cutflow_schema_version": str(cutflow_schema_version),
            "data_summary_schema_version": SUMMARY_SCHEMA_VERSION,
            "run_manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        },
    }
