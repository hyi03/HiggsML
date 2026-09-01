"""Frozen configuration contract for the MC-only flatness study."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import pickle
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

from .full_training_policy import validate_mc_frame
from .full_training_run import (
    TrainingInput,
    TrainingOutputLayout,
    _assert_empty_claimed_layout,
    _atomic_publish_bytes,
    _close_descriptors,
    _csv_bytes,
    _entries,
    _entry_exists,
    _json_bytes,
    _install_failure_locked,
    _open_claimed_directories,
    _output_record_from_descriptor,
    _terminal_lock_acquire,
    _terminal_lock_release,
    claim_training_output,
    record_training_failure,
    resolve_training_output,
)
from .mass_sculpting_ablation_run import (
    StudySource,
    _resolve_task4a_sources_without_table_load,
)


_FEATURES = (
    "lep1_pt",
    "lep2_pt",
    "lep1_eta",
    "lep2_eta",
    "lep3_eta",
    "lep4_eta",
    "pt4l",
    "deltaR_Z1",
    "deltaR_Z2",
    "deltaPhi_ZZ",
)
_COEFFICIENTS = (0.0, 0.5, 1.0, 2.0, 3.0)
_WORKING_POINTS = {"loose": 0.50, "medium": 0.20, "tight": 0.10}
_MODEL = {
    "type": "hep_ml.UGradientBoostingClassifier",
    "n_estimators": 300,
    "learning_rate": 0.05,
    "max_depth": 3,
    "min_samples_leaf": 50,
    "subsample": 0.8,
    "random_seed": 42,
}
_FLATNESS = {
    "type": "hep_ml.losses.KnnFlatnessLossFunction",
    "uniform_feature": "m4l",
    "uniform_label": 0,
    "n_neighbours": 100,
    "max_groups": 5000,
    "power": 2.0,
    "allow_wrong_signs": True,
}
_COMMON_ARTIFACTS = frozenset(
    {
        "artifacts/candidate_results.csv",
        "artifacts/working_point_metrics.csv",
        "artifacts/selection.json",
        "predictions/oof_scores.csv.gz",
        "plots/candidate_tradeoff.png",
        "plots/working_point_ks.png",
    }
)
_SELECTED_ARTIFACTS = frozenset(
    {
        "artifacts/test_metrics.json",
        "model/flatness_model.pkl",
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
    }
)


@dataclass(frozen=True)
class DecorrelationConfig:
    schema_version: str
    input_run: str
    input_manifest_sha256: str
    input_mc_sha256: str
    features: tuple[str, ...]
    folds: int
    model: Mapping[str, Any]
    flatness: Mapping[str, Any]
    coefficients: tuple[float, ...]
    working_points: Mapping[str, float]
    auc_floor: float
    ks_limit: float
    require_signal_efficiency_above_background: bool
    artifacts_no_selection: tuple[str, ...]
    artifacts_selected: tuple[str, ...]

    @property
    def mass_bins_gev(self) -> tuple[float, ...]:
        return tuple(float(value) for value in range(105, 165, 5))

    @property
    def ks_distance_limit(self) -> float:
        return self.ks_limit


@dataclass(frozen=True)
class DecorrelationSources:
    config: DecorrelationConfig
    config_bytes: bytes
    training_input: TrainingInput
    records: Mapping[str, StudySource]


class MCStudyPartitions:
    def __init__(self, development: pd.DataFrame, test: pd.DataFrame):
        self._development = development.copy(deep=True)
        self._test = test.copy(deep=True)
        self._test_opened = False

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> "MCStudyPartitions":
        validate_mc_frame(frame)
        development = frame.loc[frame["split"] != "test"].copy(deep=True)
        test = frame.loc[frame["split"] == "test"].copy(deep=True)
        return cls(development, test)

    @property
    def development(self) -> pd.DataFrame:
        return self._development.copy(deep=True)

    def open_test(self) -> pd.DataFrame:
        if self._test_opened:
            raise RuntimeError("held-out test was already opened")
        self._test_opened = True
        return self._test.copy(deep=True)


_RECEIPT_TOKEN = object()


@dataclass(frozen=True, init=False)
class DecorrelationArtifactReceipt:
    _run_identity: tuple[int, int]
    selected: bool

    def __new__(
        cls,
        token: object = None,
        run_identity: tuple[int, int] | None = None,
        selected: bool = False,
    ):
        if token is not _RECEIPT_TOKEN or run_identity is None:
            raise TypeError(
                "DecorrelationArtifactReceipt is returned by the artifact writer"
            )
        return super().__new__(cls)

    def __init__(
        self, token: object, run_identity: tuple[int, int], selected: bool
    ) -> None:
        object.__setattr__(self, "_run_identity", run_identity)
        object.__setattr__(self, "selected", bool(selected))


def approved_decorrelation_artifacts(*, selected: bool) -> set[str]:
    return set(
        _COMMON_ARTIFACTS
        | (_SELECTED_ARTIFACTS if selected else frozenset())
    )


def _expected_config() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "input_run": "runs/full-baseline-363490-2026-08-11-r2",
        "input_manifest_sha256": (
            "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8"
        ),
        "input_mc_sha256": (
            "1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e"
        ),
        "features": list(_FEATURES),
        "folds": 5,
        "model": dict(_MODEL),
        "flatness": dict(_FLATNESS),
        "coefficients": list(_COEFFICIENTS),
        "working_points": dict(_WORKING_POINTS),
        "auc_floor": 0.80,
        "ks_limit": 0.10,
        "require_signal_efficiency_above_background": True,
        "artifacts_no_selection": sorted(_COMMON_ARTIFACTS),
        "artifacts_selected": sorted(_COMMON_ARTIFACTS | _SELECTED_ARTIFACTS),
    }


def load_decorrelation_config(path: str | Path) -> DecorrelationConfig:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ValueError("decorrelation config is not valid YAML") from error
    if not isinstance(raw, dict):
        raise ValueError("decorrelation config must be a mapping")

    expected = _expected_config()
    comparable = dict(raw)
    for key in ("artifacts_no_selection", "artifacts_selected"):
        value = comparable.get(key)
        if isinstance(value, list):
            comparable[key] = sorted(value)
    if comparable != expected:
        raise ValueError("decorrelation config changed a frozen decision")

    return DecorrelationConfig(
        schema_version="1.0",
        input_run=expected["input_run"],
        input_manifest_sha256=expected["input_manifest_sha256"],
        input_mc_sha256=expected["input_mc_sha256"],
        features=_FEATURES,
        folds=5,
        model=MappingProxyType(dict(_MODEL)),
        flatness=MappingProxyType(dict(_FLATNESS)),
        coefficients=_COEFFICIENTS,
        working_points=MappingProxyType(dict(_WORKING_POINTS)),
        auc_floor=0.80,
        ks_limit=0.10,
        require_signal_efficiency_above_background=True,
        artifacts_no_selection=tuple(raw["artifacts_no_selection"]),
        artifacts_selected=tuple(raw["artifacts_selected"]),
    )


def resolve_decorrelation_sources(
    *, input_run: str | Path, config_path: str | Path
) -> DecorrelationSources:
    config_source = StudySource.from_path(
        "study_config", config_path, capture=True
    )
    if config_source.snapshot is None:
        raise RuntimeError("decorrelation config snapshot is unavailable")
    config = load_decorrelation_config(config_source.path)
    if Path(input_run).resolve() != Path(config.input_run).resolve():
        raise ValueError("--input-run does not match the frozen decorrelation config")
    training_input, task4a_records = _resolve_task4a_sources_without_table_load(
        input_run
    )
    if training_input.hashes["manifest"] != config.input_manifest_sha256:
        raise ValueError("Task 4A manifest does not match the frozen config")
    if training_input.hashes["mc"] != config.input_mc_sha256:
        raise ValueError("Task 4A MC table does not match the frozen config")
    records = {"study_config": config_source, **task4a_records}
    if set(records) != _SOURCE_KEYS:
        raise RuntimeError("decorrelation source inventory is incomplete")
    return DecorrelationSources(
        config=config,
        config_bytes=config_source.snapshot,
        training_input=training_input,
        records=MappingProxyType(records),
    )


def assert_decorrelation_sources_unchanged(
    sources: DecorrelationSources,
) -> None:
    if not isinstance(sources, DecorrelationSources):
        raise TypeError("sources must be DecorrelationSources")
    for name, source in sources.records.items():
        current = StudySource.from_path(name, source.path)
        if (
            current.sha256 != source.sha256
            or current.size_bytes != source.size_bytes
        ):
            raise RuntimeError(
                f"decorrelation source changed during study: {name}"
            )


def resolve_decorrelation_output(
    *,
    project_root: Path,
    working_directory: Path,
    input_run: str | Path,
    run_dir: str | Path,
) -> TrainingOutputLayout:
    return resolve_training_output(
        project_root=project_root,
        working_directory=working_directory,
        input_run=input_run,
        run_dir=run_dir,
    )


def claim_decorrelation_output(
    layout: TrainingOutputLayout,
) -> TrainingOutputLayout:
    return claim_training_output(layout)


def write_decorrelation_artifacts(
    *,
    layout: TrainingOutputLayout,
    config_bytes: bytes,
    artifacts: Mapping[str, Any],
) -> DecorrelationArtifactReceipt:
    selected = artifacts.get("model") is not None
    descriptors: dict[str, int] | None = None
    try:
        descriptors = _open_claimed_directories(layout)
        if _entry_exists(descriptors["."], ".terminal.failed"):
            raise RuntimeError("cannot write a failed decorrelation run")
        _assert_empty_claimed_layout(descriptors)
        _validate_artifacts(artifacts, selected=selected)
        serialized = {
            "config.yaml": bytes(config_bytes),
            "artifacts/candidate_results.csv": _plain_csv_bytes(
                artifacts["candidate_results"]
            ),
            "artifacts/working_point_metrics.csv": _plain_csv_bytes(
                artifacts["working_point_metrics"]
            ),
            "artifacts/selection.json": _json_bytes(artifacts["selection"]),
            "predictions/oof_scores.csv.gz": _csv_bytes(
                artifacts["oof_scores"]
            ),
            "plots/candidate_tradeoff.png": artifacts["plot_artifacts"][
                "candidate_tradeoff.png"
            ],
            "plots/working_point_ks.png": artifacts["plot_artifacts"][(
                "working_point_ks.png"
            )],
        }
        if selected:
            model_payload = pickle.dumps(artifacts["model"], protocol=5)
            pickle.loads(model_payload)
            serialized.update(
                {
                    "model/flatness_model.pkl": model_payload,
                    "artifacts/test_metrics.json": _json_bytes(
                        artifacts["test_metrics"]
                    ),
                    "predictions/selected_oof_scores.csv.gz": _csv_bytes(
                        artifacts["selected_oof_scores"]
                    ),
                    "predictions/test_scores.csv.gz": _csv_bytes(
                        artifacts["test_scores"]
                    ),
                    "plots/selected_mass_sculpting.png": artifacts[
                        "plot_artifacts"
                    ]["selected_mass_sculpting.png"],
                }
            )
        expected = {"config.yaml", *approved_decorrelation_artifacts(selected=selected)}
        if set(serialized) != expected:
            raise ValueError("serialized outputs do not match the approved allowlist")
        for relative, payload in serialized.items():
            if relative == "config.yaml":
                descriptor = descriptors["."]
                parent = layout.run_dir
                filename = relative
            else:
                directory, filename = relative.split("/", 1)
                descriptor = descriptors[directory]
                parent = layout.run_dir / directory
            _atomic_publish_bytes(descriptor, parent, filename, payload)
        _assert_output_contract(descriptors, selected=selected, manifest=False)
        return DecorrelationArtifactReceipt(
            _RECEIPT_TOKEN, layout.directory_identities["."], selected
        )
    except Exception as error:
        record_decorrelation_failure(layout, error)
        raise
    finally:
        _close_descriptors(descriptors)


def publish_decorrelation_manifest(
    *,
    layout: TrainingOutputLayout,
    sources: DecorrelationSources,
    outcome,
    receipt: DecorrelationArtifactReceipt,
    software: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(receipt, DecorrelationArtifactReceipt):
        raise TypeError("publisher requires a decorrelation artifact receipt")
    if (
        layout.directory_identities is None
        or receipt._run_identity != layout.directory_identities.get(".")
    ):
        raise ValueError("artifact receipt does not belong to this run")
    if software.get("hep_ml") != "0.8.0":
        raise ValueError("manifest requires hep_ml 0.8.0")
    outcome_selected = getattr(outcome.selection, "selected", None) is not None
    outcome_test_opened = getattr(outcome, "evidence", None) is not None
    if (
        receipt.selected != outcome_selected
        or outcome_selected != outcome_test_opened
    ):
        raise ValueError("decorrelation decision contradicts published artifacts")
    descriptors: dict[str, int] | None = None
    locked = False
    try:
        descriptors = _open_claimed_directories(layout)
        _terminal_lock_acquire(descriptors["."])
        locked = True
        _assert_output_contract(
            descriptors, selected=receipt.selected, manifest=False, terminal_lock=True
        )
        assert_decorrelation_sources_unchanged(sources)
        outputs = _output_records(
            layout, descriptors, selected=receipt.selected
        )
        selected = getattr(outcome.selection, "selected", None)
        manifest = {
            "schema_version": "1.0",
            "status": "complete",
            "decision": {
                "selected_candidate": (
                    None
                    if selected is None
                    else _candidate_name(selected.coefficient)
                ),
                "test_opened": outcome.evidence is not None,
            },
            "software": dict(software),
            "sources": {
                name: {
                    "path": str(source.path),
                    "size_bytes": source.size_bytes,
                    "sha256": source.sha256,
                }
                for name, source in sources.records.items()
            },
            "outputs": outputs,
        }
        assert_decorrelation_sources_unchanged(sources)
        if _output_records(
            layout, descriptors, selected=receipt.selected
        ) != outputs:
            raise RuntimeError("decorrelation output changed before manifest")
        _atomic_publish_bytes(
            descriptors["artifacts"],
            layout.artifacts_dir,
            "study_manifest.json",
            _json_bytes(manifest),
        )
        _assert_output_contract(
            descriptors, selected=receipt.selected, manifest=True, terminal_lock=True
        )
        return manifest
    except Exception as error:
        if descriptors is not None and locked:
            _install_failure_locked(descriptors["."], layout.run_dir, error)
        else:
            record_decorrelation_failure(layout, error)
        raise
    finally:
        if descriptors is not None and locked:
            _terminal_lock_release(descriptors["."])
        _close_descriptors(descriptors)


def record_decorrelation_failure(
    layout: TrainingOutputLayout, error: BaseException
) -> None:
    record_training_failure(layout, error)


def _validate_artifacts(artifacts: Mapping[str, Any], *, selected: bool) -> None:
    required = {
        "candidate_results",
        "working_point_metrics",
        "selection",
        "oof_scores",
        "plot_artifacts",
        "model",
        "selected_oof_scores",
        "test_scores",
        "test_metrics",
    }
    if not isinstance(artifacts, Mapping) or set(artifacts) != required:
        raise ValueError("artifact payload does not match the approved contract")
    for name in ("candidate_results", "working_point_metrics", "oof_scores"):
        _validate_finite_frame(artifacts[name], name)
    expected_plots = {"candidate_tradeoff.png", "working_point_ks.png"}
    if selected:
        expected_plots.add("selected_mass_sculpting.png")
    if set(artifacts["plot_artifacts"]) != expected_plots:
        raise ValueError("plot outputs do not match the conditional allowlist")
    for name, payload in artifacts["plot_artifacts"].items():
        if not isinstance(payload, bytes) or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"plot output is not a PNG: {name}")
    optional = (
        artifacts["selected_oof_scores"],
        artifacts["test_scores"],
        artifacts["test_metrics"],
    )
    if selected and any(value is None for value in optional):
        raise ValueError("selected study is missing test-only artifacts")
    if not selected and any(value is not None for value in optional):
        raise ValueError("no-selection study contains test-only artifacts")
    if selected:
        _validate_finite_frame(artifacts["selected_oof_scores"], "selected OOF")
        _validate_finite_frame(artifacts["test_scores"], "test scores")
        _json_bytes(artifacts["test_metrics"])
    _json_bytes(artifacts["selection"])


def _validate_finite_frame(frame: pd.DataFrame, name: str) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{name} must be a DataFrame")
    numeric = frame.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError(f"{name} contains non-finite values")


def _plain_csv_bytes(frame: pd.DataFrame) -> bytes:
    _validate_finite_frame(frame, "CSV table")
    return frame.to_csv(index=False).encode("utf-8")


def _assert_output_contract(
    descriptors: Mapping[str, int],
    *,
    selected: bool,
    manifest: bool,
    terminal_lock: bool = False,
) -> None:
    root = {"config.yaml", "model", "artifacts", "predictions", "plots"}
    if terminal_lock:
        root.add(".terminal.lock")
    if _entries(descriptors["."]) != root:
        raise ValueError("decorrelation run root does not match the contract")
    relative = approved_decorrelation_artifacts(selected=selected)
    expected = {
        name: {
            Path(item).name
            for item in relative
            if item.startswith(f"{name}/")
        }
        for name in ("model", "artifacts", "predictions", "plots")
    }
    if manifest:
        expected["artifacts"].add("study_manifest.json")
    for name, values in expected.items():
        if _entries(descriptors[name]) != values:
            raise ValueError(f"decorrelation {name} outputs do not match contract")


def _output_records(
    layout: TrainingOutputLayout,
    descriptors: Mapping[str, int],
    *,
    selected: bool,
) -> dict[str, dict[str, Any]]:
    records = {}
    config_record, _ = _output_record_from_descriptor(
        descriptors["."], layout.config_snapshot, csv_rows=False
    )
    records["config.yaml"] = config_record
    for relative in sorted(approved_decorrelation_artifacts(selected=selected)):
        directory, _ = relative.split("/", 1)
        record, _ = _output_record_from_descriptor(
            descriptors[directory],
            layout.run_dir / relative,
            csv_rows=relative.endswith(".csv") or relative.endswith(".csv.gz"),
            compression="gzip" if relative.endswith(".csv.gz") else None,
        )
        records[relative] = record
    return records


def _candidate_name(coefficient: float) -> str:
    return f"lambda_{float(coefficient):.1f}".replace(".", "p")
