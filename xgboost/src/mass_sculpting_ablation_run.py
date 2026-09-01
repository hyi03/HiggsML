"""Safe source binding and terminal publication for the MC-only ablation study."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

from .external_zz_run import (
    _TRAINING_OUTPUT_NAMES,
    _assert_staged_manifest_unchanged,
    _open_verified_staged_manifest,
    _promote_bound_manifest_no_clobber,
    _read_safe_regular,
    _require_safe_directory,
)
from .features import FEATURES
from .full_training_policy import TrainingPolicy, load_training_policy
from .full_training_run import (
    TrainingInput,
    TrainingOutputLayout,
    _assert_empty_claimed_layout,
    _atomic_publish_bytes,
    _cleanup_staged,
    _close_descriptors,
    _csv_bytes,
    _entries,
    _entry_exists,
    _install_failure_locked as _training_install_failure_locked,
    _is_within,
    _json_bytes,
    _model_bytes,
    _open_claimed_directories,
    _open_verified_root,
    _output_record_from_descriptor,
    _revalidate_named_layout,
    _stage_bytes,
    _summary_label_counts,
    _terminal_lock_acquire,
    _terminal_lock_release,
    _validate_manifest,
    assert_input_hashes_unchanged,
    claim_training_output,
    resolve_training_output,
)
from .mass_sculpting_ablation import ABLATION_PROFILES


_COMMON_ARTIFACTS = frozenset(
    {
        "artifacts/profile_results.csv",
        "artifacts/selection.json",
        "plots/oof_profile_tradeoff.png",
    }
)
_SELECTED_ARTIFACTS = frozenset(
    {
        "artifacts/test_metrics.json",
        "model/xgboost_model.json",
        "predictions/selected_oof_scores.csv.gz",
        "predictions/test_scores.csv.gz",
        "plots/selected_mass_sculpting.png",
    }
)
_SOURCE_KEYS = frozenset(
    {
        "study_config",
        "task4a_config",
        "task4a_mc",
        "task4a_summary",
        "task4a_manifest",
        "reference_config",
        "reference_manifest",
        "reference_model",
        "reference_metrics",
    }
)


@dataclass(frozen=True)
class AblationConfig:
    schema_version: str
    input_run: str
    input_manifest_sha256: str
    reference_run: str
    reference_manifest_sha256: str
    auc_floor: float
    ks_limit: float
    profiles: Mapping[str, tuple[str, ...]]
    artifacts_no_selection: tuple[str, ...]
    artifacts_selected: tuple[str, ...]


@dataclass(frozen=True)
class StudySource:
    name: str
    path: Path
    size_bytes: int
    sha256: str
    snapshot: bytes | None = None

    @classmethod
    def from_path(
        cls, name: str, path: str | Path, *, capture: bool = False
    ) -> "StudySource":
        resolved = Path(os.path.abspath(path))
        payload = _read_safe_regular(resolved, name)
        return cls(
            name=name,
            path=resolved,
            size_bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            snapshot=payload if capture else None,
        )


@dataclass(frozen=True)
class AblationSources:
    config: AblationConfig
    config_bytes: bytes
    training_input: TrainingInput
    reference_run: Path
    policy: TrainingPolicy
    reference_summary: Mapping[str, Any]
    records: Mapping[str, StudySource]


_RECEIPT_TOKEN = object()


@dataclass(frozen=True, init=False)
class AblationArtifactReceipt:
    _run_identity: tuple[int, int]
    selected: bool

    def __new__(
        cls,
        token: object = None,
        run_identity: tuple[int, int] | None = None,
        selected: bool = False,
    ):
        if token is not _RECEIPT_TOKEN or run_identity is None:
            raise TypeError("AblationArtifactReceipt is returned by write_ablation_artifacts")
        return super().__new__(cls)

    def __init__(self, token: object, run_identity: tuple[int, int], selected: bool) -> None:
        object.__setattr__(self, "_run_identity", run_identity)
        object.__setattr__(self, "selected", bool(selected))


def approved_ablation_artifacts(*, selected: bool) -> set[str]:
    return set(_COMMON_ARTIFACTS | (_SELECTED_ARTIFACTS if selected else frozenset()))


def resolve_ablation_output(
    *,
    project_root: Path,
    working_directory: Path,
    input_run: Path,
    run_dir: Path,
    reference_run: Path | None = None,
) -> TrainingOutputLayout:
    """Use the already hardened fresh-path resolver and fixed directory layout."""
    layout = resolve_training_output(
        project_root=project_root,
        working_directory=working_directory,
        input_run=input_run,
        run_dir=run_dir,
    )
    if reference_run is not None and _is_within(
        layout.run_dir, Path(reference_run).resolve()
    ):
        raise ValueError("ablation --run-dir resolves inside the reference training run")
    return layout


def claim_ablation_output(layout: TrainingOutputLayout) -> TrainingOutputLayout:
    return claim_training_output(layout)


def load_ablation_config(path: str | Path) -> AblationConfig:
    config_path = Path(path)
    try:
        payload = config_path.read_bytes()
    except OSError as error:
        raise ValueError("ablation config is not valid YAML") from error
    return _load_ablation_config_bytes(payload)


def _load_ablation_config_bytes(payload: bytes) -> AblationConfig:
    try:
        raw = yaml.safe_load(payload)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ValueError("ablation config is not valid YAML") from error
    if not isinstance(raw, dict):
        raise ValueError("ablation config must be a mapping")
    expected_keys = {
        "schema_version",
        "input_run",
        "input_manifest_sha256",
        "reference_run",
        "reference_manifest_sha256",
        "auc_floor",
        "ks_limit",
        "profiles",
        "artifacts_no_selection",
        "artifacts_selected",
    }
    if set(raw) != expected_keys or raw.get("schema_version") != "1.0":
        raise ValueError("ablation config does not match schema 1.0")
    if raw.get("auc_floor") != 0.80 or raw.get("ks_limit") != 0.10:
        raise ValueError("ablation eligibility gates must remain 0.80 and 0.10")
    profiles = raw.get("profiles")
    expected_profiles = {
        name: list(profile.features) for name, profile in ABLATION_PROFILES.items()
    }
    if profiles != expected_profiles:
        raise ValueError("ablation profiles must match the exact canonical definitions")
    no_selection = raw.get("artifacts_no_selection")
    selected = raw.get("artifacts_selected")
    if not isinstance(no_selection, list) or set(no_selection) != approved_ablation_artifacts(selected=False):
        raise ValueError("no-selection artifacts do not match the approved allowlist")
    if not isinstance(selected, list) or set(selected) != approved_ablation_artifacts(selected=True):
        raise ValueError("selected artifacts do not match the approved allowlist")
    for key in (
        "input_run",
        "input_manifest_sha256",
        "reference_run",
        "reference_manifest_sha256",
    ):
        if not isinstance(raw.get(key), str) or not raw[key]:
            raise ValueError(f"ablation config {key} must be a non-empty string")
    for key in ("input_manifest_sha256", "reference_manifest_sha256"):
        if len(raw[key]) != 64 or any(character not in "0123456789abcdef" for character in raw[key]):
            raise ValueError(f"ablation config {key} must be a lowercase SHA-256")
    return AblationConfig(
        schema_version="1.0",
        input_run=raw["input_run"],
        input_manifest_sha256=raw["input_manifest_sha256"],
        reference_run=raw["reference_run"],
        reference_manifest_sha256=raw["reference_manifest_sha256"],
        auc_floor=0.80,
        ks_limit=0.10,
        profiles=MappingProxyType(
            {name: tuple(values) for name, values in profiles.items()}
        ),
        artifacts_no_selection=tuple(no_selection),
        artifacts_selected=tuple(selected),
    )


def resolve_ablation_sources(
    *, input_run: str | Path, reference_run: str | Path, config_path: str | Path
) -> AblationSources:
    config_source = StudySource.from_path("study_config", config_path, capture=True)
    config_bytes = config_source.snapshot
    if config_bytes is None:
        raise RuntimeError("ablation config snapshot is unavailable")
    config = _load_ablation_config_bytes(config_bytes)
    requested_input = Path(input_run).resolve()
    configured_input = Path(config.input_run).resolve()
    requested_reference = Path(reference_run).resolve()
    configured_reference = Path(config.reference_run).resolve()
    if requested_input != configured_input:
        raise ValueError("--input-run does not match the frozen ablation config")
    if requested_reference != configured_reference:
        raise ValueError("--reference-run does not match the frozen ablation config")

    training_input, task4a_records = _resolve_task4a_sources_without_table_load(
        input_run
    )
    if training_input.hashes["manifest"] != config.input_manifest_sha256:
        raise ValueError("Task 4A manifest does not match the frozen ablation config")
    reference, reference_summary = _resolve_reference_run(
        requested_reference, training_input, config
    )
    records = {
        "study_config": config_source,
        **task4a_records,
        **reference,
    }
    if set(records) != _SOURCE_KEYS:
        raise RuntimeError("ablation source inventory is incomplete")
    policy = load_training_policy(records["reference_config"].path)
    return AblationSources(
        config=config,
        config_bytes=config_bytes,
        training_input=training_input,
        reference_run=requested_reference,
        policy=policy,
        reference_summary=MappingProxyType(reference_summary),
        records=MappingProxyType(records),
    )


def _resolve_task4a_sources_without_table_load(
    input_run: str | Path,
) -> tuple[TrainingInput, dict[str, StudySource]]:
    run = _require_safe_directory(
        Path(os.path.abspath(input_run)), "Task 4A input run"
    )
    records = {
        "task4a_config": StudySource.from_path(
            "task4a_config", run / "config.yaml", capture=True
        ),
        "task4a_mc": StudySource.from_path(
            "task4a_mc", run / "processed/mc_events.csv.gz"
        ),
        "task4a_summary": StudySource.from_path(
            "task4a_summary", run / "artifacts/data_summary.json", capture=True
        ),
        "task4a_manifest": StudySource.from_path(
            "task4a_manifest", run / "artifacts/run_manifest.json", capture=True
        ),
    }
    hashes = MappingProxyType(
        {
            "config": records["task4a_config"].sha256,
            "mc": records["task4a_mc"].sha256,
            "summary": records["task4a_summary"].sha256,
            "manifest": records["task4a_manifest"].sha256,
        }
    )
    summary = _json_object(
        records["task4a_summary"].snapshot, "Task 4A summary"
    )
    manifest = _json_object(
        records["task4a_manifest"].snapshot, "Task 4A manifest"
    )
    _validate_manifest(manifest, hashes["config"])
    expected_rows = int(sum(_summary_label_counts(summary).values()))
    for name, source in records.items():
        current = StudySource.from_path(name, source.path)
        if current.sha256 != source.sha256 or current.size_bytes != source.size_bytes:
            raise RuntimeError("Task 4A input changed during ablation resolution")
    return (
        TrainingInput(
            input_run=run,
            config_path=records["task4a_config"].path,
            mc_path=records["task4a_mc"].path,
            summary_path=records["task4a_summary"].path,
            manifest_path=records["task4a_manifest"].path,
            hashes=hashes,
            expected_rows=expected_rows,
        ),
        records,
    )


def _resolve_reference_run(
    reference_run: Path, training_input: TrainingInput, config: AblationConfig
) -> tuple[dict[str, StudySource], dict[str, Any]]:
    reference_run = _require_safe_directory(reference_run, "reference training run")
    if (reference_run / "failure.json").exists() or (reference_run / "failure.json").is_symlink():
        raise ValueError("reference training run is failed")
    config_source = StudySource.from_path(
        "reference_config", reference_run / "config.yaml", capture=True
    )
    manifest_source = StudySource.from_path(
        "reference_manifest",
        reference_run / "artifacts/training_manifest.json",
        capture=True,
    )
    model_source = StudySource.from_path(
        "reference_model", reference_run / "model/xgboost_model.json"
    )
    metrics_source = StudySource.from_path(
        "reference_metrics", reference_run / "artifacts/metrics.json", capture=True
    )
    if manifest_source.sha256 != config.reference_manifest_sha256:
        raise ValueError("reference manifest does not match the frozen ablation config")
    manifest = _json_object(manifest_source.snapshot, "reference manifest")
    if manifest.get("schema_version") != "1.0" or manifest.get("status") != "complete":
        raise ValueError("reference training manifest must be complete schema 1.0")
    if manifest.get("features") != list(FEATURES):
        raise ValueError("reference training manifest must use the frozen 14 features")
    input_record = manifest.get("input_task4a")
    if not isinstance(input_record, Mapping):
        raise ValueError("reference manifest is missing Task 4A binding")
    if input_record.get("hashes") != dict(training_input.hashes):
        raise ValueError("reference training run is not bound to the requested Task 4A run")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, Mapping) or set(outputs) != set(_TRAINING_OUTPUT_NAMES):
        raise ValueError("reference manifest output receipts are incomplete")
    for relative, raw_record in outputs.items():
        if not isinstance(relative, str) or not isinstance(raw_record, Mapping):
            raise ValueError("reference output receipt is invalid")
        output_source = StudySource.from_path("reference_output", reference_run / relative)
        if (
            raw_record.get("sha256") != output_source.sha256
            or raw_record.get("size_bytes") != output_source.size_bytes
        ):
            raise ValueError(f"reference output receipt mismatch: {relative}")
    if outputs["config.yaml"].get("sha256") != config_source.sha256:
        raise ValueError("reference config receipt mismatch")
    if outputs["model/xgboost_model.json"].get("sha256") != model_source.sha256:
        raise ValueError("reference model receipt mismatch")
    if outputs["artifacts/metrics.json"].get("sha256") != metrics_source.sha256:
        raise ValueError("reference metrics receipt mismatch")
    metrics = _json_object(metrics_source.snapshot, "reference metrics")
    summary = _reference_summary(manifest, metrics)
    return (
        {
            "reference_config": config_source,
            "reference_manifest": manifest_source,
            "reference_model": model_source,
            "reference_metrics": metrics_source,
        },
        summary,
    )


def _reference_summary(
    manifest: Mapping[str, Any], metrics: Mapping[str, Any]
) -> dict[str, Any]:
    development = metrics.get("development_oof")
    sculpting = metrics.get("mass_sculpting")
    oof_zz = sculpting.get("oof_zz") if isinstance(sculpting, Mapping) else None
    diagnostics = oof_zz.get("working_points") if isinstance(oof_zz, Mapping) else None
    points = manifest.get("working_points")
    selected_model = manifest.get("selected_model")
    if not all(
        isinstance(value, Mapping)
        for value in (development, oof_zz, diagnostics, points, selected_model)
    ):
        raise ValueError("reference metrics are missing OOF comparison evidence")
    names = {"loose", "medium", "tight"}
    if set(diagnostics) != names or set(points) != names:
        raise ValueError("reference metrics have incomplete working points")
    summary = {
        "profile": "full14_reference",
        "features": tuple(FEATURES),
        "candidate": selected_model.get("candidate"),
        "final_tree_count": selected_model.get("final_tree_count"),
        "weighted_auc": development.get("weighted_auc"),
        "score_mass_correlation": oof_zz.get("weighted_score_mass_correlation"),
        "working_points": {
            name: {
                "threshold": points[name].get("threshold"),
                "signal_efficiency": points[name].get("signal_efficiency"),
                "target_background_efficiency": points[name].get(
                    "target_background_efficiency"
                ),
                "zz_ks_distance": diagnostics[name].get(
                    "inclusive_to_selected_ks_distance"
                ),
            }
            for name in ("loose", "medium", "tight")
        },
        "eligibility_reasons": ("reference_only", "zz_mass_ks_exceeds_limit"),
    }
    numeric = [
        summary["final_tree_count"],
        summary["weighted_auc"],
        summary["score_mass_correlation"],
        *(
            value
            for point in summary["working_points"].values()
            for value in point.values()
        ),
    ]
    try:
        finite = np.isfinite(np.asarray(numeric, dtype=float)).all()
    except (TypeError, ValueError) as error:
        raise ValueError("reference comparison metrics must be numeric") from error
    if not finite or not isinstance(summary["candidate"], str):
        raise ValueError("reference comparison metrics must be finite")
    return summary


def assert_ablation_sources_unchanged(sources: AblationSources) -> None:
    if not isinstance(sources, AblationSources):
        raise TypeError("sources must be AblationSources")
    assert_input_hashes_unchanged(sources.training_input)
    for source in sources.records.values():
        current = StudySource.from_path(source.name, source.path)
        if current.size_bytes != source.size_bytes or current.sha256 != source.sha256:
            raise RuntimeError(f"ablation source changed during study: {source.name}")


def summarize_mc_source_rows(
    frame: pd.DataFrame, expected_rows: int
) -> Mapping[str, Any]:
    if not isinstance(frame, pd.DataFrame) or "split" not in frame:
        raise TypeError("loaded Task 4A MC must be a DataFrame with split")
    if len(frame) != expected_rows:
        raise ValueError("Task 4A summary selected event count does not match MC rows")
    counts = frame["split"].value_counts(dropna=False).to_dict()
    if set(counts) != {"train", "validation", "test"}:
        raise ValueError("Task 4A MC split row counts are incomplete")
    normalized = {name: int(counts[name]) for name in ("train", "validation", "test")}
    if any(value <= 0 for value in normalized.values()) or sum(normalized.values()) != len(frame):
        raise ValueError("Task 4A MC split row counts are invalid")
    return MappingProxyType(
        {"row_count": int(len(frame)), "rows_by_split": MappingProxyType(normalized)}
    )


def write_ablation_artifacts(
    layout: TrainingOutputLayout,
    *,
    config_source: Path,
    config_bytes: bytes,
    profile_results: pd.DataFrame,
    selection: Mapping[str, Any],
    plot_artifacts: Mapping[str, bytes],
    model: Any | None = None,
    test_metrics: Mapping[str, Any] | None = None,
    selected_oof_scores: pd.DataFrame | None = None,
    test_scores: pd.DataFrame | None = None,
) -> AblationArtifactReceipt:
    selected = model is not None
    descriptors: dict[str, int] | None = None
    try:
        descriptors = _open_claimed_directories(layout)
        if _entry_exists(descriptors["."], ".terminal.failed") or _entry_exists(descriptors["."], "failure.json"):
            raise RuntimeError("cannot write a failed ablation run")
        _assert_empty_claimed_layout(descriptors)
        _validate_write_contract(
            selected=selected,
            profile_results=profile_results,
            selection=selection,
            plot_artifacts=plot_artifacts,
            test_metrics=test_metrics,
            selected_oof_scores=selected_oof_scores,
            test_scores=test_scores,
        )
        serialized_profile_results = _plain_csv_bytes(profile_results)
        serialized_selection = _json_bytes(selection)
        serialized_test_metrics = None if test_metrics is None else _json_bytes(test_metrics)
        serialized_model = None if model is None else _model_bytes(model)
        serialized_oof = None if selected_oof_scores is None else _csv_bytes(selected_oof_scores)
        serialized_test = None if test_scores is None else _csv_bytes(test_scores)
        if not isinstance(config_bytes, bytes) or config_source.read_bytes() != config_bytes:
            raise RuntimeError("ablation config changed before snapshot write")

        _atomic_publish_bytes(descriptors["."], layout.run_dir, "config.yaml", config_bytes)
        _atomic_publish_bytes(
            descriptors["artifacts"], layout.artifacts_dir, "profile_results.csv", serialized_profile_results
        )
        _atomic_publish_bytes(
            descriptors["artifacts"], layout.artifacts_dir, "selection.json", serialized_selection
        )
        _atomic_publish_bytes(
            descriptors["plots"], layout.plots_dir, "oof_profile_tradeoff.png",
            plot_artifacts["oof_profile_tradeoff.png"],
        )
        if selected:
            _atomic_publish_bytes(descriptors["model"], layout.model_dir, "xgboost_model.json", serialized_model)
            _atomic_publish_bytes(descriptors["artifacts"], layout.artifacts_dir, "test_metrics.json", serialized_test_metrics)
            _atomic_publish_bytes(descriptors["predictions"], layout.predictions_dir, "selected_oof_scores.csv.gz", serialized_oof)
            _atomic_publish_bytes(descriptors["predictions"], layout.predictions_dir, "test_scores.csv.gz", serialized_test)
            _atomic_publish_bytes(
                descriptors["plots"], layout.plots_dir, "selected_mass_sculpting.png",
                plot_artifacts["selected_mass_sculpting.png"],
            )
        _assert_ablation_contract(
            descriptors, selected=selected, manifest_present=False, terminal_lock_present=False
        )
        return AblationArtifactReceipt(
            _RECEIPT_TOKEN, layout.directory_identities["."], selected
        )
    except Exception as error:
        record_ablation_failure(layout, error)
        raise
    finally:
        _close_descriptors(descriptors)


def _validate_write_contract(
    *,
    selected: bool,
    profile_results: pd.DataFrame,
    selection: Mapping[str, Any],
    plot_artifacts: Mapping[str, bytes],
    test_metrics: Mapping[str, Any] | None,
    selected_oof_scores: pd.DataFrame | None,
    test_scores: pd.DataFrame | None,
) -> None:
    if not isinstance(profile_results, pd.DataFrame):
        raise TypeError("profile_results must be a DataFrame")
    _validate_finite_frame(profile_results, "profile_results")
    if not isinstance(selection, Mapping):
        raise TypeError("selection must be a mapping")
    expected_plots = {"oof_profile_tradeoff.png"} | ({"selected_mass_sculpting.png"} if selected else set())
    if set(plot_artifacts) != expected_plots:
        raise ValueError("plot outputs do not match the conditional allowlist")
    for name, payload in plot_artifacts.items():
        if not isinstance(payload, bytes) or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"plot output is not a PNG: {name}")
    optional = (test_metrics, selected_oof_scores, test_scores)
    if selected and any(value is None for value in optional):
        raise FileNotFoundError("selected study is missing test-only artifacts")
    if not selected and any(value is not None for value in optional):
        raise ValueError("no-selection study contains test-only artifacts")
    if selected:
        if not isinstance(test_metrics, Mapping):
            raise TypeError("test_metrics must be a mapping")
        _json_bytes(test_metrics)
        _validate_finite_frame(selected_oof_scores, "selected_oof_scores")
        _validate_finite_frame(test_scores, "test_scores")
    _json_bytes(selection)


def _validate_finite_frame(frame: pd.DataFrame, name: str) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{name} must be a DataFrame")
    numeric = frame.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError(f"{name} contains non-finite numeric content")


def _plain_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")


def publish_ablation_manifest(
    layout: TrainingOutputLayout,
    *,
    receipt: AblationArtifactReceipt,
    sources: Mapping[str, StudySource],
    source_row_counts: Mapping[str, Any],
    decision: Mapping[str, Any],
    software: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(receipt, AblationArtifactReceipt):
        raise FileNotFoundError("publisher requires an ablation artifact receipt")
    if layout.directory_identities is None or receipt._run_identity != layout.directory_identities.get("."):
        raise ValueError("artifact receipt does not belong to this claimed run")
    try:
        if set(sources) != _SOURCE_KEYS or any(
            not isinstance(source, StudySource) or source.name != name
            for name, source in sources.items()
        ):
            raise ValueError("ablation source inventory does not match the approved contract")
        normalized_rows = _validate_source_row_counts(source_row_counts)
        _validate_decision(receipt.selected, decision)
    except Exception as error:
        record_ablation_failure(layout, error)
        raise
    descriptors: dict[str, int] | None = None
    locked = False
    staged_manifest: str | None = None
    staged_descriptor: int | None = None
    try:
        descriptors = _open_claimed_directories(layout)
        root = descriptors["."]
        _terminal_lock_acquire(root)
        locked = True
        if _entry_exists(root, ".terminal.failed") or _entry_exists(root, "failure.json"):
            raise RuntimeError("cannot publish a failed ablation run")
        _assert_ablation_contract(
            descriptors,
            selected=receipt.selected,
            manifest_present=False,
            terminal_lock_present=True,
        )
        outputs = _build_output_records(layout, descriptors, selected=receipt.selected)
        manifest = {
            "schema_version": "1.0",
            "status": "complete",
            "decision": dict(decision),
            "software": dict(software),
            "sources": {
                name: {
                    "path": str(source.path),
                    "size_bytes": source.size_bytes,
                    "sha256": source.sha256,
                    **(normalized_rows if name == "task4a_mc" else {}),
                }
                for name, source in sources.items()
            },
            "outputs": outputs,
        }
        serialized = _json_bytes(manifest)
        staged_manifest = _stage_bytes(
            descriptors["artifacts"], "study_manifest.json", serialized
        )
        staged_descriptor, staged_identity = _open_verified_staged_manifest(
            descriptors["artifacts"], staged_manifest, serialized
        )

        def final_check() -> None:
            for source in sources.values():
                current = StudySource.from_path(source.name, source.path)
                if current.sha256 != source.sha256 or current.size_bytes != source.size_bytes:
                    raise RuntimeError(f"ablation source changed during study: {source.name}")
            _assert_staged_manifest_unchanged(
                descriptors["artifacts"],
                staged_manifest,
                staged_descriptor,
                staged_identity,
                serialized,
            )
            if _build_output_records(
                layout, descriptors, selected=receipt.selected
            ) != outputs:
                raise RuntimeError("ablation output changed before manifest publication")
            _revalidate_named_layout(layout)

        _promote_bound_manifest_no_clobber(
            descriptors["artifacts"],
            layout.artifacts_dir,
            staged_manifest,
            staged_descriptor,
            staged_identity,
            serialized,
            "study_manifest.json",
            immediate_check=final_check,
        )
        staged_manifest = None
        os.close(staged_descriptor)
        staged_descriptor = None
        _assert_ablation_contract(
            descriptors,
            selected=receipt.selected,
            manifest_present=True,
            terminal_lock_present=True,
        )
        return manifest
    except Exception as error:
        if descriptors is not None:
            _cleanup_staged(descriptors.get("artifacts", descriptors["."]), staged_manifest)
            if locked:
                _training_install_failure_locked(descriptors["."], layout.run_dir, error)
            else:
                record_ablation_failure(layout, error)
        else:
            record_ablation_failure(layout, error)
        raise
    finally:
        if descriptors is not None and locked:
            _terminal_lock_release(descriptors["."])
        if staged_descriptor is not None:
            os.close(staged_descriptor)
        _close_descriptors(descriptors)


def _validate_source_row_counts(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"row_count", "rows_by_split"}:
        raise ValueError("source row counts do not match the approved contract")
    rows_by_split = value["rows_by_split"]
    if not isinstance(rows_by_split, Mapping) or set(rows_by_split) != {
        "train", "validation", "test"
    }:
        raise ValueError("source row counts do not match the approved contract")
    if any(
        isinstance(item, bool) or not isinstance(item, (int, np.integer)) or int(item) <= 0
        for item in rows_by_split.values()
    ):
        raise ValueError("source row counts must be positive integers")
    row_count = value["row_count"]
    if (
        isinstance(row_count, bool)
        or not isinstance(row_count, (int, np.integer))
        or int(row_count) != sum(int(item) for item in rows_by_split.values())
    ):
        raise ValueError("source row count must equal the split row counts")
    return {
        "row_count": int(row_count),
        "rows_by_split": {
            name: int(rows_by_split[name]) for name in ("train", "validation", "test")
        },
    }


def _validate_decision(selected: bool, decision: Mapping[str, Any]) -> None:
    if not isinstance(decision, Mapping):
        raise TypeError("ablation decision must be a mapping")
    status = decision.get("status")
    profile = decision.get("selected_profile")
    if not selected and (status != "no_eligible_profile" or profile is not None):
        raise ValueError("ablation decision contradicts no-selection artifacts")
    if selected and (
        status not in {"successful_simple_mitigation", "test_nonreproduction"}
        or not isinstance(profile, str)
        or not profile
    ):
        raise ValueError("ablation decision contradicts selected artifacts")


def _assert_ablation_contract(
    descriptors: Mapping[str, int], *, selected: bool, manifest_present: bool, terminal_lock_present: bool
) -> None:
    root_expected = {"config.yaml", "model", "artifacts", "predictions", "plots"}
    if terminal_lock_present:
        root_expected.add(".terminal.lock")
    if _entries(descriptors["."]) != root_expected:
        raise ValueError("ablation run root does not match the approved contract")
    relative = approved_ablation_artifacts(selected=selected)
    expected = {
        "model": {Path(name).name for name in relative if name.startswith("model/")},
        "artifacts": {Path(name).name for name in relative if name.startswith("artifacts/")},
        "predictions": {Path(name).name for name in relative if name.startswith("predictions/")},
        "plots": {Path(name).name for name in relative if name.startswith("plots/")},
    }
    if manifest_present:
        expected["artifacts"].add("study_manifest.json")
    for directory, names in expected.items():
        actual = _entries(descriptors[directory])
        if actual != names:
            if names - actual:
                raise FileNotFoundError(f"required ablation output is missing in {directory}")
            raise ValueError(f"unexpected ablation output entry in {directory}")


def _build_output_records(
    layout: TrainingOutputLayout, descriptors: Mapping[str, int], *, selected: bool
) -> dict[str, dict[str, Any]]:
    outputs: dict[str, dict[str, Any]] = {}
    config_record, _ = _output_record_from_descriptor(
        descriptors["."], layout.config_snapshot, csv_rows=False
    )
    outputs["config.yaml"] = config_record
    for relative in sorted(approved_ablation_artifacts(selected=selected)):
        directory, filename = relative.split("/", 1)
        path = layout.run_dir / relative
        csv_rows = relative.endswith(".csv") or relative.endswith(".csv.gz")
        compression = "gzip" if relative.endswith(".csv.gz") else None
        record, _ = _output_record_from_descriptor(
            descriptors[directory], path, csv_rows=csv_rows, compression=compression
        )
        outputs[relative] = record
    return outputs


def record_ablation_failure(layout: TrainingOutputLayout, error: BaseException) -> None:
    """Install one no-clobber failure terminal unless completion already exists."""
    try:
        root = _open_verified_root(layout)
    except Exception:
        return
    locked = False
    try:
        _terminal_lock_acquire(root)
        locked = True
        try:
            artifacts = os.open("artifacts", os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0), dir_fd=root)
        except OSError:
            artifacts = None
        try:
            if artifacts is not None and _entry_exists(artifacts, "study_manifest.json"):
                return
        finally:
            if artifacts is not None:
                os.close(artifacts)
        _training_install_failure_locked(root, layout.run_dir, error)
    except Exception:
        pass
    finally:
        if locked:
            _terminal_lock_release(root)
        os.close(root)


def _json_object(payload: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} is not valid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value
