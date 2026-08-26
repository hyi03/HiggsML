"""Safe source binding and manifest-last publication for mass-bin reweighting."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

from .external_zz_run import (
    _assert_staged_manifest_unchanged,
    _open_verified_staged_manifest,
    _promote_bound_manifest_no_clobber,
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
    _install_failure_locked,
    _json_bytes,
    _model_bytes,
    _open_claimed_directories,
    _read_entry_bytes,
    _open_verified_root,
    _output_record_from_descriptor,
    _revalidate_named_layout,
    _stage_bytes,
    _terminal_lock_acquire,
    _terminal_lock_release,
)
from .mass_bin_reweighting import ReweightingPolicy, approved_reweighting_features
from .mass_sculpting_ablation_run import (
    StudySource,
    _resolve_reference_run,
    _resolve_task4a_sources_without_table_load,
    resolve_ablation_output,
    summarize_mc_source_rows,
)


_COMMON = frozenset(
    {
        "artifacts/iteration_results.csv",
        "artifacts/bin_efficiencies.csv",
        "artifacts/weight_multipliers.csv",
        "artifacts/selection.json",
        "plots/iteration_tradeoff.png",
        "plots/zz_efficiency_by_mass.png",
    }
)
_SELECTED = frozenset(
    {
        "artifacts/test_metrics.json",
        "model/xgboost_model.json",
        "predictions/selected_oof_scores.csv.gz",
        "predictions/test_scores.csv.gz",
        "plots/selected_mass_sculpting.png",
    }
)
_MANIFEST = "artifacts/study_manifest.json"
_FULL14_SOURCE_KEYS = frozenset(
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
        "ablation_manifest",
        "raw_zz",
    }
)
_DROP_TOP4_SOURCE_KEYS = _FULL14_SOURCE_KEYS | {
    "reweighting_reference_manifest",
}
_FULL14_FEATURES = approved_reweighting_features(tuple(FEATURES))
_DROP_TOP4_FEATURES = approved_reweighting_features((
    "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
    "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
))
_ANGULAR5_R3_ARM64_FEATURES = approved_reweighting_features((
    "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
    "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
    "cos_theta_star", "cos_theta_1", "cos_theta_2", "phi_decay_planes",
    "phi_production_plane",
))
_EDGES = tuple(float(value) for value in range(105, 161, 5))
_INPUT_HASH = "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8"
_REFERENCE_HASH = "da015d0a00bb002e69dc98eb9631c1b561af65f8da44b78a641d4e013558bf65"
_ABLATION_HASH = "5120e6080e82b14f66917ba731c98715fa5d6190c25c396d8c675200e9ca52df"
_RAW_ZZ_HASH = "76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07"
_MAXIMUM_CORRECTIONS = 5
_ANGULAR5_R3_ARM64_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "config/mass_bin_reweighting_drop_top4_angular5_r3_arm64.yaml"
).resolve()


@dataclass(frozen=True)
class MassBinReweightingConfig:
    schema_version: str
    input_run: str
    input_manifest_sha256: str
    reference_run: str
    reference_manifest_sha256: str
    ablation_run: str
    ablation_manifest_sha256: str
    raw_zz_path: str
    raw_zz_sha256: str
    reweighting_reference_run: str | None
    reweighting_reference_manifest_sha256: str | None
    features: tuple[str, ...]
    mass_bin_edges: tuple[float, ...]
    minimum_effective_count: float
    epsilon_floor: float
    damping: float
    round_factor_bounds: tuple[float, float]
    cumulative_bounds: tuple[float, float]
    maximum_corrections: int
    auc_floor: float
    ks_limit: float
    require_signal_efficiency_above_zz: bool
    artifacts_no_selection: tuple[str, ...]
    artifacts_selected: tuple[str, ...]
    input_table_path: str | None = None
    input_table_sha256: str | None = None


@dataclass(frozen=True)
class ReweightingSources:
    config: MassBinReweightingConfig
    config_bytes: bytes
    training_input: TrainingInput
    reference_run: Path
    ablation_run: Path
    raw_zz_path: Path
    policy: TrainingPolicy
    reweighting_policy: ReweightingPolicy
    records: Mapping[str, StudySource]
    reweighting_reference_run: Path | None = None


_RECEIPT_TOKEN = object()


@dataclass(frozen=True, init=False)
class ReweightingArtifactReceipt:
    _run_identity: tuple[int, int]
    selected: bool
    _decision_bytes: bytes
    _audit_bytes: bytes
    _features: tuple[str, ...]

    def __new__(
        cls, token: object = None, run_identity=None, selected: bool = False,
        decision_bytes: bytes | None = None, audit_bytes: bytes | None = None,
        features: tuple[str, ...] | None = None,
    ):
        if (
            token is not _RECEIPT_TOKEN or run_identity is None
            or decision_bytes is None or audit_bytes is None or features is None
        ):
            raise TypeError("ReweightingArtifactReceipt is returned by write_reweighting_artifacts")
        return super().__new__(cls)

    def __init__(
        self, token: object, run_identity: tuple[int, int], selected: bool,
        decision_bytes: bytes, audit_bytes: bytes, features: tuple[str, ...],
    ):
        object.__setattr__(self, "_run_identity", run_identity)
        object.__setattr__(self, "selected", bool(selected))
        object.__setattr__(self, "_decision_bytes", decision_bytes)
        object.__setattr__(self, "_audit_bytes", audit_bytes)
        object.__setattr__(self, "_features", approved_reweighting_features(features))


def approved_reweighting_artifacts(*, selected: bool) -> set[str]:
    return {"config.yaml", _MANIFEST, *_COMMON, *(_SELECTED if selected else ())}


def _source_keys_for_features(features: tuple[str, ...]) -> frozenset[str]:
    captured = approved_reweighting_features(features)
    return (
        _FULL14_SOURCE_KEYS
        if captured == _FULL14_FEATURES
        else _DROP_TOP4_SOURCE_KEYS
    )


def load_mass_bin_reweighting_config(path: str | Path) -> MassBinReweightingConfig:
    try:
        payload = Path(path).read_bytes()
    except OSError as error:
        raise ValueError("mass-bin reweighting config is not valid YAML") from error
    return _load_config_bytes(payload)


def _load_config_bytes(payload: bytes) -> MassBinReweightingConfig:
    try:
        raw = yaml.safe_load(payload)
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ValueError("mass-bin reweighting config is not valid YAML") from error
    common = {
        "schema_version", "input_run", "input_manifest_sha256", "reference_run",
        "reference_manifest_sha256", "ablation_run", "ablation_manifest_sha256",
        "raw_zz_path", "raw_zz_sha256", "features", "mass_bin_edges",
        "minimum_effective_count", "epsilon_floor", "damping",
        "round_factor_bounds", "cumulative_bounds", "maximum_corrections",
        "auc_floor", "ks_limit", "require_signal_efficiency_above_zz",
        "artifacts_no_selection", "artifacts_selected",
    }
    new = common | {
        "reweighting_reference_run", "reweighting_reference_manifest_sha256",
    }
    angular5 = new | {"input_table_path", "input_table_sha256"}
    if not isinstance(raw, dict):
        raise ValueError("mass-bin reweighting config does not match an approved schema")
    schema_version = raw.get("schema_version")
    if schema_version == "1.0" and set(raw) == common:
        expected_features = _FULL14_FEATURES
        reference_run = None
        reference_hash = None
    elif schema_version == "1.1" and set(raw) == new:
        expected_features = _DROP_TOP4_FEATURES
        reference_run = "runs/mass-reweighting-363490-2026-08-11"
        reference_hash = "145e38478dfd12310a82f4ed544c6cf0b09204cbc1c7d08e6e485941c00f9e38"
    elif schema_version == "1.2" and set(raw) == angular5:
        expected_features = _ANGULAR5_R3_ARM64_FEATURES
        reference_run = "runs/mass-reweighting-363490-2026-08-11"
        reference_hash = "145e38478dfd12310a82f4ed544c6cf0b09204cbc1c7d08e6e485941c00f9e38"
    else:
        raise ValueError("mass-bin reweighting config does not match an approved schema")
    raw_features = raw.get("features")
    if not isinstance(raw_features, list) or any(type(item) is not str for item in raw_features):
        raise ValueError("mass-bin reweighting config changes a frozen decision")
    try:
        features = approved_reweighting_features(tuple(raw_features))
    except ValueError as error:
        raise ValueError("mass-bin reweighting config changes a frozen decision") from error
    expected_input_run = (
        "runs/angular5-mc-363490-2026-08-26-r3-arm64"
        if schema_version == "1.2"
        else "runs/full-baseline-363490-2026-08-11-r2"
    )
    expected_input_hash = (
        "ab5e283f4b6a2038a100a2a9d4e6745cccc3ee7f400ef056bcd05d3c22f28ad5"
        if schema_version == "1.2" else _INPUT_HASH
    )
    expected_table_path = (
        "runs/angular5-mc-363490-2026-08-26-r3-arm64/processed/mc_events_angular5.csv.gz"
    )
    expected_table_hash = "bc31f4e65ccecc0a1962648cfe240b67d8ecc6df8eda2478b3f46c93d2f34f09"
    exact = (
        raw.get("input_run") == expected_input_run
        and raw.get("input_manifest_sha256") == expected_input_hash
        and raw.get("reference_run") == "runs/full-training-363490-2026-08-11-r2"
        and raw.get("reference_manifest_sha256") == _REFERENCE_HASH
        and raw.get("ablation_run") == "runs/mass-ablation-363490-2026-08-11"
        and raw.get("ablation_manifest_sha256") == _ABLATION_HASH
        and raw.get("raw_zz_path") == "data/raw/zz_363490.root"
        and raw.get("raw_zz_sha256") == _RAW_ZZ_HASH
        and features == expected_features
        and raw.get("mass_bin_edges") == list(range(105, 161, 5))
        and type(raw.get("minimum_effective_count")) is float and raw["minimum_effective_count"] == 100.0
        and type(raw.get("epsilon_floor")) is float and raw["epsilon_floor"] == 1e-6
        and type(raw.get("damping")) is float and raw["damping"] == 0.5
        and raw.get("round_factor_bounds") == [0.5, 2.0]
        and raw.get("cumulative_bounds") == [0.2, 5.0]
        and type(raw.get("maximum_corrections")) is int and raw["maximum_corrections"] == 5
        and type(raw.get("auc_floor")) is float and raw["auc_floor"] == 0.80
        and type(raw.get("ks_limit")) is float and raw["ks_limit"] == 0.10
        and raw.get("require_signal_efficiency_above_zz") is True
        and raw.get("reweighting_reference_run", reference_run) == reference_run
        and raw.get("reweighting_reference_manifest_sha256", reference_hash) == reference_hash
        and (
            schema_version != "1.2"
            or (
                raw.get("input_table_path") == expected_table_path
                and raw.get("input_table_sha256") == expected_table_hash
            )
        )
    )
    if not exact:
        raise ValueError("mass-bin reweighting config changes a frozen decision")
    no_selection = raw.get("artifacts_no_selection")
    selected = raw.get("artifacts_selected")
    if (
        not isinstance(no_selection, list)
        or len(no_selection) != len(set(no_selection))
        or set(no_selection) != approved_reweighting_artifacts(selected=False)
        or not isinstance(selected, list)
        or len(selected) != len(set(selected))
        or set(selected) != approved_reweighting_artifacts(selected=True)
    ):
        raise ValueError("conditional artifact allowlists do not match the approved contract")
    return MassBinReweightingConfig(
        schema_version=schema_version,
        input_run=raw["input_run"],
        input_manifest_sha256=expected_input_hash,
        reference_run=raw["reference_run"],
        reference_manifest_sha256=_REFERENCE_HASH,
        ablation_run=raw["ablation_run"],
        ablation_manifest_sha256=_ABLATION_HASH,
        raw_zz_path=raw["raw_zz_path"],
        raw_zz_sha256=_RAW_ZZ_HASH,
        reweighting_reference_run=reference_run,
        reweighting_reference_manifest_sha256=reference_hash,
        features=features,
        mass_bin_edges=_EDGES,
        minimum_effective_count=100.0,
        epsilon_floor=1e-6,
        damping=0.5,
        round_factor_bounds=(0.5, 2.0),
        cumulative_bounds=(0.2, 5.0),
        maximum_corrections=5,
        auc_floor=0.80,
        ks_limit=0.10,
        require_signal_efficiency_above_zz=True,
        artifacts_no_selection=tuple(no_selection),
        artifacts_selected=tuple(selected),
        input_table_path=(expected_table_path if schema_version == "1.2" else None),
        input_table_sha256=(expected_table_hash if schema_version == "1.2" else None),
    )


def resolve_reweighting_output(
    *, project_root: Path, working_directory: Path, input_run: Path,
    reference_run: Path, run_dir: Path, ablation_run: Path | None = None,
    raw_zz_path: Path | None = None,
    reweighting_reference_run: Path | None = None,
) -> TrainingOutputLayout:
    layout = resolve_ablation_output(
        project_root=project_root,
        working_directory=working_directory,
        input_run=input_run,
        reference_run=reference_run,
        run_dir=run_dir,
    )
    protected = (
        Path(ablation_run) if ablation_run is not None else project_root / "runs/mass-ablation-363490-2026-08-11",
        Path(raw_zz_path) if raw_zz_path is not None else project_root / "data/raw/zz_363490.root",
        *((Path(reweighting_reference_run),) if reweighting_reference_run is not None else ()),
    )
    for source in protected:
        try:
            layout.run_dir.relative_to(source.resolve())
        except ValueError:
            continue
        raise ValueError("reweighting --run-dir resolves at or inside a protected source")
    return layout


def claim_reweighting_output(layout: TrainingOutputLayout) -> TrainingOutputLayout:
    from .full_training_run import claim_training_output
    return claim_training_output(layout)


def resolve_reweighting_sources(
    *, input_run: str | Path, reference_run: str | Path, config_path: str | Path,
) -> ReweightingSources:
    config_source = StudySource.from_path("study_config", config_path, capture=True)
    if config_source.snapshot is None:
        raise RuntimeError("study config snapshot is unavailable")
    config = _load_config_bytes(config_source.snapshot)
    if (
        config.schema_version == "1.2"
        and config_source.path != _ANGULAR5_R3_ARM64_CONFIG
    ):
        raise ValueError("R3-ARM64 reweighting requires the canonical R3-ARM64 config")
    requested_input = Path(input_run).resolve()
    requested_reference = Path(reference_run).resolve()
    requested_ablation = Path(config.ablation_run).resolve()
    requested_raw_zz = Path(config.raw_zz_path).resolve()
    requested_reweighting_reference = (
        None if config.reweighting_reference_run is None
        else Path(config.reweighting_reference_run).resolve()
    )
    if requested_input != Path(config.input_run).resolve():
        raise ValueError("--input-run does not match the frozen reweighting config")
    if requested_reference != Path(config.reference_run).resolve():
        raise ValueError("--reference-run does not match the frozen reweighting config")
    if config.schema_version == "1.2":
        training_input, task4a = _resolve_angular5_r3_arm64_sources(
            requested_input, config
        )
    else:
        training_input, task4a = _resolve_task4a_sources_without_table_load(requested_input)
    if training_input.hashes["manifest"] != config.input_manifest_sha256:
        raise ValueError("Task 4A manifest does not match the frozen reweighting config")
    if config.schema_version == "1.2":
        reference = _resolve_angular5_r3_arm64_reference(requested_reference, config)
    else:
        reference, _ = _resolve_reference_run(requested_reference, training_input, config)
    ablation_manifest = StudySource.from_path(
        "ablation_manifest", requested_ablation / "artifacts/study_manifest.json"
    )
    raw_zz = StudySource.from_path("raw_zz", requested_raw_zz)
    if ablation_manifest.sha256 != config.ablation_manifest_sha256:
        raise ValueError("mass-ablation manifest does not match the frozen reweighting config")
    if raw_zz.sha256 != config.raw_zz_sha256:
        raise ValueError("raw ZZ input does not match the frozen reweighting config")
    records = {
        "study_config": config_source, **task4a, **reference,
        "ablation_manifest": ablation_manifest, "raw_zz": raw_zz,
    }
    if requested_reweighting_reference is not None:
        reweighting_manifest = StudySource.from_path(
            "reweighting_reference_manifest",
            requested_reweighting_reference / "artifacts/study_manifest.json",
        )
        if reweighting_manifest.sha256 != config.reweighting_reference_manifest_sha256:
            raise ValueError("reweighting reference manifest does not match the frozen config")
        records["reweighting_reference_manifest"] = reweighting_manifest
    if set(records) != _source_keys_for_features(config.features):
        raise RuntimeError("reweighting source inventory is incomplete")
    return ReweightingSources(
        config=config,
        config_bytes=config_source.snapshot,
        training_input=training_input,
        reference_run=requested_reference,
        ablation_run=requested_ablation,
        raw_zz_path=requested_raw_zz,
        reweighting_reference_run=requested_reweighting_reference,
        policy=load_training_policy(records["reference_config"].path),
        reweighting_policy=ReweightingPolicy(
            mass_bin_edges=config.mass_bin_edges,
            minimum_effective_count=config.minimum_effective_count,
            epsilon_floor=config.epsilon_floor,
            damping=config.damping,
            round_factor_bounds=config.round_factor_bounds,
            cumulative_bounds=config.cumulative_bounds,
            maximum_corrections=config.maximum_corrections,
            auc_floor=config.auc_floor,
            ks_limit=config.ks_limit,
        ),
        records=MappingProxyType(records),
    )


def _resolve_angular5_r3_arm64_sources(
    input_run: Path, config: MassBinReweightingConfig,
) -> tuple[TrainingInput, dict[str, StudySource]]:
    table_path = Path(config.input_table_path or "")
    if table_path.resolve() != (input_run / "processed/mc_events_angular5.csv.gz").resolve():
        raise ValueError("R3-ARM64 Angular5 table path does not match the frozen config")
    records = {
        "task4a_config": StudySource.from_path("task4a_config", input_run / "config.yaml"),
        "task4a_mc": StudySource.from_path("task4a_mc", table_path),
        "task4a_summary": StudySource.from_path(
            "task4a_summary", input_run / "artifacts/angular5_summary.json", capture=True
        ),
        "task4a_manifest": StudySource.from_path(
            "task4a_manifest", input_run / "artifacts/run_manifest.json", capture=True
        ),
    }
    if (
        records["task4a_mc"].sha256 != config.input_table_sha256
        or records["task4a_manifest"].sha256 != config.input_manifest_sha256
    ):
        raise ValueError("R3-ARM64 Angular5 input does not match the frozen reweighting config")
    try:
        summary = json.loads(records["task4a_summary"].snapshot or b"")
        expected_rows = summary["row_count"]
    except (TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("R3-ARM64 Angular5 summary is invalid") from error
    if isinstance(expected_rows, bool) or not isinstance(expected_rows, int) or expected_rows <= 0:
        raise ValueError("R3-ARM64 Angular5 summary row count is invalid")
    hashes = MappingProxyType({
        "config": records["task4a_config"].sha256,
        "mc": records["task4a_mc"].sha256,
        "summary": records["task4a_summary"].sha256,
        "manifest": records["task4a_manifest"].sha256,
    })
    return TrainingInput(
        input_run=input_run,
        config_path=records["task4a_config"].path,
        mc_path=records["task4a_mc"].path,
        summary_path=records["task4a_summary"].path,
        manifest_path=records["task4a_manifest"].path,
        hashes=hashes,
        expected_rows=expected_rows,
    ), records


def _resolve_angular5_r3_arm64_reference(
    reference_run: Path, config: MassBinReweightingConfig,
) -> dict[str, StudySource]:
    records = {
        "reference_config": StudySource.from_path("reference_config", reference_run / "config.yaml"),
        "reference_manifest": StudySource.from_path(
            "reference_manifest", reference_run / "artifacts/training_manifest.json"
        ),
        "reference_model": StudySource.from_path(
            "reference_model", reference_run / "model/xgboost_model.json"
        ),
        "reference_metrics": StudySource.from_path(
            "reference_metrics", reference_run / "artifacts/metrics.json"
        ),
    }
    if records["reference_manifest"].sha256 != config.reference_manifest_sha256:
        raise ValueError("reference manifest does not match the frozen reweighting config")
    return records


def assert_reweighting_sources_unchanged(sources: ReweightingSources) -> None:
    if not isinstance(sources, ReweightingSources):
        raise TypeError("sources must be ReweightingSources")
    for name, source in sources.records.items():
        current = StudySource.from_path(name, source.path)
        if current.size_bytes != source.size_bytes or current.sha256 != source.sha256:
            raise RuntimeError(f"reweighting source changed during study: {name}")


def write_reweighting_artifacts(
    layout: TrainingOutputLayout,
    *,
    config_source: Path,
    config_bytes: bytes,
    iteration_results: pd.DataFrame,
    bin_efficiencies: pd.DataFrame,
    weight_multipliers: pd.DataFrame,
    selection: Mapping[str, Any],
    plot_artifacts: Mapping[str, bytes],
    model: Any | None = None,
    test_metrics: Mapping[str, Any] | None = None,
    selected_oof_scores: pd.DataFrame | None = None,
    test_scores: pd.DataFrame | None = None,
    fixed_bin_statistics: pd.DataFrame | None = None,
    features: tuple[str, ...] = _FULL14_FEATURES,
) -> ReweightingArtifactReceipt:
    selected = model is not None
    captured_features = approved_reweighting_features(features)
    descriptors = None
    try:
        descriptors = _open_claimed_directories(layout)
        root = descriptors["."]
        if _entry_exists(root, ".terminal.failed") or _entry_exists(root, "failure.json"):
            raise RuntimeError("cannot write a failed reweighting run")
        _assert_empty_claimed_layout(descriptors)
        _validate_write_contract(
            selected, iteration_results, bin_efficiencies, weight_multipliers,
            selection, plot_artifacts, test_metrics, selected_oof_scores, test_scores,
        )
        audit = _manifest_audit_evidence(
            bin_efficiencies, weight_multipliers, selection,
            fixed_bin_statistics=fixed_bin_statistics,
        )
        config_current = StudySource.from_path("study_config", config_source)
        if not isinstance(config_bytes, bytes) or config_current.sha256 != hashlib.sha256(config_bytes).hexdigest():
            raise RuntimeError("reweighting config changed before snapshot write")
        config = _load_config_bytes(config_bytes)
        if captured_features != config.features:
            raise ValueError("artifact features differ from the frozen reweighting config")
        _atomic_publish_bytes(root, layout.run_dir, "config.yaml", config_bytes)
        tables = {
            "iteration_results.csv": iteration_results,
            "bin_efficiencies.csv": bin_efficiencies,
            "weight_multipliers.csv": weight_multipliers,
        }
        for name, frame in tables.items():
            _atomic_publish_bytes(descriptors["artifacts"], layout.artifacts_dir, name, _plain_csv_bytes(frame))
        _atomic_publish_bytes(descriptors["artifacts"], layout.artifacts_dir, "selection.json", _json_bytes(selection))
        for name in ("iteration_tradeoff.png", "zz_efficiency_by_mass.png"):
            _atomic_publish_bytes(descriptors["plots"], layout.plots_dir, name, plot_artifacts[name])
        if selected:
            _atomic_publish_bytes(descriptors["artifacts"], layout.artifacts_dir, "test_metrics.json", _json_bytes(test_metrics))
            _atomic_publish_bytes(descriptors["model"], layout.model_dir, "xgboost_model.json", _model_bytes(model))
            _atomic_publish_bytes(descriptors["predictions"], layout.predictions_dir, "selected_oof_scores.csv.gz", _csv_bytes(selected_oof_scores))
            _atomic_publish_bytes(descriptors["predictions"], layout.predictions_dir, "test_scores.csv.gz", _csv_bytes(test_scores))
            _atomic_publish_bytes(descriptors["plots"], layout.plots_dir, "selected_mass_sculpting.png", plot_artifacts["selected_mass_sculpting.png"])
        _assert_contract(descriptors, selected=selected, manifest=False, locked=False)
        return ReweightingArtifactReceipt(
            _RECEIPT_TOKEN,
            layout.directory_identities["."],
            selected,
            _json_bytes(selection),
            _json_bytes(audit),
            captured_features,
        )
    except Exception as error:
        record_reweighting_failure(layout, error)
        raise
    finally:
        _close_descriptors(descriptors)


def _validate_write_contract(selected, iterations, bins, multipliers, selection, plots, test_metrics, oof, test):
    for frame, name in ((iterations, "iteration_results"), (bins, "bin_efficiencies"), (multipliers, "weight_multipliers")):
        _validate_finite_frame(frame, name)
    if not isinstance(selection, Mapping):
        raise TypeError("selection must be a mapping")
    status = selection.get("status")
    selected_iteration = selection.get("selected_iteration")
    test_opened = selection.get("test_opened")
    no_status = {"no_eligible_iteration", "insufficient_bin_statistics"}
    selected_status = {"eligible_iteration_test_reproduced", "test_nonreproduction"}
    if selected:
        if status not in selected_status or isinstance(selected_iteration, bool) or not isinstance(selected_iteration, int) or test_opened is not True:
            raise ValueError("selection contradicts selected artifacts")
    elif status not in no_status or selected_iteration is not None or test_opened is not False:
        raise ValueError("selection contradicts no-selection artifacts")
    expected_plots = {"iteration_tradeoff.png", "zz_efficiency_by_mass.png"} | ({"selected_mass_sculpting.png"} if selected else set())
    if set(plots) != expected_plots:
        raise ValueError("plot outputs do not match the conditional allowlist")
    if any(not isinstance(payload, bytes) or not payload.startswith(b"\x89PNG\r\n\x1a\n") for payload in plots.values()):
        raise ValueError("plot output is not a PNG")
    optional = (test_metrics, oof, test)
    if selected and any(value is None for value in optional):
        raise FileNotFoundError("selected study is missing test-only artifacts")
    if not selected and any(value is not None for value in optional):
        raise ValueError("no-selection study contains test-only artifacts")
    _json_bytes(selection)
    if selected:
        _json_bytes(test_metrics)
        _validate_finite_frame(oof, "selected_oof_scores")
        _validate_finite_frame(test, "test_scores")


def _validate_finite_frame(frame: pd.DataFrame, name: str) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{name} must be a DataFrame")
    numeric = frame.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError(f"{name} contains non-finite numeric content")


def _manifest_audit_evidence(
    bin_efficiencies: pd.DataFrame,
    weight_multipliers: pd.DataFrame,
    selection: Mapping[str, Any],
    *,
    fixed_bin_statistics: pd.DataFrame | None,
) -> dict[str, Any]:
    expected_bins = [
        f"[{int(lower)},{int(upper)})" if upper < 160 else "[155,160]"
        for lower, upper in zip(_EDGES, _EDGES[1:])
    ]
    source = fixed_bin_statistics if fixed_bin_statistics is not None else bin_efficiencies
    _validate_finite_frame(source, "fixed_bin_statistics")
    if not {"mass_bin", "effective_count"}.issubset(source.columns):
        if source.index.name == "mass_bin" and "effective_count" in source.columns:
            source = source.reset_index()
        else:
            raise ValueError("fixed-bin effective-count evidence is incomplete")
    effective: dict[str, float] = {}
    for mass_bin in expected_bins:
        values = source.loc[source["mass_bin"] == mass_bin, "effective_count"].to_numpy(dtype=float)
        if values.size == 0 or not np.isfinite(values).all() or not np.all(values == values[0]) or values[0] < 0.0:
            raise ValueError("fixed-bin effective-count evidence is incomplete")
        effective[mass_bin] = float(values[0])
    if set(source["mass_bin"].astype(str)) != set(expected_bins):
        raise ValueError("fixed-bin effective-count evidence changes the fixed bins")

    multipliers: dict[str, dict[str, float]] = {}
    if not weight_multipliers.empty:
        if set(weight_multipliers.columns) != {"iteration", "mass_bin", "multiplier"}:
            raise ValueError("cumulative-multiplier evidence is malformed")
        for iteration, rows in weight_multipliers.groupby("iteration", sort=True):
            if isinstance(iteration, bool) or int(iteration) != iteration:
                raise ValueError("cumulative-multiplier iteration is invalid")
            values = dict(zip(rows["mass_bin"].astype(str), rows["multiplier"].astype(float)))
            if len(rows) != len(expected_bins) or set(values) != set(expected_bins):
                raise ValueError("cumulative-multiplier evidence is incomplete")
            if not np.isfinite(list(values.values())).all() or any(value <= 0.0 for value in values.values()):
                raise ValueError("cumulative-multiplier evidence must be finite and positive")
            multipliers[str(int(iteration))] = {name: float(values[name]) for name in expected_bins}
        if list(multipliers) != [str(value) for value in range(len(multipliers))]:
            raise ValueError("cumulative-multiplier iterations must be complete and ordered")
    elif selection.get("status") != "insufficient_bin_statistics":
        raise ValueError("executed iterations require cumulative-multiplier evidence")
    return {
        "fixed_bin_effective_counts": effective,
        "iteration_cumulative_multipliers": multipliers,
    }


def _plain_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")


def publish_reweighting_manifest(
    layout: TrainingOutputLayout,
    *,
    receipt: ReweightingArtifactReceipt,
    sources: Mapping[str, StudySource],
    source_row_counts: Mapping[str, Any],
    decision: Mapping[str, Any],
    policy: Mapping[str, Any],
    software: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(receipt, ReweightingArtifactReceipt):
        raise FileNotFoundError("publisher requires a reweighting artifact receipt")
    if layout.directory_identities is None or receipt._run_identity != layout.directory_identities.get("."):
        raise ValueError("artifact receipt does not belong to this claimed run")
    descriptors = None
    locked = False
    staged = None
    staged_fd = None
    try:
        if set(sources) != _source_keys_for_features(receipt._features) or any(not isinstance(source, StudySource) or source.name != name for name, source in sources.items()):
            raise ValueError("reweighting source inventory does not match the approved contract")
        rows = _validate_rows(source_row_counts)
        _validate_manifest_decision(receipt.selected, decision)
        if _json_bytes(decision) != receipt._decision_bytes:
            raise ValueError("manifest decision differs from the written selection")
        _validate_policy_record(policy, receipt._features)
        descriptors = _open_claimed_directories(layout)
        root = descriptors["."]
        _terminal_lock_acquire(root)
        locked = True
        if _entry_exists(root, ".terminal.failed") or _entry_exists(root, "failure.json"):
            raise RuntimeError("cannot publish a failed reweighting run")
        _assert_contract(descriptors, selected=receipt.selected, manifest=False, locked=True)
        audit = json.loads(receipt._audit_bytes)
        audit_snapshots = _read_audit_csv_snapshots(descriptors["artifacts"])
        _validate_published_audit_csvs(audit_snapshots, audit, decision)
        outputs = _build_output_records(
            layout,
            descriptors,
            selected=receipt.selected,
            audit_snapshots=audit_snapshots,
        )
        manifest = {
            "schema_version": "1.0",
            "status": "complete",
            "decision": dict(decision),
            "policy": dict(policy),
            "software": dict(software),
            "sources": {
                name: {
                    "path": str(source.path),
                    "size_bytes": source.size_bytes,
                    "sha256": source.sha256,
                    **(rows if name == "task4a_mc" else {}),
                }
                for name, source in sources.items()
            },
            "outputs": outputs,
            **audit,
        }
        serialized = _json_bytes(manifest)
        staged = _stage_bytes(descriptors["artifacts"], "study_manifest.json", serialized)
        staged_fd, identity = _open_verified_staged_manifest(descriptors["artifacts"], staged, serialized)

        def immediate_check():
            for name, source in sources.items():
                current = StudySource.from_path(name, source.path)
                if current.size_bytes != source.size_bytes or current.sha256 != source.sha256:
                    raise RuntimeError(f"reweighting source changed during study: {name}")
            _assert_staged_manifest_unchanged(descriptors["artifacts"], staged, staged_fd, identity, serialized)
            _assert_audit_csv_snapshots_unchanged(
                descriptors["artifacts"], audit_snapshots
            )
            if _build_output_records(layout, descriptors, selected=receipt.selected) != outputs:
                raise RuntimeError("reweighting output changed before manifest publication")
            _revalidate_named_layout(layout)

        _promote_bound_manifest_no_clobber(
            descriptors["artifacts"], layout.artifacts_dir, staged, staged_fd,
            identity, serialized, "study_manifest.json", immediate_check=immediate_check,
        )
        staged = None
        os.close(staged_fd)
        staged_fd = None
        _assert_contract(descriptors, selected=receipt.selected, manifest=True, locked=True)
        return manifest
    except Exception as error:
        if descriptors is not None:
            _cleanup_staged(descriptors.get("artifacts", descriptors["."]), staged)
            if locked:
                _install_failure_locked(descriptors["."], layout.run_dir, error)
            else:
                record_reweighting_failure(layout, error)
        else:
            record_reweighting_failure(layout, error)
        raise
    finally:
        if descriptors is not None and locked:
            _terminal_lock_release(descriptors["."])
        if staged_fd is not None:
            os.close(staged_fd)
        _close_descriptors(descriptors)


def _validate_published_audit_csvs(
    snapshots: Mapping[str, tuple[bytes, tuple[int, int]]],
    audit: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> None:
    expected_bins = [
        f"[{int(lower)},{int(upper)})" if upper < 160 else "[155,160]"
        for lower, upper in zip(_EDGES, _EDGES[1:])
    ]
    effective = audit.get("fixed_bin_effective_counts")
    multipliers = audit.get("iteration_cumulative_multipliers")
    if not isinstance(effective, Mapping) or list(effective) != expected_bins:
        raise ValueError("effective-count audit changes fixed-bin keys or order")
    if not isinstance(multipliers, Mapping):
        raise ValueError("cumulative-multiplier audit is malformed")

    status = decision.get("status")
    if status == "insufficient_bin_statistics":
        iteration_rows = _csv_rows_from_payload(
            snapshots["iteration_results.csv"][0],
            "iteration_results.csv",
            ("iteration", "weighted_oof_auc"),
        )
        bin_rows = _csv_rows_from_payload(
            snapshots["bin_efficiencies.csv"][0],
            "bin_efficiencies.csv",
            ("iteration", "mass_bin", "working_point", "efficiency"),
        )
        multiplier_rows = _csv_rows_from_payload(
            snapshots["weight_multipliers.csv"][0],
            "weight_multipliers.csv",
            ("iteration", "mass_bin", "multiplier"),
        )
        if iteration_rows or bin_rows or multiplier_rows or multipliers:
            raise ValueError("insufficient-statistics terminal contains executed iterations")
        return

    iteration_columns = (
        "iteration", "candidate", "final_tree_count", "weighted_oof_auc",
        "maximum_oof_zz_ks", "eligible", "eligibility_reasons",
        "loose_threshold", "loose_signal_efficiency",
        "loose_achieved_zz_efficiency", "loose_oof_zz_ks",
        "medium_threshold", "medium_signal_efficiency",
        "medium_achieved_zz_efficiency", "medium_oof_zz_ks",
        "tight_threshold", "tight_signal_efficiency",
        "tight_achieved_zz_efficiency", "tight_oof_zz_ks",
    )
    iteration_rows = _csv_rows_from_payload(
        snapshots["iteration_results.csv"][0],
        "iteration_results.csv",
        iteration_columns,
    )

    bin_rows = _csv_rows_from_payload(
        snapshots["bin_efficiencies.csv"][0],
        "bin_efficiencies.csv",
        (
            "iteration", "mass_bin", "working_point", "numerator",
            "denominator", "efficiency", "effective_count", "standard_error",
        ),
    )
    multiplier_rows = _csv_rows_from_payload(
        snapshots["weight_multipliers.csv"][0],
        "weight_multipliers.csv",
        ("iteration", "mass_bin", "multiplier"),
    )

    bin_iterations: list[int] = []
    canonical_keys = [
        (mass_bin, working_point)
        for mass_bin in expected_bins
        for working_point in ("loose", "medium", "tight")
    ]
    seen_keys: set[tuple[int, str, str]] = set()
    keys_by_iteration: dict[int, list[tuple[str, str]]] = {}
    for row in bin_rows:
        iteration = _csv_nonnegative_integer(row["iteration"], "bin iteration")
        mass_bin = row["mass_bin"]
        working_point = row["working_point"]
        if mass_bin not in effective or working_point not in {"loose", "medium", "tight"}:
            raise ValueError("published bin-efficiency keys are invalid")
        key = (iteration, mass_bin, working_point)
        if key in seen_keys:
            raise ValueError("published bin-efficiency keys are duplicated")
        seen_keys.add(key)
        value = _csv_finite_float(row["effective_count"], "effective count")
        if value < 0.0 or value != float(effective[mass_bin]):
            raise ValueError("effective-count audit differs from published bin efficiencies")
        numerator = _csv_finite_float(row["numerator"], "bin numerator")
        denominator = _csv_finite_float(row["denominator"], "bin denominator")
        efficiency = _csv_finite_float(row["efficiency"], "bin efficiency")
        standard_error = _csv_finite_float(row["standard_error"], "bin standard error")
        if denominator <= 0.0 or numerator < 0.0 or numerator > denominator:
            raise ValueError("bin-efficiency numerator or denominator is invalid")
        if not np.isclose(efficiency, numerator / denominator, rtol=1e-12, atol=1e-15):
            raise ValueError("bin-efficiency identity is inconsistent")
        expected_error = float(np.sqrt(efficiency * (1.0 - efficiency) / value))
        if value <= 0.0 or not np.isclose(standard_error, expected_error, rtol=1e-12, atol=1e-15):
            raise ValueError("bin-efficiency standard error is inconsistent")
        if iteration not in keys_by_iteration:
            bin_iterations.append(iteration)
            keys_by_iteration[iteration] = []
        keys_by_iteration[iteration].append((mass_bin, working_point))
    if bin_iterations:
        if bin_iterations != list(range(len(bin_iterations))):
            raise ValueError("published bin-efficiency iterations are incomplete or reordered")
        if any(keys_by_iteration[item] != canonical_keys for item in bin_iterations):
            raise ValueError("published bin-efficiency keys differ across iterations")

    expected_iterations = [int(name) for name in multipliers]
    if list(multipliers) != [str(value) for value in range(len(multipliers))]:
        raise ValueError("cumulative-multiplier audit iterations are incomplete or reordered")
    multiplier_iterations: list[int] = []
    values_by_iteration: dict[int, dict[str, float]] = {}
    bin_order_by_iteration: dict[int, list[str]] = {}
    for row in multiplier_rows:
        iteration = _csv_nonnegative_integer(row["iteration"], "multiplier iteration")
        mass_bin = row["mass_bin"]
        if iteration not in values_by_iteration:
            multiplier_iterations.append(iteration)
            values_by_iteration[iteration] = {}
            bin_order_by_iteration[iteration] = []
        if mass_bin in values_by_iteration[iteration]:
            raise ValueError("published cumulative-multiplier keys are duplicated")
        value = _csv_finite_float(row["multiplier"], "cumulative multiplier")
        if value <= 0.0:
            raise ValueError("published cumulative multiplier must be positive")
        values_by_iteration[iteration][mass_bin] = value
        bin_order_by_iteration[iteration].append(mass_bin)
    if multiplier_iterations != expected_iterations:
        raise ValueError("multiplier audit differs from published iteration keys or order")
    for iteration in expected_iterations:
        if bin_order_by_iteration[iteration] != expected_bins:
            raise ValueError("published multiplier bins are incomplete or reordered")
        expected = multipliers[str(iteration)]
        if not isinstance(expected, Mapping) or list(expected) != expected_bins:
            raise ValueError("cumulative-multiplier audit changes fixed-bin keys or order")
        if values_by_iteration[iteration] != {
            name: float(expected[name]) for name in expected_bins
        }:
            raise ValueError("multiplier audit differs from published weight multipliers")
    if bin_iterations != expected_iterations:
        raise ValueError("published bin and multiplier iteration keys differ")
    _validate_iteration_results(iteration_rows, expected_iterations, decision)


def _validate_iteration_results(
    rows: list[dict[str, str]],
    expected_iterations: list[int],
    decision: Mapping[str, Any],
    maximum_corrections: int = _MAXIMUM_CORRECTIONS,
) -> None:
    if len(rows) != len(expected_iterations):
        raise ValueError("iteration results row count differs from executed iterations")
    observed_iterations: list[int] = []
    observed_eligible: list[bool] = []
    for row in rows:
        iteration = _csv_nonnegative_integer(row["iteration"], "iteration result")
        observed_iterations.append(iteration)
        if not row["candidate"]:
            raise ValueError("iteration candidate is empty")
        tree_count = _csv_nonnegative_integer(row["final_tree_count"], "tree count")
        if tree_count <= 0:
            raise ValueError("iteration tree count must be positive")
        auc = _csv_finite_float(row["weighted_oof_auc"], "weighted OOF AUC")
        if not 0.0 <= auc <= 1.0:
            raise ValueError("iteration weighted OOF AUC is outside [0,1]")
        ks_values: dict[str, float] = {}
        signal: dict[str, float] = {}
        achieved: dict[str, float] = {}
        for name in ("loose", "medium", "tight"):
            threshold = _csv_finite_float(row[f"{name}_threshold"], f"{name} threshold")
            signal[name] = _csv_finite_float(
                row[f"{name}_signal_efficiency"], f"{name} signal efficiency"
            )
            achieved[name] = _csv_finite_float(
                row[f"{name}_achieved_zz_efficiency"], f"{name} ZZ efficiency"
            )
            ks_values[name] = _csv_finite_float(
                row[f"{name}_oof_zz_ks"], f"{name} OOF ZZ KS"
            )
            if not np.isfinite(threshold):
                raise ValueError("iteration threshold must be finite")
            if not 0.0 <= signal[name] <= 1.0 or not 0.0 <= achieved[name] <= 1.0:
                raise ValueError("iteration efficiency is outside [0,1]")
            if not 0.0 <= ks_values[name] <= 1.0:
                raise ValueError("iteration KS is outside [0,1]")
        maximum = _csv_finite_float(row["maximum_oof_zz_ks"], "maximum OOF ZZ KS")
        if maximum != max(ks_values.values()):
            raise ValueError("iteration maximum OOF ZZ KS disagrees with three gates")
        reasons: list[str] = []
        if auc < 0.80:
            reasons.append("weighted_auc_below_floor")
        for name in ("loose", "medium", "tight"):
            if ks_values[name] > 0.10:
                reasons.append(f"{name}_zz_ks_above_limit")
        for name in ("loose", "medium", "tight"):
            if not signal[name] > achieved[name]:
                reasons.append(f"{name}_signal_efficiency_not_strictly_greater")
        eligible = _csv_boolean(row["eligible"], "iteration eligibility")
        if eligible != (not reasons):
            raise ValueError("iteration eligibility contradicts frozen gates")
        if row["eligibility_reasons"] != ",".join(reasons):
            raise ValueError("iteration eligibility reasons contradict frozen gates")
        observed_eligible.append(eligible)
    if observed_iterations != expected_iterations:
        raise ValueError("iteration results keys or order differ from audit artifacts")

    status = decision.get("status")
    selected_iteration = decision.get("selected_iteration")
    if status == "no_eligible_iteration":
        if expected_iterations != list(range(6)) or any(observed_eligible):
            raise ValueError("no-eligible terminal contradicts iteration evidence")
        if selected_iteration is not None or decision.get("test_opened") is not False:
            raise ValueError("no-eligible terminal contradicts selection evidence")
    elif status in {"eligible_iteration_test_reproduced", "test_nonreproduction"}:
        if (
            isinstance(selected_iteration, bool)
            or not isinstance(selected_iteration, int)
            or not 0 <= selected_iteration <= maximum_corrections
            or expected_iterations != list(range(selected_iteration + 1))
        ):
            raise ValueError("selected iteration must be within frozen range 0..5")
        eligible_indices = [
            iteration
            for iteration, eligible in zip(expected_iterations, observed_eligible)
            if eligible
        ]
        if (
            len(eligible_indices) != 1
            or eligible_indices[0] != expected_iterations[-1]
            or selected_iteration != eligible_indices[0]
            or decision.get("test_opened") is not True
        ):
            raise ValueError("selected terminal contradicts first-eligible iteration")
    else:
        raise ValueError("selection terminal is invalid for executed iterations")


def _read_audit_csv_snapshots(
    artifacts_descriptor: int,
) -> dict[str, tuple[bytes, tuple[int, int]]]:
    return {
        name: _read_entry_bytes(artifacts_descriptor, name)
        for name in (
            "iteration_results.csv", "bin_efficiencies.csv",
            "weight_multipliers.csv",
        )
    }


def _assert_audit_csv_snapshots_unchanged(
    artifacts_descriptor: int,
    snapshots: Mapping[str, tuple[bytes, tuple[int, int]]],
) -> None:
    for name, expected in snapshots.items():
        if _read_entry_bytes(artifacts_descriptor, name) != expected:
            raise RuntimeError(f"audit CSV changed before manifest publication: {name}")


def _csv_rows_from_payload(
    payload: bytes, name: str, expected_columns: tuple[str, ...]
) -> list[dict[str, str]]:
    try:
        text = payload.decode("utf-8", errors="strict")
        reader = csv.DictReader(io.StringIO(text))
        fieldnames = reader.fieldnames
        if fieldnames != list(expected_columns):
            raise ValueError
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError
        return rows
    except (UnicodeDecodeError, csv.Error, ValueError) as error:
        raise ValueError(f"published audit CSV is invalid: {name}") from error


def _csv_nonnegative_integer(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"published {name} is invalid") from error
    if str(parsed) != value or parsed < 0:
        raise ValueError(f"published {name} is invalid")
    return parsed


def _csv_boolean(value: str, name: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"published {name} is invalid")


def _csv_finite_float(value: str, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"published {name} is invalid") from error
    if not np.isfinite(parsed):
        raise ValueError(f"published {name} must be finite")
    return parsed


def _validate_manifest_decision(selected: bool, decision: Mapping[str, Any]) -> None:
    if not isinstance(decision, Mapping):
        raise TypeError("decision must be a mapping")
    fake_selection = {"status": decision.get("status"), "selected_iteration": decision.get("selected_iteration"), "test_opened": decision.get("test_opened")}
    _validate_write_contract(selected, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), fake_selection, {"iteration_tradeoff.png": b"\x89PNG\r\n\x1a\n", "zz_efficiency_by_mass.png": b"\x89PNG\r\n\x1a\n", **({"selected_mass_sculpting.png": b"\x89PNG\r\n\x1a\n"} if selected else {})}, {} if selected else None, pd.DataFrame() if selected else None, pd.DataFrame() if selected else None)


def _validate_policy_record(
    value: Mapping[str, Any], expected_features: tuple[str, ...]
) -> None:
    captured_features = approved_reweighting_features(expected_features)
    expected = {
        "features": list(captured_features),
        "mass_bin_edges": list(_EDGES),
        "minimum_effective_count": 100.0,
        "epsilon_floor": 1e-6,
        "damping": 0.5,
        "round_factor_bounds": [0.5, 2.0],
        "cumulative_bounds": [0.2, 5.0],
        "maximum_corrections": 5,
        "auc_floor": 0.8,
        "ks_limit": 0.1,
        "require_signal_efficiency_above_zz": True,
    }
    if not isinstance(value, Mapping) or dict(value) != expected:
        raise ValueError("manifest policy differs from the frozen reweighting config")


def _validate_rows(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"row_count", "rows_by_split"}:
        raise ValueError("source row counts do not match the approved contract")
    split = value["rows_by_split"]
    if not isinstance(split, Mapping) or set(split) != {"train", "validation", "test"}:
        raise ValueError("source row counts do not match the approved contract")
    normalized = {}
    for name in ("train", "validation", "test"):
        item = split[name]
        if isinstance(item, bool) or not isinstance(item, (int, np.integer)) or int(item) <= 0:
            raise ValueError("source row counts must be positive integers")
        normalized[name] = int(item)
    total = value["row_count"]
    if isinstance(total, bool) or not isinstance(total, (int, np.integer)) or int(total) != sum(normalized.values()):
        raise ValueError("source row count must equal split rows")
    return {"row_count": int(total), "rows_by_split": normalized}


def _assert_contract(descriptors, *, selected: bool, manifest: bool, locked: bool):
    root_expected = {"config.yaml", "model", "artifacts", "predictions", "plots"}
    if locked:
        root_expected.add(".terminal.lock")
    if _entries(descriptors["."]) != root_expected:
        raise ValueError("reweighting run root does not match the approved contract")
    files = approved_reweighting_artifacts(selected=selected) - {"config.yaml", _MANIFEST}
    expected = {
        name: {Path(item).name for item in files if item.startswith(name + "/")}
        for name in ("model", "artifacts", "predictions", "plots")
    }
    if manifest:
        expected["artifacts"].add("study_manifest.json")
    for name, wanted in expected.items():
        actual = _entries(descriptors[name])
        if actual != wanted:
            if wanted - actual:
                raise FileNotFoundError(f"required reweighting output is missing in {name}")
            raise ValueError(f"unexpected reweighting output entry in {name}")


def _build_output_records(
    layout,
    descriptors,
    *,
    selected: bool,
    audit_snapshots: Mapping[str, tuple[bytes, tuple[int, int]]] | None = None,
):
    result = {}
    record = _output_record_without_pandas(descriptors["."], layout.config_snapshot, csv_rows=False)
    result["config.yaml"] = record
    for relative in sorted(approved_reweighting_artifacts(selected=selected) - {"config.yaml", _MANIFEST}):
        directory, _ = relative.split("/", 1)
        path = layout.run_dir / relative
        csv = relative.endswith(".csv") or relative.endswith(".csv.gz")
        snapshot = (
            None
            if audit_snapshots is None or directory != "artifacts"
            else audit_snapshots.get(path.name)
        )
        if snapshot is None:
            record = _output_record_without_pandas(
                descriptors[directory],
                path,
                csv_rows=csv,
                compression="gzip" if relative.endswith(".gz") else None,
            )
        else:
            record = _output_record_from_payload(
                path,
                snapshot[0],
                csv_rows=csv,
                compression="gzip" if relative.endswith(".gz") else None,
            )
        result[relative] = record
    return result


def _output_record_without_pandas(descriptor: int, path: Path, *, csv_rows: bool, compression: str | None = None):
    payload, _ = _read_entry_bytes(descriptor, path.name)
    return _output_record_from_payload(
        path, payload, csv_rows=csv_rows, compression=compression
    )


def _output_record_from_payload(
    path: Path,
    payload: bytes,
    *,
    csv_rows: bool,
    compression: str | None = None,
):
    record = {
        "path": str(path),
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    if csv_rows:
        try:
            decoded = gzip.decompress(payload) if compression == "gzip" else payload
            rows = list(csv.reader(io.StringIO(decoded.decode("utf-8", errors="strict"))))
        except (OSError, UnicodeDecodeError, csv.Error) as error:
            raise ValueError(f"reweighting CSV is invalid: {path.name}") from error
        if not rows or not rows[0] or len(set(rows[0])) != len(rows[0]):
            raise ValueError(f"reweighting CSV is invalid: {path.name}")
        width = len(rows[0])
        if any(len(row) != width for row in rows[1:]):
            raise ValueError(f"reweighting CSV is invalid: {path.name}")
        nonfinite = {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}
        if any(cell.strip().lower() in nonfinite for row in rows[1:] for cell in row):
            raise ValueError(f"reweighting CSV contains non-finite content: {path.name}")
        record["row_count"] = len(rows) - 1
    return record


def record_reweighting_failure(layout: TrainingOutputLayout, error: BaseException) -> None:
    try:
        root = _open_verified_root(layout)
    except Exception:
        return
    locked = False
    try:
        _terminal_lock_acquire(root)
        locked = True
        artifacts = None
        try:
            artifacts = os.open("artifacts", os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0), dir_fd=root)
            if _entry_exists(artifacts, "study_manifest.json"):
                return
        except OSError:
            pass
        finally:
            if artifacts is not None:
                os.close(artifacts)
        _install_failure_locked(root, layout.run_dir, error)
    except Exception:
        pass
    finally:
        if locked:
            _terminal_lock_release(root)
        os.close(root)


def policy_manifest_record(config: MassBinReweightingConfig) -> dict[str, Any]:
    return {
        "features": list(config.features),
        "mass_bin_edges": list(config.mass_bin_edges),
        "minimum_effective_count": config.minimum_effective_count,
        "epsilon_floor": config.epsilon_floor,
        "damping": config.damping,
        "round_factor_bounds": list(config.round_factor_bounds),
        "cumulative_bounds": list(config.cumulative_bounds),
        "maximum_corrections": config.maximum_corrections,
        "auc_floor": config.auc_floor,
        "ks_limit": config.ks_limit,
        "require_signal_efficiency_above_zz": config.require_signal_efficiency_above_zz,
    }
