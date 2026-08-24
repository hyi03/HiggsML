from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import pickle
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

from .external_zz_run import (
    _assert_staged_manifest_unchanged,
    _open_verified_staged_manifest,
    _publish_descriptor_no_clobber,
)
from .full_training_policy import validate_mc_frame
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
    _json_bytes,
    _open_claimed_directories,
    _open_verified_root,
    _output_record_from_descriptor,
    _read_entry_bytes,
    _revalidate_named_layout,
    _stage_bytes,
    _terminal_lock_acquire,
    _terminal_lock_release,
    assert_input_hashes_unchanged,
    claim_training_output,
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
_WORKING_POINTS = {
    "loose": 0.50,
    "medium": 0.20,
    "tight": 0.10,
}
_COEFFICIENTS = (0.0, 0.5, 1.0, 2.0, 3.0)
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
_SOFTWARE_KEYS = frozenset(
    {
        "python",
        "numpy",
        "pandas",
        "pyyaml",
        "uproot",
        "xgboost",
        "scikit-learn",
        "hep_ml",
    }
)
_TOP_LEVEL_KEYS = {
    "schema_version",
    "input_run",
    "input_manifest_sha256",
    "input_mc_sha256",
    "features",
    "folds",
    "model",
    "flatness",
    "coefficients",
    "working_points",
    "auc_floor",
    "ks_limit",
    "require_signal_efficiency_above_background",
    "artifacts_no_selection",
    "artifacts_selected",
}


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


_SOURCE_CAPABILITY_TOKEN = object()


@dataclass(frozen=True, init=False)
class DecorrelationSources:
    config: DecorrelationConfig
    config_bytes: bytes
    training_input: TrainingInput
    records: Mapping[str, StudySource]

    def __new__(
        cls,
        token: object = None,
        *,
        config: DecorrelationConfig | None = None,
        config_bytes: bytes | None = None,
        training_input: TrainingInput | None = None,
        records: Mapping[str, StudySource] | None = None,
    ):
        if token is not _SOURCE_CAPABILITY_TOKEN:
            raise TypeError(
                "DecorrelationSources is returned by "
                "resolve_decorrelation_sources"
            )
        return super().__new__(cls)

    def __init__(
        self,
        token: object,
        *,
        config: DecorrelationConfig,
        config_bytes: bytes,
        training_input: TrainingInput,
        records: Mapping[str, StudySource],
    ) -> None:
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "config_bytes", config_bytes)
        object.__setattr__(self, "training_input", training_input)
        object.__setattr__(self, "records", MappingProxyType(dict(records)))
        _validate_source_inventory(self)


class MCStudyPartitions:
    """Own deep MC partitions and permit one semantic held-out test opening."""

    __slots__ = ("_development", "_test", "_test_opened")

    def __init__(self, development: pd.DataFrame, test: pd.DataFrame) -> None:
        self._development = development.copy(deep=True)
        self._test = test.copy(deep=True)
        self._test_opened = False

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> "MCStudyPartitions":
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("MC study input must be a DataFrame")
        validate_mc_frame(frame)
        development = frame.loc[frame["split"].isin(("train", "validation"))]
        test = frame.loc[frame["split"] == "test"]
        return cls(development.copy(deep=True), test.copy(deep=True))

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
    _outputs: Mapping[str, Mapping[str, Any]]

    def __new__(
        cls,
        token: object = None,
        run_identity: tuple[int, int] | None = None,
        selected: bool = False,
        outputs: Mapping[str, Mapping[str, Any]] | None = None,
    ):
        if (
            token is not _RECEIPT_TOKEN
            or run_identity is None
            or outputs is None
        ):
            raise TypeError(
                "DecorrelationArtifactReceipt is returned by "
                "write_decorrelation_artifacts"
            )
        return super().__new__(cls)

    def __init__(
        self,
        token: object,
        run_identity: tuple[int, int],
        selected: bool,
        outputs: Mapping[str, Mapping[str, Any]],
    ) -> None:
        object.__setattr__(self, "_run_identity", run_identity)
        object.__setattr__(self, "selected", bool(selected))
        object.__setattr__(self, "_outputs", _freeze_output_records(outputs))


def approved_decorrelation_artifacts(*, selected: bool) -> set[str]:
    return set(_COMMON_ARTIFACTS | (_SELECTED_ARTIFACTS if selected else frozenset()))


def load_decorrelation_config(path: str | Path) -> DecorrelationConfig:
    try:
        payload = Path(path).read_bytes()
    except OSError as error:
        raise ValueError("decorrelation config is not valid YAML") from error
    return _load_config_bytes(payload)


