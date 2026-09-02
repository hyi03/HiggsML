from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import re
import sys
import time
from typing import Any
import unicodedata
import uuid

import numpy as np
import pandas as pd
import torch
import yaml

from src.artifacts.manifest import canonical_json_bytes, peak_memory_bytes, sha256_file, software_record, write_canonical_json
from src.artifacts.plots import write_test_plots
from src.artifacts.transaction import RunPathError, RunTransaction
from src.config import ExitCode, InputBindingError, TestOpeningFailure, TestOpeningRefused
from src.preprocessing.outputs import canonical_csv_bytes, write_canonical_table
from src.training.config import INPUT_COLUMNS, TARGET_LAMBDAS, validate_training_protocol_snapshot
from src.training.dataset import FEATURE_COLUMNS, FoldLocalScaler
from src.training.development_reader import (
    _bound_input_run,
    _canonical_content_sha256,
    _is_link_or_reparse,
    _output_records,
    _plain_descendant,
    _read_manifest,
)
from src.training.network import AdversarialMLP
from src.training.qualification import frozen_working_point_metrics, weighted_auc, weighted_roc_points
from src.training.test_reader import read_test_rows_after_claim


LOGGER = logging.getLogger(__name__)
TEST_SCORE_COLUMNS = (
    "source_sample", "source_entry", "label", "m4l",
    "physical_weight", "train_weight", "score",
)
_DEV_OUTPUTS = {
    "config.yaml", "artifacts/candidate_metrics.csv", "artifacts/fold_metrics.csv",
    "artifacts/qualification.json", "artifacts/working_points.json",
    "predictions/oof_scores.csv.gz", "plots/auc_vs_lambda.png", "plots/ks_vs_lambda.png",
    "plots/oof_roc.png", "plots/oof_mass_sculpting.png", "model/model.pt", "model/scaler.json",
}
_DEVELOPMENT_BOUNDARIES = {
    "educational_technical_demo": True,
    "real_data_read": False,
    "held_out_test_opened": False,
    "open_test_run": False,
    "authority_environment_verified": False,
}
_TEST_BOUNDARIES = {
    "educational_technical_demo": True,
    "real_data_read": False,
    "held_out_test_opened": True,
    "open_test_run": True,
    "authority_environment_verified": False,
}
_INPUT_HASH_KEYS = {
    "manifest_sha256",
    "table_sha256",
    "canonical_content_sha256",
    "preprocess_protocol_sha256",
    "preprocess_run_config_sha256",
}
_POINT_FIELDS = {
    "threshold",
    "target_background_efficiency",
    "achieved_background_efficiency",
    "signal_efficiency",
    "ks",
}
_SENSITIVE_AUTHORIZATION = re.compile(
    r"(?:password|passwd|api[\s_-]*key|secret|token|credential)\s*[:=]",
    re.IGNORECASE,
)


class _ClaimPathError(RunPathError):
    """A claim-path failure with explicit ownership of the O_EXCL file."""

    def __init__(self, message: str, *, claim_created: bool) -> None:
        self.claim_created = claim_created
        super().__init__(message)


@dataclass(frozen=True)
class TestOpeningResult:
    status: str
    run_dir: Path


@dataclass(frozen=True)
class _Binding:
    development_run: Path
    development_manifest_sha256: str
    development_manifest: dict[str, Any]
    preprocess_run: Path
    table: Path
    expected_test_rows: int
    protocol: dict[str, Any]
    protocol_sha256: str
    selected_lambda: float
    scaler: FoldLocalScaler
    model: AdversarialMLP
    working_points: dict[str, dict[str, float]]
    input_hashes: dict[str, str]
    artifact_hashes: dict[str, str]