def _load_config_bytes(payload: bytes) -> DecorrelationConfig:
    try:
        raw = yaml.safe_load(payload)
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ValueError("decorrelation config is not valid YAML") from error
    if not isinstance(raw, dict) or set(raw) != _TOP_LEVEL_KEYS:
        raise ValueError("decorrelation config does not match an approved schema")
    if not _matches_frozen_decisions(raw):
        raise ValueError("decorrelation config changes a frozen decision")

    no_selection = raw.get("artifacts_no_selection")
    selected = raw.get("artifacts_selected")
    if (
        not isinstance(no_selection, list)
        or len(no_selection) != len(set(no_selection))
        or set(no_selection) != approved_decorrelation_artifacts(selected=False)
        or not isinstance(selected, list)
        or len(selected) != len(set(selected))
        or set(selected) != approved_decorrelation_artifacts(selected=True)
    ):
        raise ValueError(
            "conditional artifact allowlists do not match the approved contract"
        )

    return DecorrelationConfig(
        schema_version="1.0",
        input_run=raw["input_run"],
        input_manifest_sha256=raw["input_manifest_sha256"],
        input_mc_sha256=raw["input_mc_sha256"],
        features=_FEATURES,
        folds=5,
        model=MappingProxyType(dict(_MODEL)),
        flatness=MappingProxyType(dict(_FLATNESS)),
        coefficients=_COEFFICIENTS,
        working_points=MappingProxyType(dict(_WORKING_POINTS)),
        auc_floor=0.80,
        ks_limit=0.10,
        require_signal_efficiency_above_background=True,
        artifacts_no_selection=tuple(no_selection),
        artifacts_selected=tuple(selected),
    )


def _matches_frozen_decisions(raw: Mapping[str, Any]) -> bool:
    return (
        raw.get("schema_version") == "1.0"
        and raw.get("input_run") == "runs/full-baseline-363490-2026-08-11-r2"
        and raw.get("input_manifest_sha256")
        == "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8"
        and raw.get("input_mc_sha256")
        == "1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e"
        and raw.get("features") == list(_FEATURES)
        and type(raw.get("folds")) is int
        and raw["folds"] == 5
        and raw.get("model") == _MODEL
        and raw.get("flatness") == _FLATNESS
        and raw.get("coefficients") == list(_COEFFICIENTS)
        and raw.get("working_points") == _WORKING_POINTS
        and type(raw.get("auc_floor")) is float
        and raw["auc_floor"] == 0.80
        and type(raw.get("ks_limit")) is float
        and raw["ks_limit"] == 0.10
        and raw.get("require_signal_efficiency_above_background") is True
    )


def resolve_decorrelation_sources(
    *, input_run: str | Path, config_path: str | Path
) -> DecorrelationSources:
    """Resolve only the exact frozen production config and MC-only receipts."""
    config_source = StudySource.from_path(
        "study_config", config_path, capture=True
    )
    config_bytes = config_source.snapshot
    if config_bytes is None:
        raise RuntimeError("decorrelation config snapshot is unavailable")
    config = _load_config_bytes(config_bytes)

    requested_input = Path(os.path.abspath(input_run)).resolve()
    configured_input = Path(config.input_run).resolve()
    if requested_input != configured_input:
        raise ValueError("--input-run does not match the frozen decorrelation config")

    training_input, task4a_records = _resolve_task4a_sources_without_table_load(
        requested_input
    )
    if training_input.hashes["manifest"] != config.input_manifest_sha256:
        raise ValueError(
            "Task 4A manifest does not match the frozen decorrelation config"
        )
    if training_input.hashes["mc"] != config.input_mc_sha256:
        raise ValueError("Task 4A MC does not match the frozen decorrelation config")

    records = {"study_config": config_source, **task4a_records}
    if set(records) != _SOURCE_KEYS:
        raise RuntimeError("decorrelation source inventory is incomplete")
    sources = DecorrelationSources(
        _SOURCE_CAPABILITY_TOKEN,
        config=config,
        config_bytes=config_bytes,
        training_input=training_input,
        records=MappingProxyType(records),
    )
    assert_decorrelation_sources_unchanged(sources)
    return sources