def _hex_sha(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _finite_number(value: Any) -> bool:
    return type(value) in {int, float} and np.isfinite(float(value))


def _authorization_reference(value: Any) -> str:
    reference = value.strip() if type(value) is str else ""
    if not reference:
        raise TestOpeningRefused("authorization reference is blank")
    if (
        len(reference) > 256
        or any(unicodedata.category(character) in {"Cc", "Cf"} for character in reference)
        or _SENSITIVE_AUTHORIZATION.search(reference)
    ):
        raise TestOpeningRefused("authorization reference is not a public audit identifier")
    return reference


def _read_canonical_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        payload = path.read_bytes()
        value = json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InputBindingError("development JSON artifact cannot be loaded") from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != payload:
        raise InputBindingError("development JSON artifact is not canonical")
    return value, payload


def _development_manifest(run: Path) -> tuple[dict[str, Any], str]:
    manifest, payload = _read_canonical_json(
        _plain_descendant(run, Path("artifacts/manifest.json"))
    )
    required = {
        "schema_version", "status", "run_type", "started_at_utc", "completed_at_utc",
        "input", "protocol", "outputs", "counts", "schema", "oof_completeness",
        "selection", "environment", "software", "performance", "boundaries",
    }
    if set(manifest) != required:
        raise InputBindingError("development manifest schema changed")
    if manifest.get("status") != "eligible":
        raise TestOpeningRefused("development run is not eligible")
    selection = manifest.get("selection")
    counts = manifest.get("counts")
    completeness = manifest.get("oof_completeness")
    schema = manifest.get("schema")
    input_hashes = manifest.get("input")
    protocol = manifest.get("protocol")
    performance = manifest.get("performance")
    if (
        manifest.get("schema_version") != "development-manifest-v1"
        or manifest.get("run_type") != "development"
        or type(manifest.get("started_at_utc")) is not str
        or type(manifest.get("completed_at_utc")) is not str
        or manifest.get("boundaries") != _DEVELOPMENT_BOUNDARIES
        or not isinstance(manifest.get("outputs"), list)
        or not isinstance(manifest.get("environment"), dict)
        or not isinstance(manifest.get("software"), dict)
        or not isinstance(performance, dict)
        or set(performance) != {"wall_seconds", "peak_memory_bytes"}
        or not _finite_number(performance.get("wall_seconds"))
        or float(performance["wall_seconds"]) < 0.0
        or type(performance.get("peak_memory_bytes")) is not int
        or performance["peak_memory_bytes"] < 0
        or not isinstance(input_hashes, dict)
        or set(input_hashes) != _INPUT_HASH_KEYS
        or any(not _hex_sha(value) for value in input_hashes.values())
        or not isinstance(protocol, dict)
        or set(protocol) != {"id", "sha256"}
        or protocol.get("id") != "adversarial-mlp-protocol-v1"
        or not _hex_sha(protocol.get("sha256"))
        or not isinstance(selection, dict)
        or set(selection) != {"selected_lambda", "final_epochs"}
        or type(selection.get("selected_lambda")) is not float
        or not np.isfinite(selection["selected_lambda"])
        or type(selection.get("final_epochs")) is not int
        or selection["final_epochs"] <= 0
        or not isinstance(counts, dict)
        or set(counts) != {
            "input_rows", "development_rows", "held_out_test_rows_not_opened",
            "candidates", "folds_per_candidate", "fold_epoch_rows", "oof_rows",
        }
        or any(type(value) is not int or value <= 0 for value in counts.values())
        or counts["input_rows"]
        != counts["development_rows"] + counts["held_out_test_rows_not_opened"]
        or counts["candidates"] != len(TARGET_LAMBDAS)
        or counts["folds_per_candidate"] != 5
        or counts["oof_rows"] != counts["development_rows"] * counts["candidates"]
        or not isinstance(completeness, dict)
        or completeness != {
            "complete": True,
            "candidate_count": counts["candidates"],
            "rows_per_candidate": counts["development_rows"],
            "unique_identities_per_candidate": counts["development_rows"],
        }
        or not isinstance(schema, dict)
        or set(schema) != {
            "oof_columns", "oof_dtypes", "candidate_metric_columns",
            "candidate_metric_dtypes", "fold_metric_columns", "fold_metric_dtypes",
        }
        or any(not isinstance(schema[key], expected) for key, expected in (
            ("oof_columns", list),
            ("oof_dtypes", dict),
            ("candidate_metric_columns", list),
            ("candidate_metric_dtypes", dict),
            ("fold_metric_columns", list),
            ("fold_metric_dtypes", dict),
        ))
    ):
        raise InputBindingError("development manifest binding changed")
    return manifest, hashlib.sha256(payload).hexdigest()


def _validate_dev_outputs(run: Path, manifest: dict[str, Any]) -> None:
    seen: set[str] = set()
    for record in manifest["outputs"]:
        if (
            not isinstance(record, dict)
            or set(record) != {"path", "sha256", "size_bytes", "row_count", "canonical_content_sha256"}
            or type(record.get("path")) is not str
            or not _hex_sha(record.get("sha256"))
            or type(record.get("size_bytes")) is not int
            or record["size_bytes"] <= 0
            or record["path"] in seen
        ):
            raise InputBindingError("development output receipt changed")
        path = _plain_descendant(run, Path(record["path"]))
        if (
            not path.is_file()
            or path.stat().st_size != record["size_bytes"]
            or sha256_file(path) != record["sha256"]
        ):
            raise InputBindingError("development output hash changed")
        if record["path"] == "predictions/oof_scores.csv.gz":
            try:
                canonical_sha = hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()
            except (OSError, EOFError) as error:
                raise InputBindingError("development OOF artifact cannot be verified") from error
            expected_rows = manifest["counts"]["oof_rows"]
            if (
                type(record.get("row_count")) is not int
                or record["row_count"] != expected_rows
                or not _hex_sha(record.get("canonical_content_sha256"))
                or record["canonical_content_sha256"] != canonical_sha
            ):
                raise InputBindingError("development OOF receipt changed")
        elif record.get("row_count") is not None or record.get("canonical_content_sha256") is not None:
            raise InputBindingError("development output receipt changed")
        seen.add(record["path"])
    if seen != _DEV_OUTPUTS:
        raise InputBindingError("development output set changed")


def _resolve_preprocess(recorded: str, *, allowed_root: Path) -> Path:
    raw = Path(recorded)
    if raw.is_absolute():
        candidate = raw
    elif raw.parts and raw.parts[0].lower() == allowed_root.name.lower():
        candidate = allowed_root.parent / raw
    else:
        candidate = allowed_root / raw
    return _bound_input_run(candidate, allowed_root)


def _validate_protocol_manifest_binding(
    protocol: dict[str, Any], manifest: dict[str, Any]
) -> None:
    validate_training_protocol_snapshot(protocol)
    schema = manifest["schema"]
    artifacts = protocol["development_artifacts"]
    if (
        schema["oof_columns"] != artifacts["oof_columns"]
        or schema["candidate_metric_columns"] != artifacts["candidate_metric_columns"]
        or schema["fold_metric_columns"] != artifacts["fold_metric_columns"]
        or set(schema["oof_dtypes"]) != set(artifacts["oof_columns"])
        or set(schema["candidate_metric_dtypes"])
        != set(artifacts["candidate_metric_columns"])
        or set(schema["fold_metric_dtypes"]) != set(artifacts["fold_metric_columns"])
        or tuple(protocol["features"]) != FEATURE_COLUMNS
        or tuple(protocol["input_columns"]) != INPUT_COLUMNS
    ):
        raise InputBindingError("development schema is not bound to the frozen protocol")


def _validated_working_points(
    points_file: dict[str, Any],
    qualification: dict[str, Any],
    protocol: dict[str, Any],
    *,
    selected_lambda: float,
) -> dict[str, dict[str, float]]:
    targets = list(protocol["determinism"]["target_lambdas"])
    if (
        set(points_file) != {"schema_version", "selected_lambda", "candidates"}
        or points_file.get("schema_version") != "development-working-points-v1"
        or points_file.get("selected_lambda") != selected_lambda
        or not isinstance(points_file.get("candidates"), list)
        or set(qualification)
        != {
            "schema_version", "status", "selected_lambda", "final_epochs",
            "tie_rule", "candidates",
        }
        or qualification.get("schema_version") != "development-qualification-v1"
        or qualification.get("status") != "eligible"
        or qualification.get("selected_lambda") != selected_lambda
        or qualification.get("tie_rule")
        != {
            "reference": "maximum_eligible_auc",
            "rtol": 0.0,
            "atol": 1.0e-6,
            "prefer": "smaller_lambda",
        }
        or not isinstance(qualification.get("candidates"), list)
        or len(points_file["candidates"]) != len(targets)
        or len(qualification["candidates"]) != len(targets)
    ):
        raise InputBindingError("development qualification schema changed")

    selected_points: dict[str, dict[str, float]] | None = None
    eligible_candidates: list[dict[str, Any]] = []
    for index, target_lambda in enumerate(targets):
        point_candidate = points_file["candidates"][index]
        candidate = qualification["candidates"][index]
        if (
            not isinstance(point_candidate, dict)
            or set(point_candidate) != {"target_lambda", "working_points"}
            or point_candidate.get("target_lambda") != target_lambda
            or not isinstance(candidate, dict)
            or set(candidate)
            != {
                "target_lambda", "weighted_oof_auc", "working_points",
                "eligible", "rejection_reasons",
            }
            or candidate.get("target_lambda") != target_lambda
            or not _finite_number(candidate.get("weighted_oof_auc"))
            or type(candidate.get("eligible")) is not bool
            or not isinstance(candidate.get("rejection_reasons"), list)
            or candidate.get("working_points") != point_candidate.get("working_points")
            or not isinstance(point_candidate.get("working_points"), dict)
            or tuple(point_candidate["working_points"]) != ("loose", "medium", "tight")
        ):
            raise InputBindingError("development candidate binding changed")
        for name, point in point_candidate["working_points"].items():
            if (
                not isinstance(point, dict)
                or set(point) != _POINT_FIELDS
                or any(not _finite_number(value) for value in point.values())
                or float(point["threshold"]) < 0.0
                or float(point["threshold"]) > 1.0
                or float(point["target_background_efficiency"])
                != float(protocol["working_points"][name])
                or any(
                    float(point[field]) < 0.0 or float(point[field]) > 1.0
                    for field in (
                        "target_background_efficiency",
                        "achieved_background_efficiency",
                        "signal_efficiency",
                        "ks",
                    )
                )
            ):
                raise InputBindingError("frozen working point changed")
        expected_reasons: list[str] = []
        if float(candidate["weighted_oof_auc"]) < float(protocol["qualification"]["auc_minimum"]):
            expected_reasons.append("auc_below_minimum")
        for name, point in point_candidate["working_points"].items():
            if float(point["ks"]) > float(protocol["qualification"]["ks_maximum"]):
                expected_reasons.append(f"{name}_ks_above_maximum")
            if float(point["signal_efficiency"]) <= float(
                point["achieved_background_efficiency"]
            ):
                expected_reasons.append(f"{name}_signal_efficiency_not_greater")
        if (
            candidate["rejection_reasons"] != expected_reasons
            or candidate["eligible"] != (not expected_reasons)
        ):
            raise InputBindingError("development candidate qualification changed")
        if candidate["eligible"]:
            eligible_candidates.append(candidate)
        if target_lambda == selected_lambda:
            if candidate["eligible"] is not True or candidate["rejection_reasons"] != []:
                raise InputBindingError("selected development candidate is not eligible")
            selected_points = point_candidate["working_points"]
    if selected_points is None:
        raise InputBindingError("selected development candidate is missing")
    best_auc = max(float(candidate["weighted_oof_auc"]) for candidate in eligible_candidates)
    tolerance = float(protocol["qualification"]["auc_tie_atol"])
    expected_selection = min(
        float(candidate["target_lambda"])
        for candidate in eligible_candidates
        if abs(float(candidate["weighted_oof_auc"]) - best_auc) <= tolerance
    )
    if selected_lambda != expected_selection:
        raise InputBindingError("development candidate selection changed")
    return selected_points


def _load_binding(development_run: str | Path, *, allowed_root: str | Path) -> _Binding:
    root = Path(allowed_root).resolve(strict=True)
    run = _bound_input_run(development_run, root)
    manifest, manifest_sha = _development_manifest(run)
    _validate_dev_outputs(run, manifest)
    try:
        config = yaml.safe_load((run / "config.yaml").read_bytes())
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise InputBindingError("development config cannot be loaded") from error
    if not isinstance(config, dict) or set(config) != {
        "schema_version", "input_run", "input_manifest_sha256", "protocol_sha256", "protocol"
    } or config.get("schema_version") != "development-config-v1" or not isinstance(config.get("protocol"), dict):
        raise InputBindingError("development config binding changed")
    protocol = config["protocol"]
    _validate_protocol_manifest_binding(protocol, manifest)
    protocol_sha = config.get("protocol_sha256")
    selection = manifest.get("selection")
    if (
        not _hex_sha(protocol_sha)
        or manifest.get("protocol")
        != {"id": "adversarial-mlp-protocol-v1", "sha256": protocol_sha}
        or not isinstance(selection, dict)
        or selection["selected_lambda"] not in TARGET_LAMBDAS
    ):
        raise InputBindingError("development selection binding changed")
    selected = selection["selected_lambda"]
    qualification, _ = _read_canonical_json(run / "artifacts/qualification.json")
    points_file, _ = _read_canonical_json(run / "artifacts/working_points.json")
    if qualification.get("final_epochs") != selection["final_epochs"]:
        raise InputBindingError("development qualification binding changed")
    working_points = _validated_working_points(
        points_file,
        qualification,
        protocol,
        selected_lambda=selected,
    )
    scaler_raw, _ = _read_canonical_json(run / "model/scaler.json")
    scaler = FoldLocalScaler.from_dict(scaler_raw)
    if scaler.fitting_rows != manifest["counts"]["development_rows"]:
        raise InputBindingError("frozen scaler row binding changed")
    try:
        payload = torch.load(run / "model/model.pt", map_location="cpu", weights_only=True)
    except Exception as error:
        raise InputBindingError("frozen model cannot be loaded") from error
    model_keys = {
        "schema_version", "protocol_sha256", "feature_tuple", "scaler", "target_lambda",
        "seed", "epochs", "classifier_state_dict", "adversary_state_dict", "environment",
    }
    if (
        not isinstance(payload, dict)
        or set(payload) != model_keys
        or payload.get("schema_version") != "adversarial-mlp-final-v1"
        or payload.get("protocol_sha256") != protocol_sha
        or tuple(payload.get("feature_tuple", ())) != FEATURE_COLUMNS
        or payload.get("target_lambda") != selected
        or payload.get("seed") != protocol["final_fit"]["seed"]
        or payload.get("epochs") != selection["final_epochs"]
        or payload.get("scaler") != scaler_raw
        or not isinstance(payload.get("environment"), dict)
        or not isinstance(payload.get("classifier_state_dict"), dict)
        or not isinstance(payload.get("adversary_state_dict"), dict)
        or any(
            not isinstance(tensor, torch.Tensor)
            or tensor.device.type != "cpu"
            or tensor.dtype != torch.float32
            or not torch.isfinite(tensor).all()
            for state in (
                payload.get("classifier_state_dict", {}),
                payload.get("adversary_state_dict", {}),
            )
            for tensor in state.values()
        )
    ):
        raise InputBindingError("frozen model binding changed")
    model = AdversarialMLP().cpu().to(torch.float32)
    try:
        model.classifier.load_state_dict(payload["classifier_state_dict"], strict=True)
        model.adversary.load_state_dict(payload["adversary_state_dict"], strict=True)
    except (RuntimeError, TypeError) as error:
        raise InputBindingError("frozen model state changed") from error
    if any(t.device.type != "cpu" or t.dtype != torch.float32 for t in model.state_dict().values()):
        raise InputBindingError("frozen model tensor binding changed")
    model.eval()

    preprocess = _resolve_preprocess(str(config.get("input_run")), allowed_root=root)
    pre_manifest, pre_manifest_sha = _read_manifest(preprocess)
    records = _output_records(preprocess, pre_manifest)
    table_record = records["processed/mc_events.csv.gz"]
    table = preprocess / "processed/mc_events.csv.gz"
    input_hashes = manifest["input"]
    if (
        pre_manifest_sha != input_hashes.get("manifest_sha256")
        or table_record["sha256"] != input_hashes.get("table_sha256")
        or table_record["canonical_content_sha256"] != input_hashes.get("canonical_content_sha256")
        or _canonical_content_sha256(table) != table_record["canonical_content_sha256"]
        or config.get("input_manifest_sha256") != pre_manifest_sha
    ):
        raise InputBindingError("preprocess lineage binding changed")
    try:
        pre_count = pre_manifest["counts"]["totals"]["split_counts"]["test"]
        dev_count = manifest["counts"]["held_out_test_rows_not_opened"]
    except (KeyError, TypeError) as error:
        raise InputBindingError("test row count binding changed") from error
    if type(pre_count) is not int or pre_count <= 0 or pre_count != dev_count:
        raise InputBindingError("test row count binding changed")
    output_records = {record["path"]: record for record in manifest["outputs"]}
    artifact_hashes = {
        "qualification_sha256": output_records["artifacts/qualification.json"]["sha256"],
        "working_points_sha256": output_records["artifacts/working_points.json"]["sha256"],
        "oof_scores_sha256": output_records["predictions/oof_scores.csv.gz"]["sha256"],
        "model_sha256": output_records["model/model.pt"]["sha256"],
        "scaler_sha256": output_records["model/scaler.json"]["sha256"],
    }
    return _Binding(
        run,
        manifest_sha,
        manifest,
        preprocess,
        table,
        pre_count,
        protocol,
        protocol_sha,
        selected,
        scaler,
        model,
        working_points,
        input_hashes,
        artifact_hashes,
    )


def _flush_directory(path: Path) -> None:
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        )
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.FlushFileBuffers.argtypes = (wintypes.HANDLE,)
        kernel32.FlushFileBuffers.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.CreateFileW(
            str(path),
            0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
            0x00000001 | 0x00000002 | 0x00000004,
            None,
            3,  # OPEN_EXISTING
            0x02000000,  # FILE_FLAG_BACKUP_SEMANTICS
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            error = ctypes.get_last_error()
            raise OSError(error, "cannot open directory for durable flush", str(path))
        try:
            if not kernel32.FlushFileBuffers(handle):
                error = ctypes.get_last_error()
                raise OSError(error, "cannot durably flush directory", str(path))
        finally:
            kernel32.CloseHandle(handle)
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _claim(
    binding: _Binding,
    *,
    output_run: Path,
    authorization: str,
    staging: Path,
    claimed_at_utc: str,
) -> Path:
    state_dir = binding.development_run / "state"
    state_dir_existed = state_dir.exists()
    try:
        state_dir.mkdir(exist_ok=True)
    except OSError as error:
        raise _ClaimPathError(
            "test-opening state directory cannot be created",
            claim_created=False,
        ) from error
    if _is_link_or_reparse(state_dir) or not state_dir.is_dir():
        raise InputBindingError("test-opening state directory is invalid")
    if not state_dir_existed:
        try:
            _flush_directory(binding.development_run)
        except OSError as error:
            raise _ClaimPathError(
                "test-opening state directory is not durable",
                claim_created=False,
            ) from error
    state = state_dir / "test_opening.json"
    claim = {
        "schema_version": "test-opening-state-v1", "status": "claimed",
        "development_manifest_sha256": binding.development_manifest_sha256,
        "test_run": output_run.as_posix(), "output_staging": staging.as_posix(),
        "authorization_reference": authorization, "claimed_at_utc": claimed_at_utc,
        "test_features_opened": False, "terminal_receipt": False,
    }
    try:
        descriptor = os.open(state, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise TestOpeningRefused("development run already has a test-opening state") from error
    except OSError as error:
        raise _ClaimPathError(
            "test-opening claim cannot be created",
            claim_created=False,
        ) from error
    try:
        try:
            stream = os.fdopen(descriptor, "wb")
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise
        with stream:
            stream.write(canonical_json_bytes(claim))
            stream.flush()
            os.fsync(stream.fileno())
        _flush_directory(state_dir)
    except BaseException as error:
        raise _ClaimPathError(
            "test-opening claim is not durable",
            claim_created=True,
        ) from error
    return state


def _replace_state(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        stream = os.fdopen(descriptor, "wb")
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    with stream:
        stream.write(canonical_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    _flush_directory(path.parent)


def _record(root: Path, relative: str, *, canonical: str | None = None, rows: int | None = None) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "row_count": rows,
        "canonical_content_sha256": canonical,
    }


def _evaluate(binding: _Binding) -> tuple[pd.DataFrame, dict[str, Any]]:
    torch.use_deterministic_algorithms(True)
    test = read_test_rows_after_claim(binding.table, expected_rows=binding.expected_test_rows)
    raw = test.frame
    features = binding.scaler.transform(raw[list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64))
    with torch.no_grad():
        logits = binding.model.classifier(torch.from_numpy(features))
        scores = torch.sigmoid(logits).cpu().numpy().astype(np.float64)
    if scores.shape != (binding.expected_test_rows,) or not np.isfinite(scores).all() or np.any(scores < 0.0) or np.any(scores > 1.0):
        raise RuntimeError("test prediction completeness changed")
    frame = pd.DataFrame({name: raw[name].to_numpy(copy=True) for name in TEST_SCORE_COLUMNS[:-1]})
    frame["score"] = scores
    frame = frame.sort_values(["source_sample", "source_entry"], kind="stable", ignore_index=True)
    expected_identities = sorted(
        zip(raw["source_sample"], raw["source_entry"], strict=True),
        key=lambda item: (str(item[0]).encode("utf-8"), int(item[1])),
    )
    if list(zip(frame["source_sample"], frame["source_entry"], strict=True)) != expected_identities:
        raise RuntimeError("test prediction identity completeness changed")
    auc = weighted_auc(frame["label"], frame["score"], frame["train_weight"])
    points = {
        name: frozen_working_point_metrics(
            frame, target=float(binding.protocol["working_points"][name]),
            threshold=float(binding.working_points[name]["threshold"]),
        )
        for name in ("loose", "medium", "tight")
    }
    rules = binding.protocol["qualification"]
    reasons: list[str] = []
    if auc < float(rules["auc_minimum"]):
        reasons.append("auc_below_minimum")
    for name, point in points.items():
        if point["ks"] > float(rules["ks_maximum"]):
            if point["empty_selected_background"]:
                reasons.append(f"{name}_empty_selected_background")
            reasons.append(f"{name}_ks_above_maximum")
        if point["signal_efficiency"] <= point["achieved_background_efficiency"]:
            reasons.append(f"{name}_signal_efficiency_not_greater")
    status = "test_nonreproduction" if reasons else "test_reproduced"
    return frame, {
        "schema_version": "test-metrics-v1",
        "status": status,
        "selected_lambda": binding.selected_lambda,
        "weighted_auc": auc,
        "working_points": points,
        "prediction_completeness": {
            "complete": True,
            "row_count": len(frame),
            "unique_identities": len(expected_identities),
        },
        "rejection_reasons": reasons,
        "no_feedback": True,
        "boundaries": {
            "training_performed": False,
            "scaler_fit_performed": False,
            "threshold_selection_performed": False,
            "candidate_selection_performed": False,
            "parameter_updates_performed": False,
        },
    }


def _write_success_artifacts(
    transaction: RunTransaction,
    binding: _Binding,
    scores: pd.DataFrame,
    metrics: dict[str, Any],
    *,
    authorization: str,
    started: float,
    started_utc: str,
) -> None:
    artifacts = transaction.path / "artifacts"
    predictions = transaction.path / "predictions"
    artifacts.mkdir()
    predictions.mkdir()
    snapshot = {
        "schema_version": "test-config-v1",
        "development_run": binding.development_run.as_posix(),
        "development_manifest_sha256": binding.development_manifest_sha256,
        "protocol_sha256": binding.protocol_sha256,
        "authorization_reference": authorization,
    }
    config_bytes = yaml.safe_dump(snapshot, sort_keys=False).encode("utf-8")
    (transaction.path / "config.yaml").write_bytes(config_bytes)
    write_canonical_json(artifacts / "test_metrics.json", metrics)
    csv_payload = canonical_csv_bytes(
        scores,
        TEST_SCORE_COLUMNS,
        integer_columns={"source_entry", "label"},
        string_columns={"source_sample"},
    )
    score_receipt = write_canonical_table(
        predictions / "test_scores.csv.gz",
        csv_payload,
        row_count=len(scores),
    )
    roc = weighted_roc_points(scores)
    write_test_plots(
        transaction.path / "plots",
        scores,
        roc_points=roc,
        medium_threshold=float(metrics["working_points"]["medium"]["threshold"]),
        mass_edges=tuple(
            float(value) for value in binding.protocol["adversary"]["mass_edges_gev"]
        ),
    )
    paths = [
        "config.yaml",
        "artifacts/test_metrics.json",
        "predictions/test_scores.csv.gz",
        "plots/test_roc.png",
        "plots/test_mass_sculpting.png",
    ]
    outputs = [
        _record(
            transaction.path,
            path,
            canonical=(
                score_receipt.canonical_content_sha256
                if path == "predictions/test_scores.csv.gz"
                else None
            ),
            rows=len(scores) if path == "predictions/test_scores.csv.gz" else None,
        )
        for path in paths
    ]
    manifest = {
        "schema_version": "test-manifest-v1",
        "run_type": "test_opening",
        "status": metrics["status"],
        "started_at_utc": started_utc,
        "completed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "authorization_reference": authorization,
        "development": {
            "run": binding.development_run.as_posix(),
            "manifest_sha256": binding.development_manifest_sha256,
            "selected_lambda": binding.selected_lambda,
            "artifacts": binding.artifact_hashes,
        },
        "input": binding.input_hashes,
        "protocol_sha256": binding.protocol_sha256,
        "outputs": outputs,
        "schema": {
            "score_columns": list(TEST_SCORE_COLUMNS),
            "score_dtypes": {
                name: str(scores[name].dtype) for name in TEST_SCORE_COLUMNS
            },
        },
        "counts": {"test_rows": len(scores)},
        "metrics": metrics,
        "environment": {
            "development": binding.development_manifest["environment"],
            "evaluation": {
                "os": platform.system(),
                "architecture": platform.machine(),
                "python": sys.version.split()[0],
                "pytorch": torch.__version__,
                "device": "cpu",
                "dtype": "float32",
                "threads": torch.get_num_threads(),
                "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            },
        },
        "software": software_record(),
        "performance": {
            "wall_seconds": time.perf_counter() - started,
            "peak_memory_bytes": peak_memory_bytes(),
        },
        "boundaries": _TEST_BOUNDARIES,
    }
    write_canonical_json(artifacts / "manifest.json", manifest)


def _failure_state(
    binding: _Binding,
    transaction: RunTransaction,
    authorization: str,
    error: BaseException,
    *,
    claimed_at_utc: str,
    output_staging: Path,
    test_features_opened: bool,
) -> dict[str, Any]:
    code = getattr(error, "exit_code", ExitCode.INTERNAL_ERROR)
    cause = error.__cause__ if isinstance(error, TestOpeningFailure) else None
    return {
        "schema_version": "test-opening-state-v1",
        "status": "failed_after_claim",
        "development_manifest_sha256": binding.development_manifest_sha256,
        "authorization_reference": authorization,
        "test_run": transaction.run_dir.as_posix(),
        "output_staging": output_staging.as_posix(),
        "output_failure_run_published": transaction.published,
        "claimed_at_utc": claimed_at_utc,
        "failed_stage": getattr(error, "stage", "model_scoring_or_publication"),
        "error_type": type(cause or error).__name__,
        "exit_code": int(code),
        "failed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "test_features_opened": test_features_opened,
        "terminal_receipt": True,
    }


def _store_failure_state(
    state: Path,
    binding: _Binding,
    transaction: RunTransaction,
    authorization: str,
    error: BaseException,
    *,
    claimed_at_utc: str,
    output_staging: Path,
    test_features_opened: bool,
) -> None:
    try:
        _replace_state(
            state,
            _failure_state(
                binding,
                transaction,
                authorization,
                error,
                claimed_at_utc=claimed_at_utc,
                output_staging=output_staging,
                test_features_opened=test_features_opened,
            ),
        )
    except BaseException:
        error.add_note("test-opening terminal state could not be durably updated")


def execute_test_opening(
    *,
    development_run: str | Path,
    run_dir: str | Path,
    authorization_reference: str,
    allowed_root: str | Path,
) -> TestOpeningResult:
    started = time.perf_counter()
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    authorization = _authorization_reference(authorization_reference)
    transaction = RunTransaction(
        run_dir,
        allowed_root=allowed_root,
        safe_failure_message="test-opening failed; see development state receipt",
        safe_failure_stage="output_transaction",
    )
    output_staging = transaction.path
    try:
        prechecked_run = _bound_input_run(development_run, allowed_root)
        state_candidate = prechecked_run / "state" / "test_opening.json"
        if os.path.lexists(state_candidate):
            raise TestOpeningRefused("development run already has a test-opening state")
        binding = _load_binding(prechecked_run, allowed_root=allowed_root)
        if os.path.lexists(state_candidate):
            raise TestOpeningRefused("development run already has a test-opening state")
    except BaseException:
        transaction.abort_without_receipt()
        raise
    claimed_at_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        state = _claim(
            binding,
            output_run=transaction.run_dir,
            authorization=authorization,
            staging=transaction.path,
            claimed_at_utc=claimed_at_utc,
        )
    except TestOpeningRefused:
        transaction.abort_without_receipt()
        raise
    except _ClaimPathError as error:
        if not error.claim_created:
            transaction.abort_without_receipt()
            if os.path.lexists(state_candidate):
                raise TestOpeningRefused(
                    "development run already has a test-opening state"
                ) from error
            raise
        wrapped = TestOpeningFailure("claim_durability", ExitCode.TRANSACTION)
        try:
            with transaction:
                raise wrapped from error
        except TestOpeningFailure:
            pass
        _store_failure_state(
            state_candidate,
            binding,
            transaction,
            authorization,
            wrapped,
            claimed_at_utc=claimed_at_utc,
            output_staging=output_staging,
            test_features_opened=False,
        )
        raise wrapped from error
    except BaseException:
        transaction.abort_without_receipt()
        raise
    opened = False
    try:
        with transaction:
            try:
                opened = True
                scores, metrics = _evaluate(binding)
            except InputBindingError as error:
                raise TestOpeningFailure("test_frame_binding", ExitCode.INPUT_BINDING) from error
            except TestOpeningFailure:
                raise
            except BaseException as error:
                raise TestOpeningFailure("model_scoring", ExitCode.INTERNAL_ERROR) from error
            try:
                _write_success_artifacts(
                    transaction,
                    binding,
                    scores,
                    metrics,
                    authorization=authorization,
                    started=started,
                    started_utc=started_utc,
                )
            except (OSError, RunPathError) as error:
                raise TestOpeningFailure("output_transaction", ExitCode.TRANSACTION) from error
            except TestOpeningFailure:
                raise
            except BaseException as error:
                raise TestOpeningFailure("publication_internal", ExitCode.INTERNAL_ERROR) from error
    except RunPathError as error:
        wrapped = TestOpeningFailure("output_transaction", ExitCode.TRANSACTION)
        _store_failure_state(
            state,
            binding,
            transaction,
            authorization,
            wrapped,
            claimed_at_utc=claimed_at_utc,
            output_staging=output_staging,
            test_features_opened=opened,
        )
        raise wrapped from error
    except BaseException as error:
        _store_failure_state(
            state,
            binding,
            transaction,
            authorization,
            error,
            claimed_at_utc=claimed_at_utc,
            output_staging=output_staging,
            test_features_opened=opened,
        )
        raise
    try:
        manifest_sha = sha256_file(transaction.run_dir / "artifacts/manifest.json")
    except BaseException as error:
        wrapped = TestOpeningFailure("terminal_receipt", ExitCode.TRANSACTION)
        _store_failure_state(
            state,
            binding,
            transaction,
            authorization,
            wrapped,
            claimed_at_utc=claimed_at_utc,
            output_staging=output_staging,
            test_features_opened=opened,
        )
        raise wrapped from error
    try:
        _replace_state(
            state,
            {
                "schema_version": "test-opening-state-v1",
                "status": metrics["status"],
                "development_manifest_sha256": binding.development_manifest_sha256,
                "authorization_reference": authorization,
                "claimed_at_utc": claimed_at_utc,
                "output_staging": output_staging.as_posix(),
                "test_run": transaction.run_dir.as_posix(),
                "test_manifest_sha256": manifest_sha,
                "completed_at_utc": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
                "test_features_opened": True,
                "terminal_receipt": True,
            },
        )
    except BaseException as error:
        raise TestOpeningFailure("terminal_receipt", ExitCode.TRANSACTION) from error
    LOGGER.info(
        "test-opening complete: status=%s run_dir=%s",
        metrics["status"],
        transaction.run_dir,
    )
    return TestOpeningResult(metrics["status"], transaction.run_dir)