def assert_decorrelation_sources_unchanged(
    sources: DecorrelationSources,
) -> None:
    _validate_source_inventory(sources)
    for source in sources.records.values():
        try:
            current = StudySource.from_path(source.name, source.path)
        except Exception as error:
            raise RuntimeError(
                f"decorrelation source changed during study: {source.name}"
            ) from error
        if (
            current.size_bytes != source.size_bytes
            or current.sha256 != source.sha256
        ):
            raise RuntimeError(
                f"decorrelation source changed during study: {source.name}"
            )
    assert_input_hashes_unchanged(sources.training_input)


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
    layout: TrainingOutputLayout,
    *,
    config_bytes: bytes,
    artifacts: Mapping[str, Any],
) -> DecorrelationArtifactReceipt:
    """Write exactly one conditional non-manifest contract without clobbering."""
    descriptors: dict[str, int] | None = None
    try:
        descriptors = _open_claimed_directories(layout)
        root = descriptors["."]
        if _entry_exists(root, ".terminal.failed") or _entry_exists(
            root, "failure.json"
        ):
            raise RuntimeError("cannot write a failed decorrelation run")
        _assert_empty_claimed_layout(descriptors)
        if not isinstance(config_bytes, bytes):
            raise TypeError("config_bytes must contain bytes")
        config = _load_config_bytes(config_bytes)
        selected = _validate_artifact_values(artifacts, config=config)
        serialized = _serialize_artifacts(artifacts, selected=selected)
        expected_outputs = _serialized_output_records(
            layout,
            config_bytes=config_bytes,
            artifacts=artifacts,
            serialized=serialized,
            selected=selected,
        )

        _atomic_publish_bytes(root, layout.run_dir, "config.yaml", config_bytes)
        _atomic_publish_bytes(
            descriptors["artifacts"],
            layout.artifacts_dir,
            "candidate_results.csv",
            serialized["candidate_results"],
        )
        _atomic_publish_bytes(
            descriptors["artifacts"],
            layout.artifacts_dir,
            "working_point_metrics.csv",
            serialized["working_point_metrics"],
        )
        _atomic_publish_bytes(
            descriptors["artifacts"],
            layout.artifacts_dir,
            "selection.json",
            serialized["selection"],
        )
        _atomic_publish_bytes(
            descriptors["predictions"],
            layout.predictions_dir,
            "oof_scores.csv.gz",
            serialized["oof_scores"],
        )
        for name in ("candidate_tradeoff.png", "working_point_ks.png"):
            _atomic_publish_bytes(
                descriptors["plots"],
                layout.plots_dir,
                name,
                serialized[name],
            )
        if selected:
            _atomic_publish_bytes(
                descriptors["artifacts"],
                layout.artifacts_dir,
                "test_metrics.json",
                serialized["test_metrics"],
            )
            _atomic_publish_bytes(
                descriptors["model"],
                layout.model_dir,
                "flatness_model.pkl",
                serialized["flatness_model"],
            )
            _atomic_publish_bytes(
                descriptors["predictions"],
                layout.predictions_dir,
                "selected_oof_scores.csv.gz",
                serialized["selected_oof_scores"],
            )
            _atomic_publish_bytes(
                descriptors["predictions"],
                layout.predictions_dir,
                "test_scores.csv.gz",
                serialized["test_scores"],
            )
            _atomic_publish_bytes(
                descriptors["plots"],
                layout.plots_dir,
                "selected_mass_sculpting.png",
                serialized["selected_mass_sculpting.png"],
            )
        _assert_decorrelation_contract(
            descriptors,
            selected=selected,
            manifest_present=False,
            terminal_lock_present=False,
        )
        outputs = _build_output_records(
            layout, descriptors, selected=selected
        )
        if outputs != expected_outputs:
            raise RuntimeError(
                "decorrelation output changed during artifact publication"
            )
        return DecorrelationArtifactReceipt(
            _RECEIPT_TOKEN,
            layout.directory_identities["."],
            selected,
            expected_outputs,
        )
    except Exception as error:
        record_decorrelation_failure(layout, error)
        raise
    finally:
        _close_descriptors(descriptors)


def _validate_artifact_values(
    artifacts: Mapping[str, Any], *, config: DecorrelationConfig
) -> bool:
    expected_keys = {
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
    if not isinstance(artifacts, Mapping) or set(artifacts) != expected_keys:
        raise ValueError("artifact payload does not match the approved contract")
    for name in ("candidate_results", "working_point_metrics", "oof_scores"):
        _validate_finite_frame(artifacts[name], name)
    if not isinstance(artifacts["selection"], Mapping):
        raise TypeError("selection must be a mapping")
    _json_bytes(artifacts["selection"])

    selected = artifacts["model"] is not None
    optional = (
        artifacts["selected_oof_scores"],
        artifacts["test_scores"],
        artifacts["test_metrics"],
    )
    if selected and any(value is None for value in optional):
        raise FileNotFoundError("selected study is missing test-only artifacts")
    if not selected and any(value is not None for value in optional):
        raise ValueError("no-selection study contains test-only artifacts")

    selection = artifacts["selection"]
    _validate_selection_contract(selection, config)
    status = selection.get("status")
    candidate = selection.get("selected_candidate")
    test_opened = selection.get("test_opened")
    if not selected and (
        status != "no_eligible_candidate"
        or candidate is not None
        or test_opened is not False
    ):
        raise ValueError("decision artifact contradicts no-selection artifacts")
    if selected and (
        status != "eligible_candidate_test_reported"
        or not isinstance(candidate, str)
        or not candidate
        or test_opened is not True
    ):
        raise ValueError("decision artifact contradicts selected artifacts")

    plots = artifacts["plot_artifacts"]
    expected_plots = {"candidate_tradeoff.png", "working_point_ks.png"}
    if selected:
        expected_plots.add("selected_mass_sculpting.png")
    if not isinstance(plots, Mapping) or set(plots) != expected_plots:
        raise ValueError("plot outputs do not match the conditional allowlist")
    for name, payload in plots.items():
        if not isinstance(payload, bytes) or not payload.startswith(
            b"\x89PNG\r\n\x1a\n"
        ):
            raise ValueError(f"plot output is not a PNG: {name}")

    if selected:
        _validate_finite_frame(
            artifacts["selected_oof_scores"], "selected_oof_scores"
        )
        _validate_finite_frame(artifacts["test_scores"], "test_scores")
        if not isinstance(artifacts["test_metrics"], Mapping):
            raise TypeError("test_metrics must be a mapping")
        _json_bytes(artifacts["test_metrics"])
    return selected


def _validate_selection_contract(
    selection: Mapping[str, Any], config: DecorrelationConfig
) -> None:
    expected_keys = {
        "schema_version",
        "status",
        "selected_candidate",
        "test_opened",
        "auc_floor",
        "ks_limit",
    }
    if (
        set(selection) != expected_keys
        or selection.get("schema_version") != "1.0"
        or type(selection.get("auc_floor")) is not float
        or selection.get("auc_floor") != config.auc_floor
        or type(selection.get("ks_limit")) is not float
        or selection.get("ks_limit") != config.ks_limit
    ):
        raise ValueError("selection contract changes the frozen schema or gates")


def _serialize_artifacts(
    artifacts: Mapping[str, Any], *, selected: bool
) -> dict[str, bytes]:
    plots = artifacts["plot_artifacts"]
    serialized = {
        "candidate_results": _plain_csv_bytes(artifacts["candidate_results"]),
        "working_point_metrics": _plain_csv_bytes(
            artifacts["working_point_metrics"]
        ),
        "selection": _json_bytes(artifacts["selection"]),
        "oof_scores": _csv_bytes(artifacts["oof_scores"]),
        "candidate_tradeoff.png": plots["candidate_tradeoff.png"],
        "working_point_ks.png": plots["working_point_ks.png"],
    }
    if selected:
        serialized.update(
            test_metrics=_json_bytes(artifacts["test_metrics"]),
            flatness_model=_trusted_model_bytes(artifacts["model"]),
            selected_oof_scores=_csv_bytes(artifacts["selected_oof_scores"]),
            test_scores=_csv_bytes(artifacts["test_scores"]),
            **{
                "selected_mass_sculpting.png": plots[
                    "selected_mass_sculpting.png"
                ]
            },
        )
    return serialized


def _trusted_model_bytes(model: Any) -> bytes:
    from hep_ml.gradientboosting import UGradientBoostingClassifier

    if type(model) is not UGradientBoostingClassifier:
        raise TypeError("selected model must be a local hep_ml flatness model")
    if tuple(getattr(model, "train_features", ())) != _FEATURES:
        raise ValueError("selected model does not use the exact DropTop4 features")
    verification = _model_verification_frame()
    try:
        expected = np.asarray(model.predict_proba(verification), dtype=float)
    except Exception as error:
        raise ValueError("selected hep_ml model is not fitted") from error
    if not np.isfinite(expected).all():
        raise ValueError("selected model verification predictions must be finite")
    payload = pickle.dumps(model, protocol=5)
    restored = pickle.loads(payload)
    observed = np.asarray(restored.predict_proba(verification), dtype=float)
    try:
        np.testing.assert_allclose(observed, expected, rtol=0.0, atol=0.0)
    except AssertionError as error:
        raise ValueError(
            "selected model pickle round-trip changed verification predictions"
        ) from error
    return payload


def _model_verification_frame() -> pd.DataFrame:
    rows = (
        (35.0, 28.0, 0.1, -0.2, 0.3, -0.4, 42.0, 1.1, 1.4, 2.2),
        (52.0, 31.0, -0.5, 0.6, -0.7, 0.8, 63.0, 2.1, 2.4, -2.2),
    )
    return pd.DataFrame(rows, columns=_FEATURES)


def _validate_finite_frame(frame: Any, name: str) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{name} must be a DataFrame")
    try:
        numeric = frame.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} numeric content must be finite") from error
    if not np.isfinite(numeric).all():
        raise ValueError(f"{name} contains non-finite numeric content")


def _plain_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")


def publish_decorrelation_manifest(
    layout: TrainingOutputLayout,
    *,
    sources: DecorrelationSources,
    outcome: Any,
    receipt: DecorrelationArtifactReceipt,
    software: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish a complete manifest last after immediate source/output rechecks."""
    try:
        if not isinstance(receipt, DecorrelationArtifactReceipt):
            raise FileNotFoundError(
                "publisher requires a DecorrelationArtifactReceipt"
            )
        if (
            layout.directory_identities is None
            or receipt._run_identity != layout.directory_identities.get(".")
        ):
            raise ValueError(
                "artifact receipt does not belong to this claimed run"
            )
        _validate_source_inventory(sources)
        _validate_software(software)
        decision = _decision_from_outcome(outcome, sources.config)
        if receipt.selected != decision["test_opened"]:
            raise ValueError("decision contradicts conditional artifact receipt")
    except Exception as error:
        record_decorrelation_failure(layout, error)
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
        if _entry_exists(root, ".terminal.failed") or _entry_exists(
            root, "failure.json"
        ):
            raise RuntimeError("cannot publish a failed decorrelation run")
        if _entry_exists(descriptors["artifacts"], "study_manifest.json"):
            raise FileExistsError(
                f"output entry already exists: "
                f"{layout.artifacts_dir / 'study_manifest.json'}"
            )
        _assert_decorrelation_contract(
            descriptors,
            selected=receipt.selected,
            manifest_present=False,
            terminal_lock_present=True,
        )
        _assert_selection_matches_decision(
            descriptors["artifacts"], decision, sources.config
        )
        outputs = _assert_output_receipt(layout, descriptors, receipt)
        manifest = {
            "schema_version": "1.0",
            "status": "complete",
            "decision": decision,
            "software": dict(software),
            "sources": _source_manifest_records(sources),
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
            assert_decorrelation_sources_unchanged(sources)
            _assert_staged_manifest_unchanged(
                descriptors["artifacts"],
                staged_manifest,
                staged_descriptor,
                staged_identity,
                serialized,
            )
            if _assert_output_receipt(layout, descriptors, receipt) != outputs:
                raise RuntimeError("decorrelation output receipt changed")
            _revalidate_named_layout(layout)

        _promote_decorrelation_manifest_no_clobber(
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
        _assert_decorrelation_contract(
            descriptors,
            selected=receipt.selected,
            manifest_present=True,
            terminal_lock_present=True,
        )
        return manifest
    except Exception as error:
        if descriptors is not None:
            _cleanup_staged(
                descriptors.get("artifacts", descriptors["."]), staged_manifest
            )
            if locked:
                _install_decorrelation_failure_locked(
                    descriptors["."], layout, error
                )
            else:
                record_decorrelation_failure(layout, error)
        else:
            record_decorrelation_failure(layout, error)
        raise
    finally:
        if descriptors is not None and locked:
            _terminal_lock_release(descriptors["."])
        if staged_descriptor is not None:
            os.close(staged_descriptor)
        _close_descriptors(descriptors)


def _before_decorrelation_manifest_promotion(destination: Path) -> None:
    """Test seam before the final checks at the descriptor promotion boundary."""


def _promote_decorrelation_manifest_no_clobber(
    root: int,
    parent: Path,
    staged: str,
    staged_descriptor: int,
    staged_identity: tuple[int, int],
    expected: bytes,
    final_name: str,
    *,
    immediate_check,
) -> None:
    destination = parent / final_name
    try:
        _before_decorrelation_manifest_promotion(destination)
        immediate_check()
        _publish_descriptor_no_clobber(
            staged_descriptor, root, final_name, destination
        )
    finally:
        _cleanup_staged(root, staged)


def _validate_source_inventory(sources: DecorrelationSources) -> None:
    if type(sources) is not DecorrelationSources:
        raise TypeError(
            "sources must be returned by resolve_decorrelation_sources"
        )
    if not isinstance(sources.config_bytes, bytes):
        raise TypeError("decorrelation source config snapshot must contain bytes")
    strict_config = _load_config_bytes(sources.config_bytes)
    if sources.config != strict_config:
        raise ValueError(
            "decorrelation source capability does not match strict frozen config"
        )
    if not isinstance(sources.training_input, TrainingInput):
        raise TypeError("decorrelation source training input is invalid")
    if set(sources.records) != _SOURCE_KEYS or any(
        not isinstance(source, StudySource) or source.name != name
        for name, source in sources.records.items()
    ):
        raise ValueError(
            "decorrelation source inventory does not match the approved contract"
        )
    if sources.records["study_config"].snapshot != sources.config_bytes:
        raise ValueError("decorrelation config receipt does not match its snapshot")
    training_input = sources.training_input
    hashes = training_input.hashes
    if set(hashes) != {"config", "mc", "summary", "manifest"}:
        raise ValueError("decorrelation training input hashes are incomplete")
    configured_input = Path(strict_config.input_run).resolve()
    if Path(training_input.input_run).resolve() != configured_input:
        raise ValueError("decorrelation training input changes the frozen run")
    expected_paths = {
        "task4a_config": training_input.config_path,
        "task4a_mc": training_input.mc_path,
        "task4a_summary": training_input.summary_path,
        "task4a_manifest": training_input.manifest_path,
    }
    expected_hashes = {
        "task4a_config": hashes["config"],
        "task4a_mc": hashes["mc"],
        "task4a_summary": hashes["summary"],
        "task4a_manifest": hashes["manifest"],
    }
    if any(
        source.path != Path(os.path.abspath(expected_paths[name]))
        or source.sha256 != expected_hashes[name]
        for name, source in sources.records.items()
        if name != "study_config"
    ):
        raise ValueError("decorrelation source records change the training input")
    for name in ("study_config", "task4a_config", "task4a_summary", "task4a_manifest"):
        source = sources.records[name]
        snapshot = source.snapshot
        if (
            not isinstance(snapshot, bytes)
            or len(snapshot) != source.size_bytes
            or hashlib.sha256(snapshot).hexdigest() != source.sha256
        ):
            raise ValueError("decorrelation captured source receipt is inconsistent")
    if sources.records["task4a_mc"].snapshot is not None:
        raise ValueError("decorrelation MC source must not capture table bytes")
    if (
        hashes["manifest"] != strict_config.input_manifest_sha256
        or hashes["mc"] != strict_config.input_mc_sha256
    ):
        raise ValueError("decorrelation source receipts do not match frozen config")
    if (
        type(training_input.expected_rows) is not int
        or training_input.expected_rows < 0
    ):
        raise ValueError("decorrelation training row receipt is invalid")


def _validate_software(software: Mapping[str, Any]) -> None:
    if (
        not isinstance(software, Mapping)
        or set(software) != _SOFTWARE_KEYS
        or any(not isinstance(value, str) for value in software.values())
    ):
        raise ValueError("manifest software does not match the approved contract")
    if software.get("hep_ml") != "0.8.0":
        raise ValueError("manifest software must record hep_ml 0.8.0")
    _json_bytes(software)


def _source_manifest_records(
    sources: DecorrelationSources,
) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "path": str(source.path),
            "size_bytes": source.size_bytes,
            "sha256": source.sha256,
            **(
                {"expected_rows": sources.training_input.expected_rows}
                if name == "task4a_mc"
                else {}
            ),
        }
        for name, source in sources.records.items()
    }


def _decision_from_outcome(
    outcome: Any, config: DecorrelationConfig
) -> dict[str, Any]:
    selection = getattr(outcome, "selection", None)
    selected = getattr(selection, "selected", None)
    evidence = getattr(outcome, "evidence", None)
    if selected is None:
        if evidence is not None:
            raise ValueError("outcome decision contradicts no-selection evidence")
        return {
            "status": "no_eligible_candidate",
            "selected_candidate": None,
            "selected_coefficient": None,
            "test_opened": False,
        }
    if evidence is None:
        raise ValueError("outcome decision contradicts selected evidence")
    try:
        coefficient = float(selected.coefficient)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("selected outcome coefficient must be numeric") from error
    if not np.isfinite(coefficient) or coefficient not in config.coefficients:
        raise ValueError("selected outcome coefficient is not approved")
    return {
        "status": "eligible_candidate_test_reported",
        "selected_candidate": _candidate_name(coefficient),
        "selected_coefficient": coefficient,
        "test_opened": True,
    }


def _candidate_name(coefficient: float) -> str:
    return f"lambda_{str(float(coefficient)).replace('.', 'p')}"


def _assert_selection_matches_decision(
    artifacts_descriptor: int,
    decision: Mapping[str, Any],
    config: DecorrelationConfig,
) -> None:
    payload, _ = _read_entry_bytes(artifacts_descriptor, "selection.json")
    try:
        selection = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("selection artifact is not valid JSON") from error
    if not isinstance(selection, Mapping):
        raise ValueError("selection artifact must contain an object")
    _validate_selection_contract(selection, config)
    if any(
        selection.get(key) != decision[key]
        for key in ("status", "selected_candidate", "test_opened")
    ):
        raise ValueError("decision contradicts the published selection artifact")


def _assert_decorrelation_contract(
    descriptors: Mapping[str, int],
    *,
    selected: bool,
    manifest_present: bool,
    terminal_lock_present: bool,
) -> None:
    root_expected = {"config.yaml", "model", "artifacts", "predictions", "plots"}
    if terminal_lock_present:
        root_expected.add(".terminal.lock")
    if _entries(descriptors["."]) != root_expected:
        raise ValueError("decorrelation run root does not match the approved contract")
    relative = approved_decorrelation_artifacts(selected=selected)
    expected = {
        "model": {
            Path(name).name for name in relative if name.startswith("model/")
        },
        "artifacts": {
            Path(name).name
            for name in relative
            if name.startswith("artifacts/")
        },
        "predictions": {
            Path(name).name
            for name in relative
            if name.startswith("predictions/")
        },
        "plots": {
            Path(name).name for name in relative if name.startswith("plots/")
        },
    }
    if manifest_present:
        expected["artifacts"].add("study_manifest.json")
    for directory, names in expected.items():
        actual = _entries(descriptors[directory])
        if actual != names:
            if names - actual:
                raise FileNotFoundError(
                    f"required decorrelation output is missing in {directory}"
                )
            raise ValueError(
                f"unexpected decorrelation output entry in {directory}"
            )


def _build_output_records(
    layout: TrainingOutputLayout,
    descriptors: Mapping[str, int],
    *,
    selected: bool,
) -> dict[str, dict[str, Any]]:
    outputs: dict[str, dict[str, Any]] = {}
    config_record, _ = _output_record_from_descriptor(
        descriptors["."], layout.config_snapshot, csv_rows=False
    )
    outputs["config.yaml"] = config_record
    for relative in sorted(approved_decorrelation_artifacts(selected=selected)):
        directory, _ = relative.split("/", 1)
        path = layout.run_dir / relative
        csv_rows = relative.endswith(".csv") or relative.endswith(".csv.gz")
        compression = "gzip" if relative.endswith(".csv.gz") else None
        record, _ = _output_record_from_descriptor(
            descriptors[directory],
            path,
            csv_rows=csv_rows,
            compression=compression,
        )
        outputs[relative] = record
    return outputs


def _serialized_output_records(
    layout: TrainingOutputLayout,
    *,
    config_bytes: bytes,
    artifacts: Mapping[str, Any],
    serialized: Mapping[str, bytes],
    selected: bool,
) -> dict[str, dict[str, Any]]:
    payloads: dict[str, bytes] = {
        "config.yaml": config_bytes,
        "artifacts/candidate_results.csv": serialized["candidate_results"],
        "artifacts/working_point_metrics.csv": serialized[
            "working_point_metrics"
        ],
        "artifacts/selection.json": serialized["selection"],
        "predictions/oof_scores.csv.gz": serialized["oof_scores"],
        "plots/candidate_tradeoff.png": serialized["candidate_tradeoff.png"],
        "plots/working_point_ks.png": serialized["working_point_ks.png"],
    }
    row_counts = {
        "artifacts/candidate_results.csv": len(artifacts["candidate_results"]),
        "artifacts/working_point_metrics.csv": len(
            artifacts["working_point_metrics"]
        ),
        "predictions/oof_scores.csv.gz": len(artifacts["oof_scores"]),
    }
    if selected:
        payloads.update(
            {
                "artifacts/test_metrics.json": serialized["test_metrics"],
                "model/flatness_model.pkl": serialized["flatness_model"],
                "predictions/selected_oof_scores.csv.gz": serialized[
                    "selected_oof_scores"
                ],
                "predictions/test_scores.csv.gz": serialized["test_scores"],
                "plots/selected_mass_sculpting.png": serialized[
                    "selected_mass_sculpting.png"
                ],
            }
        )
        row_counts.update(
            {
                "predictions/selected_oof_scores.csv.gz": len(
                    artifacts["selected_oof_scores"]
                ),
                "predictions/test_scores.csv.gz": len(artifacts["test_scores"]),
            }
        )
    expected_paths = {
        "config.yaml",
        *approved_decorrelation_artifacts(selected=selected),
    }
    if set(payloads) != expected_paths:
        raise RuntimeError("serialized outputs do not match the approved contract")
    records: dict[str, dict[str, Any]] = {}
    for relative, payload in payloads.items():
        record: dict[str, Any] = {
            "path": str(layout.run_dir / relative),
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        if relative in row_counts:
            record["row_count"] = row_counts[relative]
        records[relative] = record
    return records


def _freeze_output_records(
    records: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Mapping[str, Any]]:
    return MappingProxyType(
        {
            relative: MappingProxyType(dict(record))
            for relative, record in records.items()
        }
    )


def _assert_output_receipt(
    layout: TrainingOutputLayout,
    descriptors: Mapping[str, int],
    receipt: DecorrelationArtifactReceipt,
) -> dict[str, dict[str, Any]]:
    current = _build_output_records(
        layout, descriptors, selected=receipt.selected
    )
    expected = {
        relative: dict(record)
        for relative, record in receipt._outputs.items()
    }
    if current != expected:
        raise RuntimeError("decorrelation output receipt changed")
    return current


def _study_manifest_exists(layout: TrainingOutputLayout) -> bool:
    descriptors: dict[str, int] | None = None
    try:
        descriptors = _open_claimed_directories(layout)
        try:
            payload, identity = _read_entry_bytes(
                descriptors["artifacts"], "study_manifest.json"
            )
        except (OSError, ValueError, FileNotFoundError):
            return False
        try:
            manifest = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        if not isinstance(manifest, Mapping) or set(manifest) != {
            "schema_version",
            "status",
            "decision",
            "software",
            "sources",
            "outputs",
        }:
            return False
        decision = manifest.get("decision")
        sources = manifest.get("sources")
        outputs = manifest.get("outputs")
        if (
            manifest.get("schema_version") != "1.0"
            or manifest.get("status") != "complete"
            or not isinstance(sources, Mapping)
            or set(sources) != _SOURCE_KEYS
            or not isinstance(outputs, Mapping)
        ):
            return False
        try:
            config_bytes, _ = _read_entry_bytes(descriptors["."], "config.yaml")
            config = _load_config_bytes(config_bytes)
            selected = _validate_completed_decision(decision, config)
            _validate_software(manifest.get("software"))
            _assert_decorrelation_contract(
                descriptors,
                selected=selected,
                manifest_present=True,
                terminal_lock_present=True,
            )
            resolved_sources = resolve_decorrelation_sources(
                input_run=config.input_run,
                config_path=sources["study_config"]["path"],
            )
            _validate_source_inventory(resolved_sources)
            assert_decorrelation_sources_unchanged(resolved_sources)
            if (
                resolved_sources.config_bytes != config_bytes
                or dict(sources) != _source_manifest_records(resolved_sources)
            ):
                return False
            current_outputs = _build_output_records(
                layout, descriptors, selected=selected
            )
            if dict(outputs) != current_outputs:
                return False
            final_payload, final_identity = _read_entry_bytes(
                descriptors["artifacts"], "study_manifest.json"
            )
            if final_payload != payload or final_identity != identity:
                return False
            if (
                _build_output_records(layout, descriptors, selected=selected)
                != current_outputs
            ):
                return False
            _revalidate_named_layout(layout)
            return True
        except Exception:
            return False
    except Exception:
        return False
    finally:
        _close_descriptors(descriptors)


def _validate_completed_decision(
    decision: Any, config: DecorrelationConfig
) -> bool:
    if not isinstance(decision, Mapping) or set(decision) != {
        "status",
        "selected_candidate",
        "selected_coefficient",
        "test_opened",
    }:
        raise ValueError("study manifest decision does not match the contract")
    selected = decision["test_opened"]
    if type(selected) is not bool:
        raise ValueError("study manifest test_opened must be a boolean")
    if not selected:
        if dict(decision) != {
            "status": "no_eligible_candidate",
            "selected_candidate": None,
            "selected_coefficient": None,
            "test_opened": False,
        }:
            raise ValueError("study manifest no-selection decision is invalid")
        return False
    coefficient = decision["selected_coefficient"]
    if (
        decision["status"] != "eligible_candidate_test_reported"
        or type(coefficient) is not float
        or coefficient not in config.coefficients
        or decision["selected_candidate"] != _candidate_name(coefficient)
    ):
        raise ValueError("study manifest selected decision is invalid")
    return True


def _install_decorrelation_failure_locked(
    root: int, layout: TrainingOutputLayout, error: BaseException
) -> None:
    if _study_manifest_exists(layout):
        return
    try:
        os.mkdir(".terminal.failed", dir_fd=root)
    except FileExistsError:
        pass
    if _entry_exists(root, "failure.json"):
        return
    try:
        _atomic_publish_bytes(
            root,
            layout.run_dir,
            "failure.json",
            _json_bytes(
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "message": str(error),
                }
            ),
        )
    except Exception:
        pass


def record_decorrelation_failure(
    layout: TrainingOutputLayout, error: BaseException
) -> None:
    """Install one no-clobber terminal failure unless completion already exists."""
    try:
        root = _open_verified_root(layout)
    except Exception:
        return
    locked = False
    try:
        _terminal_lock_acquire(root)
        locked = True
        _install_decorrelation_failure_locked(root, layout, error)
    except Exception:
        pass
    finally:
        if locked:
            _terminal_lock_release(root)
        os.close(root)
