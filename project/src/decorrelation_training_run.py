from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import pickle
import pickletools
import struct
from types import MappingProxyType
from typing import Any, Mapping
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
import yaml

from .external_zz_run import (
    _assert_staged_manifest_unchanged,
    _open_verified_staged_manifest,
    _publish_descriptor_no_clobber,
)
from .full_training_policy import development_fold, validate_mc_frame
from .full_training_evaluation import weighted_pearson
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
    load_training_mc_frame,
    resolve_training_output,
)
from .mass_sculpting_ablation_run import (
    StudySource,
    _resolve_task4a_sources_without_table_load,
)
from .validation import weighted_ks_distance


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
_STUDY_CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "decorrelation_training_drop_top4.yaml"
)
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
_CANDIDATE_COLUMNS = (
    "candidate",
    "coefficient",
    "weighted_oof_auc",
    "maximum_oof_zz_ks",
    "background_score_mass_correlation",
    "eligible",
    "eligibility_reasons",
)
_WORKING_POINT_COLUMNS = (
    "candidate",
    "coefficient",
    "working_point",
    "threshold",
    "target_background_efficiency",
    "achieved_background_efficiency",
    "signal_efficiency",
    "zz_mass_ks_distance",
)
_AUDIT_COLUMNS = (
    "source_row_id",
    "eventNumber",
    "channelNumber",
    "split",
    "label",
    "physical_weight",
    "m4l",
    "development_fold",
)
_TEST_SCORE_COLUMNS = (
    "source_row_id",
    "eventNumber",
    "channelNumber",
    "split",
    "label",
    "physical_weight",
    "m4l",
    "score",
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
        _validate_source_row_ids(frame)
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


def bind_source_row_ids(frame: pd.DataFrame) -> pd.DataFrame:
    """Bind each hash-verified CSV row to its zero-based source ordinal."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("MC source must be a DataFrame")
    if "source_row_id" in frame:
        raise ValueError("MC source already contains source_row_id")
    expected_index = pd.RangeIndex(start=0, stop=len(frame), step=1)
    if not frame.index.equals(expected_index):
        raise ValueError("MC source index must match the CSV row ordinal")
    bound = frame.copy(deep=True)
    bound.insert(0, "source_row_id", np.arange(len(bound), dtype=np.int64))
    return bound


@dataclass(frozen=True, init=False)
class DecorrelationArtifactReceipt:
    _run_identity: tuple[int, int]
    selected: bool
    _selected_coefficient: float | None
    _outputs: Mapping[str, Mapping[str, Any]]
    _model: Any | None
    _model_bytes: bytes | None
    _content_digest: str

    def __new__(cls, *args, **kwargs):
        raise TypeError(
            "DecorrelationArtifactReceipt is returned by "
            "write_decorrelation_artifacts"
        )


def _new_artifact_receipt(
    run_identity: tuple[int, int],
    selected: bool,
    selected_coefficient: float | None,
    outputs: Mapping[str, Mapping[str, Any]],
    *,
    model: Any | None,
    model_bytes: bytes | None,
) -> DecorrelationArtifactReceipt:
    receipt = object.__new__(DecorrelationArtifactReceipt)
    object.__setattr__(receipt, "_run_identity", run_identity)
    object.__setattr__(receipt, "selected", bool(selected))
    object.__setattr__(receipt, "_selected_coefficient", selected_coefficient)
    object.__setattr__(receipt, "_outputs", _freeze_output_records(outputs))
    object.__setattr__(receipt, "_model", model)
    object.__setattr__(receipt, "_model_bytes", model_bytes)
    object.__setattr__(
        receipt,
        "_content_digest",
        _receipt_content_digest(
            run_identity=run_identity,
            selected=selected,
            selected_coefficient=selected_coefficient,
            outputs=outputs,
            model_bytes=model_bytes,
        ),
    )
    return receipt


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
        or any(type(value) is not str for value in no_selection)
        or len(no_selection) != len(set(no_selection))
        or set(no_selection) != approved_decorrelation_artifacts(selected=False)
        or not isinstance(selected, list)
        or any(type(value) is not str for value in selected)
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
        and _exact_frozen_value(raw.get("features"), list(_FEATURES))
        and type(raw.get("folds")) is int
        and raw["folds"] == 5
        and _exact_frozen_value(raw.get("model"), _MODEL)
        and _exact_frozen_value(raw.get("flatness"), _FLATNESS)
        and _exact_frozen_value(raw.get("coefficients"), list(_COEFFICIENTS))
        and _exact_frozen_value(raw.get("working_points"), _WORKING_POINTS)
        and type(raw.get("auc_floor")) is float
        and raw["auc_floor"] == 0.80
        and type(raw.get("ks_limit")) is float
        and raw["ks_limit"] == 0.10
        and raw.get("require_signal_efficiency_above_background") is True
    )


def _exact_frozen_value(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _exact_frozen_value(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _exact_frozen_value(observed, frozen)
            for observed, frozen in zip(actual, expected)
        )
    return actual == expected


def resolve_decorrelation_sources(
    *, input_run: str | Path, config_path: str | Path
) -> DecorrelationSources:
    """Resolve only the exact frozen production config and MC-only receipts."""
    requested_config = Path(os.path.abspath(config_path))
    if requested_config != _STUDY_CONFIG_PATH:
        raise ValueError(
            "decorrelation sources require the canonical project study config"
        )
    config_source = StudySource.from_path(
        "study_config", _STUDY_CONFIG_PATH, capture=True
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


def preflight_decorrelation_dependencies(
    config: DecorrelationConfig,
    software: Mapping[str, Any],
) -> None:
    """Validate the pinned hep_ml distribution and frozen constructor API."""
    _validate_software(software)
    try:
        from hep_ml.gradientboosting import UGradientBoostingClassifier
        from hep_ml.losses import KnnFlatnessLossFunction

        from .decorrelation_training import build_flatness_model

        coefficient = config.coefficients[0]
        model = build_flatness_model(config, coefficient)
    except Exception as error:
        raise RuntimeError(
            "hep_ml 0.8.0 does not expose the approved flatness API"
        ) from error
    loss = getattr(model, "loss", None)
    if (
        type(model) is not UGradientBoostingClassifier
        or type(loss) is not KnnFlatnessLossFunction
        or model.n_estimators != config.model["n_estimators"]
        or model.learning_rate != config.model["learning_rate"]
        or model.max_depth != config.model["max_depth"]
        or model.min_samples_leaf != config.model["min_samples_leaf"]
        or model.subsample != config.model["subsample"]
        or model.random_state != config.model["random_seed"]
        or tuple(model.train_features) != config.features
        or list(loss.uniform_features) != [config.flatness["uniform_feature"]]
        or not np.array_equal(
            np.asarray(loss.uniform_label),
            np.asarray([config.flatness["uniform_label"]]),
        )
        or loss.n_neighbours != config.flatness["n_neighbours"]
        or loss.max_groups != config.flatness["max_groups"]
        or loss.power != config.flatness["power"]
        or loss.fl_coefficient != coefficient
        or loss.allow_wrong_signs is not config.flatness["allow_wrong_signs"]
    ):
        raise RuntimeError("hep_ml 0.8.0 flatness API changes the frozen policy")


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
        selected_coefficient = _validate_artifact_values(
            artifacts, config=config
        )
        selected = selected_coefficient is not None
        serialized = _serialize_artifacts(
            artifacts,
            selected=selected,
            selected_coefficient=selected_coefficient,
        )
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
        return _new_artifact_receipt(
            layout.directory_identities["."],
            selected,
            selected_coefficient,
            expected_outputs,
            model=artifacts["model"],
            model_bytes=serialized.get("flatness_model"),
        )
    except Exception as error:
        record_decorrelation_failure(layout, error)
        raise
    finally:
        _close_descriptors(descriptors)


def _validate_artifact_values(
    artifacts: Mapping[str, Any], *, config: DecorrelationConfig
) -> float | None:
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
        _validate_png_bytes(payload, name)

    _validate_candidate_tables(
        artifacts["candidate_results"],
        artifacts["working_point_metrics"],
        config,
    )
    _validate_oof_scores(artifacts["oof_scores"], config)
    oof_winner = _validate_candidate_metrics_from_oof(
        artifacts["candidate_results"],
        artifacts["working_point_metrics"],
        artifacts["oof_scores"],
        config,
    )
    selected_candidate = _validate_selection_semantics(
        selection,
        config,
        artifacts["candidate_results"],
        selected=selected,
        decision=None,
    )
    if selected_candidate != oof_winner:
        raise ValueError("selection does not match the winner recomputed from OOF scores")

    if selected:
        _validate_finite_frame(
            artifacts["selected_oof_scores"], "selected_oof_scores"
        )
        _validate_finite_frame(artifacts["test_scores"], "test_scores")
        if not isinstance(artifacts["test_metrics"], Mapping):
            raise TypeError("test_metrics must be a mapping")
        _json_bytes(artifacts["test_metrics"])
        assert selected_candidate is not None
        _validate_selected_oof_scores(
            artifacts["selected_oof_scores"],
            artifacts["oof_scores"],
            selected_candidate,
        )
        _validate_test_scores(artifacts["test_scores"])
        selected_points = artifacts["working_point_metrics"].loc[
            artifacts["working_point_metrics"]["candidate"]
            == selected_candidate
        ]
        _validate_test_metrics(
            artifacts["test_metrics"],
            config,
            test_scores=artifacts["test_scores"],
            selected_working_points=selected_points,
        )
        selected_row = artifacts["candidate_results"].loc[
            artifacts["candidate_results"]["candidate"]
            == selected_candidate
        ].iloc[0]
        return float(selected_row["coefficient"])
    return None


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
    artifacts: Mapping[str, Any],
    *,
    selected: bool,
    selected_coefficient: float | None,
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
        if selected_coefficient is None:
            raise ValueError("selected artifacts are missing a coefficient")
        serialized.update(
            test_metrics=_json_bytes(artifacts["test_metrics"]),
            flatness_model=_trusted_model_bytes(
                artifacts["model"], selected_coefficient
            ),
            selected_oof_scores=_csv_bytes(artifacts["selected_oof_scores"]),
            test_scores=_csv_bytes(artifacts["test_scores"]),
            **{
                "selected_mass_sculpting.png": plots[
                    "selected_mass_sculpting.png"
                ]
            },
        )
    return serialized


def _trusted_model_bytes(model: Any, selected_coefficient: float) -> bytes:
    from hep_ml.gradientboosting import UGradientBoostingClassifier
    from hep_ml.losses import KnnFlatnessLossFunction

    if type(model) is not UGradientBoostingClassifier:
        raise TypeError("selected model must be a local hep_ml flatness model")
    loss = getattr(model, "loss", None)
    if type(loss) is not KnnFlatnessLossFunction:
        raise ValueError(
            "selected flatness model must use KnnFlatnessLossFunction"
        )
    model_policy = {
        "n_estimators": 300,
        "learning_rate": 0.05,
        "max_depth": 3,
        "min_samples_leaf": 50,
        "subsample": 0.8,
    }
    if any(
        getattr(model, name, None) != expected
        for name, expected in model_policy.items()
    ):
        raise ValueError("selected flatness model changes the frozen model policy")
    if tuple(getattr(model, "train_features", ())) != _FEATURES:
        raise ValueError("selected model does not use the exact DropTop4 features")
    if (
        list(getattr(loss, "uniform_features", ())) != ["m4l"]
        or not np.array_equal(
            np.asarray(getattr(loss, "uniform_label", ())), np.asarray([0])
        )
        or getattr(loss, "n_neighbours", None) != 100
        or getattr(loss, "max_groups", None) != 5000
        or getattr(loss, "power", None) != 2.0
        or getattr(loss, "fl_coefficient", None) != selected_coefficient
        or getattr(loss, "allow_wrong_signs", None) is not True
    ):
        raise ValueError("selected flatness model changes the frozen loss policy")
    if not _fitted_random_state_matches_seed(model, seed=42):
        raise ValueError(
            "selected flatness model changes the frozen random state policy"
        )
    verification = _model_verification_frame()
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="X has feature names, but NearestNeighbors was fitted without feature names",
                category=UserWarning,
            )
            expected = np.asarray(model.predict_proba(verification), dtype=float)
    except Exception as error:
        raise ValueError("selected hep_ml model is not fitted") from error
    if (
        expected.shape != (len(verification), 2)
        or not np.isfinite(expected).all()
        or (expected < 0.0).any()
        or (expected > 1.0).any()
        or not np.array_equal(expected.sum(axis=1), np.ones(len(verification)))
    ):
        raise ValueError(
            "selected model verification predictions do not match the classifier contract"
        )
    payload = pickle.dumps(model, protocol=5)
    restored = pickle.loads(payload)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="X has feature names, but NearestNeighbors was fitted without feature names",
            category=UserWarning,
        )
        observed = np.asarray(restored.predict_proba(verification), dtype=float)
    try:
        np.testing.assert_allclose(observed, expected, rtol=0.0, atol=0.0)
    except AssertionError as error:
        raise ValueError(
            "selected model pickle round-trip changed verification predictions"
        ) from error
    safe_observed = _validate_model_pickle_semantics(
        payload, selected_coefficient
    )
    try:
        np.testing.assert_allclose(
            safe_observed,
            expected,
            rtol=0.0,
            atol=4.0 * np.finfo(float).eps,
        )
    except AssertionError as error:
        raise ValueError(
            "safe model audit changed verification predictions"
        ) from error
    return payload


def _fitted_random_state_matches_seed(model: Any, *, seed: int) -> bool:
    loss = model.loss
    model_random = getattr(model, "random_state", None)
    loss_random = getattr(loss, "random_state", None)
    if not isinstance(model_random, np.random.RandomState) or not isinstance(
        loss_random, np.random.RandomState
    ):
        return False
    labels = np.asarray(getattr(loss, "y", ()))
    if labels.ndim != 1 or labels.size == 0:
        return False
    expected_loss = np.random.RandomState(seed)
    for label in np.asarray(loss.uniform_label):
        count = int(np.count_nonzero(labels == label))
        if count > int(loss.max_groups):
            expected_loss.choice(
                count, size=int(loss.max_groups), replace=False
            )
    if not _random_states_equal(loss_random, expected_loss):
        return False

    estimators = getattr(model, "estimators", None)
    if not isinstance(estimators, list) or len(estimators) != model.n_estimators:
        return False
    expected_model = np.random.RandomState(seed)
    n_samples = len(labels)
    n_inbag = int(float(model.subsample) * n_samples)
    for _ in range(model.n_estimators):
        expected_model.choice(n_samples, size=n_inbag, replace=False)
        expected_model.randint(np.iinfo(np.int32).max)
    return _random_states_equal(model_random, expected_model)


def _random_states_equal(
    first: np.random.RandomState, second: np.random.RandomState
) -> bool:
    first_state = first.get_state()
    second_state = second.get_state()
    return (
        first_state[0] == second_state[0]
        and np.array_equal(first_state[1], second_state[1])
        and first_state[2:] == second_state[2:]
    )


@dataclass(frozen=True)
class _SafePickleGlobal:
    module: str
    name: str


@dataclass(eq=False)
class _SafePickleNode:
    kind: str
    constructor: _SafePickleGlobal
    args: tuple[Any, ...]
    state: Any = None
    state_installed: bool = False


_SAFE_MODEL_GLOBALS = frozenset(
    {
        ("hep_ml.gradientboosting", "UGradientBoostingClassifier"),
        ("hep_ml.losses", "KnnFlatnessLossFunction"),
        ("hep_ml.tree", "SklearnClusteringTree"),
        ("numpy.random._pickle", "__randomstate_ctor"),
        ("numpy.random._pickle", "__bit_generator_ctor"),
        ("numpy.random._mt19937", "MT19937"),
        ("numpy._core.numeric", "_frombuffer"),
        ("numpy.core.numeric", "_frombuffer"),
        ("numpy", "dtype"),
        ("numpy._core.multiarray", "scalar"),
        ("numpy.core.multiarray", "scalar"),
        ("scipy.sparse._csr", "csr_matrix"),
        ("sklearn.tree._tree", "Tree"),
    }
)


def _validate_model_pickle_semantics(
    payload: bytes, selected_coefficient: float
) -> np.ndarray:
    """Audit a fitted hep_ml pickle without importing or invoking its globals."""
    if (
        not isinstance(payload, bytes)
        or len(payload) < 1_000
        or len(payload) > 512 * 1024 * 1024
        or not payload.startswith(b"\x80\x05")
    ):
        raise ValueError("flatness model pickle does not match the frozen policy")
    try:
        root = _safe_parse_pickle(payload)
        if not _safe_node_is(
            root,
            kind="newobj",
            module="hep_ml.gradientboosting",
            name="UGradientBoostingClassifier",
        ):
            raise ValueError("flatness model pickle changes the classifier type")
        if root.args != () or not isinstance(root.state, dict):
            raise ValueError("flatness model pickle has invalid classifier state")
        state = root.state
        required_state = {
            "loss",
            "n_estimators",
            "learning_rate",
            "subsample",
            "min_samples_split",
            "min_samples_leaf",
            "max_features",
            "max_leaf_nodes",
            "max_depth",
            "update_tree",
            "train_features",
            "random_state",
            "splitter",
            "classes_",
            "estimators",
            "scores",
            "n_features",
            "initial_step",
        }
        if set(state) != required_state:
            raise ValueError("flatness model pickle changes classifier state")
        expected_policy = {
            "n_estimators": 300,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "min_samples_split": 2,
            "min_samples_leaf": 50,
            "max_features": None,
            "max_leaf_nodes": None,
            "max_depth": 3,
            "update_tree": True,
            "splitter": "best",
            "n_features": len(_FEATURES),
        }
        if any(state.get(name) != value for name, value in expected_policy.items()):
            raise ValueError("flatness model pickle changes the frozen model policy")
        if state.get("train_features") != list(_FEATURES):
            raise ValueError("flatness model pickle changes the DropTop4 features")
        if state.get("classes_") != [0, 1]:
            raise ValueError("flatness model pickle changes the classifier labels")
        initial_step = state.get("initial_step")
        if (
            isinstance(initial_step, bool)
            or not isinstance(initial_step, (int, float))
            or not np.isfinite(float(initial_step))
        ):
            raise ValueError("flatness model pickle has an invalid initial step")

        loss = state["loss"]
        labels = _validate_safe_loss(loss, selected_coefficient)
        _validate_safe_random_state_policy(
            state["random_state"],
            loss.state["random_state"],
            labels=labels,
            uniform_labels=_safe_numpy_array(
                loss.state["uniform_label"], allowed_codes={"i8"}
            ),
            max_groups=5000,
            n_estimators=300,
            subsample=0.8,
        )
        probabilities = _safe_model_verification_probabilities(root)
        if (
            probabilities.shape != (len(_model_verification_frame()), 2)
            or not np.isfinite(probabilities).all()
            or (probabilities < 0.0).any()
            or (probabilities > 1.0).any()
            or not np.allclose(
                probabilities.sum(axis=1),
                np.ones(len(probabilities)),
                rtol=0.0,
                atol=np.finfo(float).eps,
            )
        ):
            raise ValueError(
                "flatness model pickle predictions violate the classifier contract"
            )
        return probabilities
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(
            "flatness model pickle does not match the frozen semantics"
        ) from error


def _safe_parse_pickle(payload: bytes) -> Any:
    stack: list[Any] = []
    memo: dict[int, Any] = {}
    mark = object()
    operation_count = 0
    protocol_seen = False

    def take_marked() -> list[Any]:
        for index in range(len(stack) - 1, -1, -1):
            if stack[index] is mark:
                values = stack[index + 1 :]
                del stack[index:]
                return values
        raise ValueError("flatness model pickle has an unmatched mark")

    try:
        for operation, argument, position in pickletools.genops(payload):
            operation_count += 1
            if operation_count > 2_000_000 or len(stack) > 2_000_000:
                raise ValueError("flatness model pickle exceeds safe limits")
            name = operation.name
            if name == "PROTO":
                if protocol_seen or position != 0 or argument != 5:
                    raise ValueError("flatness model pickle must use protocol 5")
                protocol_seen = True
            elif name == "FRAME":
                if not protocol_seen:
                    raise ValueError("flatness model pickle frame precedes protocol")
            elif name == "MARK":
                stack.append(mark)
            elif name == "NONE":
                stack.append(None)
            elif name == "NEWTRUE":
                stack.append(True)
            elif name == "NEWFALSE":
                stack.append(False)
            elif name in {
                "BININT",
                "BININT1",
                "BININT2",
                "BINFLOAT",
                "LONG1",
                "LONG4",
                "INT",
                "LONG",
            }:
                stack.append(argument)
            elif name in {
                "SHORT_BINUNICODE",
                "BINUNICODE",
                "BINUNICODE8",
                "UNICODE",
            }:
                if not isinstance(argument, str):
                    raise ValueError("flatness model pickle text is invalid")
                stack.append(argument)
            elif name in {
                "SHORT_BINBYTES",
                "BINBYTES",
                "BINBYTES8",
                "BYTEARRAY8",
            }:
                stack.append(bytes(argument))
            elif name == "EMPTY_DICT":
                stack.append({})
            elif name == "EMPTY_LIST":
                stack.append([])
            elif name == "EMPTY_TUPLE":
                stack.append(())
            elif name == "TUPLE":
                stack.append(tuple(take_marked()))
            elif name == "TUPLE1":
                if not stack:
                    raise ValueError("flatness model pickle stack underflow")
                stack[-1:] = [(stack[-1],)]
            elif name == "TUPLE2":
                if len(stack) < 2:
                    raise ValueError("flatness model pickle stack underflow")
                stack[-2:] = [(stack[-2], stack[-1])]
            elif name == "TUPLE3":
                if len(stack) < 3:
                    raise ValueError("flatness model pickle stack underflow")
                stack[-3:] = [(stack[-3], stack[-2], stack[-1])]
            elif name == "APPEND":
                if len(stack) < 2 or not isinstance(stack[-2], list):
                    raise ValueError("flatness model pickle append is invalid")
                value = stack.pop()
                stack[-1].append(value)
            elif name == "APPENDS":
                values = take_marked()
                if not stack or not isinstance(stack[-1], list):
                    raise ValueError("flatness model pickle appends are invalid")
                stack[-1].extend(values)
            elif name == "SETITEM":
                if len(stack) < 3 or not isinstance(stack[-3], dict):
                    raise ValueError("flatness model pickle setitem is invalid")
                value = stack.pop()
                key = stack.pop()
                stack[-1][key] = value
            elif name == "SETITEMS":
                values = take_marked()
                if (
                    not stack
                    or not isinstance(stack[-1], dict)
                    or len(values) % 2
                ):
                    raise ValueError("flatness model pickle setitems are invalid")
                for index in range(0, len(values), 2):
                    stack[-1][values[index]] = values[index + 1]
            elif name == "MEMOIZE":
                if not stack:
                    raise ValueError("flatness model pickle memo is invalid")
                memo[len(memo)] = stack[-1]
            elif name in {"BINPUT", "LONG_BINPUT", "PUT"}:
                if not stack or type(argument) is not int or argument in memo:
                    raise ValueError("flatness model pickle memo index is invalid")
                memo[argument] = stack[-1]
            elif name in {"BINGET", "LONG_BINGET", "GET"}:
                if type(argument) is not int or argument not in memo:
                    raise ValueError("flatness model pickle memo reference is invalid")
                stack.append(memo[argument])
            elif name in {"STACK_GLOBAL", "GLOBAL"}:
                if name == "STACK_GLOBAL":
                    if len(stack) < 2:
                        raise ValueError("flatness model pickle global is invalid")
                    global_name = stack.pop()
                    module = stack.pop()
                else:
                    if not isinstance(argument, str) or " " not in argument:
                        raise ValueError("flatness model pickle global is invalid")
                    module, global_name = argument.split(" ", 1)
                if (
                    not isinstance(module, str)
                    or not isinstance(global_name, str)
                    or (module, global_name) not in _SAFE_MODEL_GLOBALS
                ):
                    raise ValueError("flatness model pickle references an unsafe global")
                stack.append(_SafePickleGlobal(module, global_name))
            elif name in {"REDUCE", "NEWOBJ"}:
                if len(stack) < 2:
                    raise ValueError("flatness model pickle constructor is invalid")
                args = stack.pop()
                constructor = stack.pop()
                if (
                    not isinstance(args, tuple)
                    or not isinstance(constructor, _SafePickleGlobal)
                    or (constructor.module, constructor.name)
                    not in _SAFE_MODEL_GLOBALS
                ):
                    raise ValueError("flatness model pickle constructor is unsafe")
                stack.append(
                    _SafePickleNode(
                        "reduce" if name == "REDUCE" else "newobj",
                        constructor,
                        args,
                    )
                )
            elif name == "BUILD":
                if len(stack) < 2 or not isinstance(stack[-2], _SafePickleNode):
                    raise ValueError("flatness model pickle build is invalid")
                state = stack.pop()
                target = stack[-1]
                if target.state_installed:
                    raise ValueError("flatness model pickle repeats object state")
                target.state = state
                target.state_installed = True
            elif name == "STOP":
                if (
                    not protocol_seen
                    or position != len(payload) - 1
                    or len(stack) != 1
                    or stack[0] is mark
                ):
                    raise ValueError("flatness model pickle is incomplete")
                return stack[0]
            else:
                raise ValueError(
                    f"flatness model pickle uses unsupported opcode {name}"
                )
    except (TypeError, KeyError, IndexError, OverflowError) as error:
        raise ValueError("flatness model pickle structure is invalid") from error
    raise ValueError("flatness model pickle has no terminal opcode")


def _safe_node_is(
    value: Any, *, kind: str, module: str, name: str
) -> bool:
    return (
        isinstance(value, _SafePickleNode)
        and value.kind == kind
        and value.constructor == _SafePickleGlobal(module, name)
        and value.state_installed
    )


def _validate_safe_loss(
    loss: Any, selected_coefficient: float
) -> np.ndarray:
    if not _safe_node_is(
        loss,
        kind="newobj",
        module="hep_ml.losses",
        name="KnnFlatnessLossFunction",
    ) or loss.args != ():
        raise ValueError("flatness model pickle changes the loss type")
    if not isinstance(loss.state, dict):
        raise ValueError("flatness model pickle has invalid loss state")
    required = {
        "n_neighbours",
        "max_groups",
        "random_state",
        "uniform_features",
        "uniform_label",
        "power",
        "fl_coefficient",
        "allow_wrong_signs",
        "regularization_",
        "group_indices",
        "group_matrices",
        "group_weights",
        "label_masks",
        "y",
        "y_signed",
        "sample_weight",
        "divided_weight",
    }
    if set(loss.state) != required:
        raise ValueError("flatness model pickle changes the loss state")
    if (
        loss.state["n_neighbours"] != 100
        or loss.state["max_groups"] != 5000
        or loss.state["uniform_features"] != ["m4l"]
        or loss.state["power"] != 2.0
        or loss.state["fl_coefficient"] != selected_coefficient
        or loss.state["allow_wrong_signs"] is not True
    ):
        raise ValueError("flatness model pickle changes the frozen loss policy")
    uniform = _safe_numpy_array(
        loss.state["uniform_label"], allowed_codes={"i8"}
    )
    if uniform.shape != (1,) or not np.array_equal(uniform, np.asarray([0])):
        raise ValueError("flatness model pickle changes the uniform label")
    labels = _safe_numpy_array(loss.state["y"], allowed_codes={"i8"})
    if (
        labels.ndim != 1
        or labels.size == 0
        or not set(labels.tolist()) <= {0, 1}
    ):
        raise ValueError("flatness model pickle has invalid fitted labels")
    return labels.astype(int, copy=False)


def _safe_numpy_array(
    value: Any, *, allowed_codes: set[str]
) -> np.ndarray:
    if not (
        _safe_node_is_frombuffer(value)
        and len(value.args) == 4
        and isinstance(value.args[0], bytes)
        and isinstance(value.args[2], tuple)
        and value.args[3] == "C"
    ):
        raise ValueError("flatness model pickle contains an invalid array")
    payload, dtype_value, shape, _ = value.args
    code, byte_order = _safe_dtype(dtype_value)
    if code not in allowed_codes:
        raise ValueError("flatness model pickle changes an array dtype")
    dtype_map = {
        "i8": np.dtype("<i8"),
        "i4": np.dtype("<i4"),
        "u4": np.dtype("<u4"),
        "u1": np.dtype("u1"),
        "f8": np.dtype("<f8"),
        "b1": np.dtype("?"),
    }
    if code not in dtype_map or byte_order not in {"<", "|"}:
        raise ValueError("flatness model pickle uses an invalid array dtype")
    if (
        any(type(dimension) is not int or dimension < 0 for dimension in shape)
        or len(shape) > 4
    ):
        raise ValueError("flatness model pickle contains an invalid array shape")
    count = int(np.prod(shape, dtype=np.int64)) if shape else 1
    dtype = dtype_map[code]
    if count > 100_000_000 or len(payload) != count * dtype.itemsize:
        raise ValueError("flatness model pickle array size is inconsistent")
    return np.frombuffer(payload, dtype=dtype).reshape(shape).copy()


def _safe_node_is_frombuffer(value: Any) -> bool:
    return (
        isinstance(value, _SafePickleNode)
        and value.kind == "reduce"
        and value.constructor.name == "_frombuffer"
        and value.constructor.module
        in {"numpy._core.numeric", "numpy.core.numeric"}
        and not value.state_installed
    )


def _safe_dtype(value: Any) -> tuple[str, str]:
    if not (
        _safe_node_is(
            value,
            kind="reduce",
            module="numpy",
            name="dtype",
        )
        and len(value.args) == 3
        and isinstance(value.args[0], str)
        and value.args[1:] == (False, True)
        and isinstance(value.state, tuple)
        and len(value.state) == 8
        and value.state[0] == 3
        and value.state[1] in {"<", "|"}
    ):
        raise ValueError("flatness model pickle contains an invalid dtype")
    return value.args[0], value.state[1]


def _validate_safe_random_state_policy(
    model_random: Any,
    loss_random: Any,
    *,
    labels: np.ndarray,
    uniform_labels: np.ndarray,
    max_groups: int,
    n_estimators: int,
    subsample: float,
) -> None:
    expected_loss = np.random.RandomState(42)
    for label in uniform_labels:
        count = int(np.count_nonzero(labels == label))
        if count > max_groups:
            expected_loss.choice(count, size=max_groups, replace=False)
    if not _safe_random_state_equals(loss_random, expected_loss):
        raise ValueError("flatness model pickle changes the loss random state")

    expected_model = np.random.RandomState(42)
    n_samples = len(labels)
    n_inbag = int(subsample * n_samples)
    for _ in range(n_estimators):
        expected_model.choice(n_samples, size=n_inbag, replace=False)
        expected_model.randint(np.iinfo(np.int32).max)
    if not _safe_random_state_equals(model_random, expected_model):
        raise ValueError("flatness model pickle changes the model random state")


def _safe_random_state_equals(
    value: Any, expected: np.random.RandomState
) -> bool:
    if not (
        isinstance(value, _SafePickleNode)
        and value.kind == "reduce"
        and value.constructor
        == _SafePickleGlobal("numpy.random._pickle", "__randomstate_ctor")
        and len(value.args) == 1
        and value.state_installed
        and isinstance(value.state, dict)
    ):
        return False
    bit_generator = value.args[0]
    if not (
        isinstance(bit_generator, _SafePickleNode)
        and bit_generator.kind == "reduce"
        and bit_generator.constructor
        == _SafePickleGlobal("numpy.random._pickle", "__bit_generator_ctor")
        and bit_generator.args
        == ((_SafePickleGlobal("numpy.random._mt19937", "MT19937")),)
        and bit_generator.state_installed
        and isinstance(bit_generator.state, tuple)
        and len(bit_generator.state) == 2
        and bit_generator.state[1] is None
    ):
        return False
    state = value.state
    inner = state.get("state")
    if (
        set(state) != {"bit_generator", "state", "has_gauss", "gauss"}
        or state.get("bit_generator") != "MT19937"
        or not isinstance(inner, dict)
        or set(inner) != {"key", "pos"}
        or type(inner.get("pos")) is not int
        or state.get("has_gauss") not in {0, 1}
        or not isinstance(state.get("gauss"), float)
    ):
        return False
    try:
        key = _safe_numpy_array(inner["key"], allowed_codes={"u4"})
    except ValueError:
        return False
    expected_state = expected.get_state()
    return (
        key.shape == (624,)
        and np.array_equal(key, expected_state[1])
        and inner["pos"] == expected_state[2]
        and state["has_gauss"] == expected_state[3]
        and state["gauss"] == expected_state[4]
    )


def _safe_model_verification_probabilities(root: _SafePickleNode) -> np.ndarray:
    state = root.state
    estimators = state["estimators"]
    if not isinstance(estimators, list) or len(estimators) != 300:
        raise ValueError("flatness model pickle changes the fitted tree count")
    matrix = _model_verification_frame().loc[:, list(_FEATURES)].to_numpy(
        dtype=float
    )
    scores = np.full(len(matrix), float(state["initial_step"]), dtype=float)
    for estimator in estimators:
        if not isinstance(estimator, list) or len(estimator) != 2:
            raise ValueError("flatness model pickle contains an invalid estimator")
        tree, leaf_values_value = estimator
        leaf_values = _safe_numpy_array(
            leaf_values_value, allowed_codes={"f8"}
        )
        scores += 0.05 * _safe_tree_predictions(tree, leaf_values, matrix)
    positive = np.empty(len(scores), dtype=float)
    nonnegative = scores >= 0.0
    positive[nonnegative] = 1.0 / (1.0 + np.exp(-scores[nonnegative]))
    exponential = np.exp(scores[~nonnegative])
    positive[~nonnegative] = exponential / (1.0 + exponential)
    return np.column_stack((1.0 - positive, positive))


def _safe_tree_predictions(
    tree: Any, leaf_values: np.ndarray, matrix: np.ndarray
) -> np.ndarray:
    if not _safe_node_is(
        tree,
        kind="newobj",
        module="hep_ml.tree",
        name="SklearnClusteringTree",
    ) or not isinstance(tree.state, dict):
        raise ValueError("flatness model pickle changes a fitted tree type")
    required_tree_state = {
        "criterion",
        "splitter",
        "max_depth",
        "min_samples_split",
        "min_samples_leaf",
        "min_weight_fraction_leaf",
        "max_features",
        "max_leaf_nodes",
        "random_state",
        "min_impurity_decrease",
        "class_weight",
        "ccp_alpha",
        "monotonic_cst",
        "n_features_in_",
        "n_outputs_",
        "max_features_",
        "tree_",
    }
    state = tree.state
    if (
        set(state) != required_tree_state
        or state["criterion"] != "squared_error"
        or state["splitter"] != "best"
        or state["max_depth"] != 3
        or state["min_samples_split"] != 2
        or state["min_samples_leaf"] != 50
        or state["n_features_in_"] != len(_FEATURES)
        or state["n_outputs_"] != 1
    ):
        raise ValueError("flatness model pickle changes the fitted tree policy")
    raw_tree = state["tree_"]
    if not (
        isinstance(raw_tree, _SafePickleNode)
        and raw_tree.kind == "reduce"
        and raw_tree.constructor
        == _SafePickleGlobal("sklearn.tree._tree", "Tree")
        and len(raw_tree.args) == 3
        and raw_tree.args[0] == len(_FEATURES)
        and raw_tree.args[2] == 1
        and raw_tree.state_installed
        and isinstance(raw_tree.state, dict)
    ):
        raise ValueError("flatness model pickle contains an invalid sklearn tree")
    class_counts = _safe_numpy_array(raw_tree.args[1], allowed_codes={"i8"})
    if class_counts.shape != (1,) or not np.array_equal(
        class_counts, np.asarray([1])
    ):
        raise ValueError("flatness model pickle changes tree output shape")
    tree_state = raw_tree.state
    if set(tree_state) != {"max_depth", "node_count", "nodes", "values"}:
        raise ValueError("flatness model pickle changes sklearn tree state")
    node_count = tree_state["node_count"]
    depth = tree_state["max_depth"]
    if (
        type(node_count) is not int
        or not 1 <= node_count <= 15
        or type(depth) is not int
        or not 0 <= depth <= 3
    ):
        raise ValueError("flatness model pickle has invalid tree dimensions")
    nodes = _safe_tree_nodes(tree_state["nodes"], node_count)
    _validate_static_tree_topology(nodes, claimed_max_depth=depth)
    values = _safe_numpy_array(tree_state["values"], allowed_codes={"f8"})
    if (
        values.shape != (node_count, 1, 1)
        or leaf_values.shape != (node_count,)
        or not np.isfinite(values).all()
        or not np.isfinite(leaf_values).all()
    ):
        raise ValueError("flatness model pickle has invalid tree values")
    predictions = np.empty(len(matrix), dtype=float)
    for row_index, row in enumerate(matrix):
        node_index = 0
        for _ in range(node_count):
            left, right, feature, threshold, _, _, _, missing_left = nodes[
                node_index
            ]
            if left == -1 and right == -1:
                if feature != -2:
                    raise ValueError("flatness model pickle has an invalid leaf")
                predictions[row_index] = leaf_values[node_index]
                break
            if (
                not 0 <= left < node_count
                or not 0 <= right < node_count
                or left == node_index
                or right == node_index
                or not 0 <= feature < len(_FEATURES)
                or missing_left not in {0, 1}
            ):
                raise ValueError("flatness model pickle has an invalid branch")
            node_index = left if row[feature] <= threshold else right
        else:
            raise ValueError("flatness model pickle tree contains a cycle")
    return predictions


def _validate_static_tree_topology(
    nodes: list[tuple[Any, ...]], *, claimed_max_depth: int
) -> None:
    """Validate the complete serialized sklearn tree without executing it."""
    node_count = len(nodes)
    children: list[tuple[int, ...]] = []
    parent_counts = [0] * node_count
    for node_index, node in enumerate(nodes):
        left, right, feature, threshold, _, _, _, missing_left = node
        if missing_left not in {0, 1}:
            raise ValueError("flatness model pickle has an invalid tree node")
        if left == -1 or right == -1:
            if (
                left != -1
                or right != -1
                or feature != -2
                or threshold != -2.0
            ):
                raise ValueError("flatness model pickle has an invalid leaf sentinel")
            children.append(())
            continue
        if (
            not 0 <= left < node_count
            or not 0 <= right < node_count
            or left == node_index
            or right == node_index
            or not 0 <= feature < len(_FEATURES)
        ):
            raise ValueError("flatness model pickle has an invalid branch")
        children.append((left, right))
        parent_counts[left] += 1
        parent_counts[right] += 1

    visit_state = [0] * node_count
    for start in range(node_count):
        if visit_state[start] != 0:
            continue
        stack = [(start, False)]
        while stack:
            node_index, exiting = stack.pop()
            if exiting:
                visit_state[node_index] = 2
                continue
            if visit_state[node_index] == 1:
                raise ValueError("flatness model pickle tree contains a cycle")
            if visit_state[node_index] == 2:
                continue
            visit_state[node_index] = 1
            stack.append((node_index, True))
            stack.extend((child, False) for child in children[node_index])

    reachable: set[int] = set()
    stack = [0]
    maximum_depth = 0
    depths = [0] * node_count
    while stack:
        node_index = stack.pop()
        if node_index in reachable:
            continue
        reachable.add(node_index)
        maximum_depth = max(maximum_depth, depths[node_index])
        for child in children[node_index]:
            depths[child] = depths[node_index] + 1
            stack.append(child)
    if reachable != set(range(node_count)):
        raise ValueError("flatness model pickle tree contains unreachable nodes")
    if parent_counts[0] != 0 or any(count != 1 for count in parent_counts[1:]):
        raise ValueError("flatness model pickle is not a proper tree")
    if maximum_depth != claimed_max_depth or maximum_depth > 3:
        raise ValueError("flatness model pickle has an invalid actual maximum depth")


def _safe_tree_nodes(value: Any, node_count: int) -> list[tuple[Any, ...]]:
    if not (
        _safe_node_is_frombuffer(value)
        and len(value.args) == 4
        and isinstance(value.args[0], bytes)
        and value.args[2] == (node_count,)
        and value.args[3] == "C"
    ):
        raise ValueError("flatness model pickle contains invalid tree nodes")
    payload, dtype_value, _, _ = value.args
    code, byte_order = _safe_dtype(dtype_value)
    expected_names = (
        "left_child",
        "right_child",
        "feature",
        "threshold",
        "impurity",
        "n_node_samples",
        "weighted_n_node_samples",
        "missing_go_to_left",
    )
    state = dtype_value.state
    if (
        code != "V64"
        or byte_order != "|"
        or state[3] != expected_names
        or not isinstance(state[4], dict)
        or set(state[4]) != set(expected_names)
        or state[5:] != (64, 1, 16)
        or len(payload) != node_count * 64
    ):
        raise ValueError("flatness model pickle changes the tree-node dtype")
    expected_fields = {
        "left_child": ("i8", 0),
        "right_child": ("i8", 8),
        "feature": ("i8", 16),
        "threshold": ("f8", 24),
        "impurity": ("f8", 32),
        "n_node_samples": ("i8", 40),
        "weighted_n_node_samples": ("f8", 48),
        "missing_go_to_left": ("u1", 56),
    }
    for name, (expected_code, expected_offset) in expected_fields.items():
        field = state[4][name]
        if (
            not isinstance(field, tuple)
            or len(field) != 2
            or field[1] != expected_offset
            or _safe_dtype(field[0])[0] != expected_code
        ):
            raise ValueError("flatness model pickle changes the tree-node fields")
    records: list[tuple[Any, ...]] = []
    for index in range(node_count):
        record = struct.unpack_from("<qqqddqdB7x", payload, index * 64)
        if (
            not np.isfinite(record[3])
            or not np.isfinite(record[4])
            or not np.isfinite(record[6])
            or record[5] < 0
        ):
            raise ValueError("flatness model pickle contains invalid tree nodes")
        records.append(record)
    return records


def _validate_receipt_evidence(
    layout: TrainingOutputLayout,
    receipt: DecorrelationArtifactReceipt,
    *,
    selected_coefficient: float | None,
) -> bytes | None:
    if type(receipt) is not DecorrelationArtifactReceipt:
        raise FileNotFoundError(
            "publisher requires a DecorrelationArtifactReceipt"
        )
    try:
        run_identity = receipt._run_identity
        selected = receipt.selected
        receipt_coefficient = receipt._selected_coefficient
        outputs = receipt._outputs
        model = receipt._model
        model_bytes = receipt._model_bytes
        content_digest = receipt._content_digest
    except AttributeError as error:
        raise ValueError(
            "artifact receipt is missing writer-bound content evidence"
        ) from error
    if (
        layout.directory_identities is None
        or run_identity != layout.directory_identities.get(".")
    ):
        raise ValueError("artifact receipt does not belong to this claimed run")
    if type(selected) is not bool or not isinstance(outputs, Mapping):
        raise ValueError("artifact receipt metadata is invalid")
    if receipt_coefficient != selected_coefficient:
        raise ValueError("artifact receipt changes the selected coefficient")
    expected_digest = _receipt_content_digest(
        run_identity=run_identity,
        selected=selected,
        selected_coefficient=receipt_coefficient,
        outputs=outputs,
        model_bytes=model_bytes,
    )
    if not isinstance(content_digest, str) or content_digest != expected_digest:
        raise ValueError("artifact receipt writer-bound content evidence changed")
    if not selected:
        if (
            selected_coefficient is not None
            or model is not None
            or model_bytes is not None
        ):
            raise ValueError("no-selection receipt contains model evidence")
        return None
    if selected_coefficient is None:
        raise ValueError("selected receipt is missing a selected coefficient")
    if not isinstance(model_bytes, bytes):
        raise ValueError("selected receipt is missing trusted model bytes")
    verified = _trusted_model_bytes(model, selected_coefficient)
    if verified != model_bytes:
        raise ValueError("selected receipt model evidence changed")
    return verified


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


def _validate_candidate_tables(
    candidates: pd.DataFrame,
    working_points: pd.DataFrame,
    config: DecorrelationConfig,
) -> None:
    if list(candidates.columns) != list(_CANDIDATE_COLUMNS):
        raise ValueError("candidate_results columns do not match the contract")
    expected_candidates = [_candidate_name(value) for value in config.coefficients]
    if (
        len(candidates) != len(expected_candidates)
        or candidates["candidate"].tolist() != expected_candidates
    ):
        raise ValueError("candidate_results rows do not match frozen candidates")
    candidate_coefficients = candidates["coefficient"].to_numpy(dtype=float)
    if not np.array_equal(candidate_coefficients, np.asarray(config.coefficients)):
        raise ValueError("candidate_results coefficients changed")
    _require_finite_columns(
        candidates,
        (
            "coefficient",
            "weighted_oof_auc",
            "maximum_oof_zz_ks",
            "background_score_mass_correlation",
        ),
        "candidate_results",
    )
    if (
        (candidates["weighted_oof_auc"].to_numpy(dtype=float) < 0.0).any()
        or (candidates["weighted_oof_auc"].to_numpy(dtype=float) > 1.0).any()
        or (candidates["maximum_oof_zz_ks"].to_numpy(dtype=float) < 0.0).any()
        or (candidates["maximum_oof_zz_ks"].to_numpy(dtype=float) > 1.0).any()
        or (
            candidates["background_score_mass_correlation"].to_numpy(
                dtype=float
            )
            < -1.0
        ).any()
        or (
            candidates["background_score_mass_correlation"].to_numpy(
                dtype=float
            )
            > 1.0
        ).any()
    ):
        raise ValueError("candidate_results metrics are outside the approved range")
    if any(type(value) not in (bool, np.bool_) for value in candidates["eligible"]):
        raise ValueError("candidate_results eligible values must be booleans")
    if any(not isinstance(value, str) for value in candidates["eligibility_reasons"]):
        raise ValueError("candidate_results eligibility reasons must be strings")

    point_names = tuple(config.working_points)
    expected_point_candidates = [
        candidate
        for candidate in expected_candidates
        for _ in point_names
    ]
    expected_point_names = list(point_names) * len(expected_candidates)
    expected_point_coefficients = np.repeat(
        np.asarray(config.coefficients, dtype=float), len(point_names)
    )
    if (
        list(working_points.columns) != list(_WORKING_POINT_COLUMNS)
        or len(working_points) != len(expected_point_candidates)
        or working_points["candidate"].tolist() != expected_point_candidates
        or working_points["working_point"].tolist() != expected_point_names
        or not np.array_equal(
            working_points["coefficient"].to_numpy(dtype=float),
            expected_point_coefficients,
        )
    ):
        raise ValueError("working_point_metrics rows do not match the contract")
    _require_finite_columns(
        working_points,
        _WORKING_POINT_COLUMNS[1:2] + _WORKING_POINT_COLUMNS[3:],
        "working_point_metrics",
    )
    ranged_point_columns = (
        "threshold",
        "target_background_efficiency",
        "achieved_background_efficiency",
        "signal_efficiency",
        "zz_mass_ks_distance",
    )
    point_values = working_points.loc[
        :, list(ranged_point_columns)
    ].to_numpy(dtype=float)
    if (point_values < 0.0).any() or (point_values > 1.0).any():
        raise ValueError(
            "working_point_metrics values are outside the approved range"
        )
    for candidate_index, candidate in enumerate(expected_candidates):
        rows = working_points.loc[working_points["candidate"] == candidate]
        if any(
            rows.iloc[index]["target_background_efficiency"]
            != config.working_points[name]
            for index, name in enumerate(point_names)
        ):
            raise ValueError("working-point targets change the frozen config")
        maximum_ks = float(rows["zz_mass_ks_distance"].max())
        if maximum_ks != float(
            candidates.iloc[candidate_index]["maximum_oof_zz_ks"]
        ):
            raise ValueError("candidate and working-point KS metrics disagree")
        thresholds = rows["threshold"].to_numpy(dtype=float)
        if any(first > second for first, second in zip(thresholds, thresholds[1:])):
            raise ValueError("working-point thresholds are not monotonic")
        reasons: list[str] = []
        if (
            float(candidates.iloc[candidate_index]["weighted_oof_auc"])
            < config.auc_floor
        ):
            reasons.append("weighted_auc_below_floor")
        for _, row in rows.iterrows():
            if float(row["zz_mass_ks_distance"]) > config.ks_limit:
                reasons.append(
                    f"{row['working_point']}_zz_mass_ks_exceeds_limit"
                )
        if config.require_signal_efficiency_above_background:
            for _, row in rows.iterrows():
                if float(row["signal_efficiency"]) <= float(
                    row["target_background_efficiency"]
                ):
                    reasons.append(
                        f"{row['working_point']}_signal_efficiency_not_above_background"
                    )
        expected_reasons = ",".join(reasons)
        if candidates.iloc[candidate_index]["eligibility_reasons"] != expected_reasons:
            raise ValueError(
                "candidate eligibility reasons do not match the frozen gates"
            )
        eligible = not reasons
        if bool(candidates.iloc[candidate_index]["eligible"]) is not eligible:
            raise ValueError("candidate eligibility contradicts frozen gates")


def _validate_candidate_metrics_from_oof(
    candidates: pd.DataFrame,
    working_points: pd.DataFrame,
    oof_scores: pd.DataFrame,
    config: DecorrelationConfig,
) -> str | None:
    """Recompute every candidate metric and winner from the published OOF table."""
    from .decorrelation_training import (
        evaluate_flatness_candidate,
        select_flatness_candidate,
    )

    recomputed = []
    for coefficient in config.coefficients:
        candidate = _candidate_name(coefficient)
        score_column = f"score_{candidate}"
        audit = oof_scores.loc[:, [*_AUDIT_COLUMNS, score_column]].copy(deep=True)
        result = evaluate_flatness_candidate(
            audit,
            config,
            coefficient=coefficient,
        )
        recomputed.append(result)
        candidate_row = candidates.loc[candidates["candidate"] == candidate].iloc[0]
        expected_candidate_values = {
            "weighted_oof_auc": result.weighted_auc,
            "maximum_oof_zz_ks": max(result.zz_ks_distances.values()),
            "background_score_mass_correlation": (
                result.background_score_mass_correlation
            ),
        }
        for name, expected in expected_candidate_values.items():
            if float(candidate_row[name]) != float(expected):
                raise ValueError(
                    f"candidate_results {name} does not match published OOF scores"
                )
        expected_reasons = ",".join(result.eligibility_reasons)
        if (
            bool(candidate_row["eligible"]) is not (not result.eligibility_reasons)
            or candidate_row["eligibility_reasons"] != expected_reasons
        ):
            raise ValueError(
                "candidate_results eligibility does not match published OOF scores"
            )
        point_rows = working_points.loc[
            working_points["candidate"] == candidate
        ].set_index("working_point")
        for point_name in config.working_points:
            actual = point_rows.loc[point_name]
            expected_point = result.working_points[point_name]
            expected_values = {
                "threshold": expected_point["threshold"],
                "target_background_efficiency": (
                    result.target_background_efficiencies[point_name]
                ),
                "achieved_background_efficiency": (
                    result.achieved_background_efficiencies[point_name]
                ),
                "signal_efficiency": result.signal_efficiencies[point_name],
                "zz_mass_ks_distance": result.zz_ks_distances[point_name],
            }
            for name, expected in expected_values.items():
                if float(actual[name]) != float(expected):
                    raise ValueError(
                        f"working_point_metrics {point_name} {name} does not "
                        "match published OOF scores"
                    )
    selected = select_flatness_candidate(recomputed).selected
    return None if selected is None else _candidate_name(selected.coefficient)


def validate_decorrelation_development_artifacts(
    *,
    candidate_results: pd.DataFrame,
    working_point_metrics: pd.DataFrame,
    oof_scores: pd.DataFrame,
    config: DecorrelationConfig,
    approved_development: pd.DataFrame,
    selected_candidate: str | None,
) -> None:
    """Bind common development artifacts to source rows, folds, and OOF metrics."""
    for name, frame in (
        ("candidate_results", candidate_results),
        ("working_point_metrics", working_point_metrics),
        ("oof_scores", oof_scores),
    ):
        _validate_finite_frame(frame, name)
    _validate_candidate_tables(candidate_results, working_point_metrics, config)
    _validate_oof_scores(oof_scores, config)
    _validate_artifact_rows_against_source(
        oof_scores,
        approved_development,
        allowed_splits={"train", "validation"},
        require_development_fold=True,
    )
    winner = _validate_candidate_metrics_from_oof(
        candidate_results,
        working_point_metrics,
        oof_scores,
        config,
    )
    if selected_candidate != winner:
        raise ValueError("selected candidate does not match published OOF scores")


def _validate_artifact_rows_against_source(
    frame: pd.DataFrame,
    approved_mc: pd.DataFrame,
    *,
    allowed_splits: set[str],
    require_development_fold: bool,
) -> None:
    if not isinstance(approved_mc, pd.DataFrame) or approved_mc.empty:
        raise ValueError("approved source rows must be a non-empty DataFrame")
    _validate_source_row_ids(approved_mc)
    required = {
        "source_row_id",
        "channelNumber",
        "eventNumber",
        "split",
        "label",
        "physical_weight",
        "m4l",
    }
    if not required <= set(approved_mc):
        raise ValueError("approved source rows are missing audit attributes")
    approved = approved_mc.loc[approved_mc["split"].isin(allowed_splits)].copy(
        deep=True
    )
    if approved.empty or set(approved["split"]) != allowed_splits:
        raise ValueError("approved source rows do not contain the required split set")
    artifact_ids = frame["source_row_id"].to_numpy(dtype=np.int64)
    approved_ids = approved["source_row_id"].to_numpy(dtype=np.int64)
    if len(artifact_ids) != len(approved_ids) or set(artifact_ids) != set(
        approved_ids
    ):
        raise ValueError("artifact row set does not match approved source rows")
    artifact_indexed = frame.set_index("source_row_id").sort_index()
    approved_indexed = approved.set_index("source_row_id").sort_index()
    for column in (
        "channelNumber",
        "eventNumber",
        "split",
        "label",
        "physical_weight",
        "m4l",
    ):
        if not artifact_indexed[column].equals(approved_indexed[column]):
            raise ValueError(
                f"artifact {column} values do not match approved source rows"
            )
    if require_development_fold:
        expected_folds = np.asarray(
            [
                development_fold(channel, event)
                for channel, event in zip(
                    approved_indexed["channelNumber"],
                    approved_indexed["eventNumber"],
                    strict=True,
                )
            ],
            dtype=int,
        )
        actual_folds = artifact_indexed["development_fold"].to_numpy(dtype=int)
        if not np.array_equal(actual_folds, expected_folds):
            raise ValueError(
                "artifact development folds do not match approved source rows"
            )


def _validate_oof_scores(frame: pd.DataFrame, config: DecorrelationConfig) -> None:
    score_columns = tuple(
        f"score_{_candidate_name(value)}" for value in config.coefficients
    )
    if list(frame.columns) != [*_AUDIT_COLUMNS, *score_columns] or frame.empty:
        raise ValueError("oof_scores schema does not match the contract")
    _validate_audit_identity(frame, allowed_splits={"train", "validation"})
    _require_finite_columns(
        frame,
        (
            "source_row_id",
            "eventNumber",
            "channelNumber",
            "label",
            "physical_weight",
            "m4l",
            "development_fold",
            *score_columns,
        ),
        "oof_scores",
    )
    folds = frame["development_fold"].to_numpy(dtype=float)
    if (
        not np.equal(folds, np.floor(folds)).all()
        or (folds < 0).any()
        or (folds >= config.folds).any()
    ):
        raise ValueError("oof_scores development folds are invalid")
    _validate_binary_labels(frame, "oof_scores")
    for column in score_columns:
        scores = frame[column].to_numpy(dtype=float)
        if (scores < 0.0).any() or (scores > 1.0).any():
            raise ValueError("oof_scores probabilities are outside [0, 1]")


def _validate_selected_oof_scores(
    frame: pd.DataFrame,
    oof_scores: pd.DataFrame,
    selected_candidate: str,
) -> None:
    if list(frame.columns) != [*_AUDIT_COLUMNS, "oof_score"]:
        raise ValueError("selected_oof_scores schema does not match the contract")
    _validate_audit_identity(frame, allowed_splits={"train", "validation"})
    _require_finite_columns(
        frame,
        (
            "source_row_id",
            "eventNumber",
            "channelNumber",
            "label",
            "physical_weight",
            "m4l",
            "development_fold",
            "oof_score",
        ),
        "selected_oof_scores",
    )
    identity = ["source_row_id"]
    selected_indexed = frame.set_index(identity).sort_index()
    oof_indexed = oof_scores.set_index(identity).sort_index()
    if not selected_indexed.index.equals(oof_indexed.index):
        raise ValueError("selected_oof_scores identities differ from oof_scores")
    for column in _AUDIT_COLUMNS:
        if column in identity:
            continue
        if not selected_indexed[column].equals(oof_indexed[column]):
            raise ValueError("selected_oof_scores audit evidence changed")
    expected_score = f"score_{selected_candidate}"
    if not np.array_equal(
        selected_indexed["oof_score"].to_numpy(dtype=float),
        oof_indexed[expected_score].to_numpy(dtype=float),
    ):
        raise ValueError("selected_oof_scores do not match selected candidate")


def _validate_test_scores(frame: pd.DataFrame) -> None:
    if list(frame.columns) != list(_TEST_SCORE_COLUMNS) or frame.empty:
        raise ValueError("test_scores schema does not match the contract")
    _validate_audit_identity(frame, allowed_splits={"test"})
    _require_finite_columns(
        frame,
        (
            "source_row_id",
            "eventNumber",
            "channelNumber",
            "label",
            "physical_weight",
            "m4l",
            "score",
        ),
        "test_scores",
    )
    _validate_binary_labels(frame, "test_scores")
    scores = frame["score"].to_numpy(dtype=float)
    if (scores < 0.0).any() or (scores > 1.0).any():
        raise ValueError("test_scores probabilities are outside [0, 1]")


def _validate_audit_identity(
    frame: pd.DataFrame, *, allowed_splits: set[str]
) -> None:
    audit_attributes = ["channelNumber", "eventNumber", "split"]
    if frame.loc[:, ["source_row_id", *audit_attributes]].isna().any().any():
        raise ValueError("artifact identity fields must not be missing")
    _validate_source_row_ids(frame)
    if not set(frame["split"]) or not set(frame["split"]) <= allowed_splits:
        raise ValueError("artifact split values do not match the contract")


def _validate_source_row_ids(frame: pd.DataFrame) -> None:
    if "source_row_id" not in frame:
        raise ValueError("artifact identity requires source_row_id")
    try:
        values = frame["source_row_id"].to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("source_row_id must contain integer CSV row ordinals") from error
    if (
        not np.isfinite(values).all()
        or not np.equal(values, np.floor(values)).all()
        or (values < 0).any()
        or frame["source_row_id"].duplicated().any()
    ):
        raise ValueError("source_row_id must contain unique integer CSV row ordinals")


def _validate_binary_labels(frame: pd.DataFrame, name: str) -> None:
    labels = frame["label"].to_numpy(dtype=float)
    if not np.equal(labels, np.floor(labels)).all() or not set(labels) <= {0.0, 1.0}:
        raise ValueError(f"{name} labels must be binary integers")


def _require_finite_columns(
    frame: pd.DataFrame, columns: tuple[str, ...], name: str
) -> None:
    try:
        values = frame.loc[:, list(columns)].to_numpy(dtype=float)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{name} numeric schema is invalid") from error
    if not np.isfinite(values).all():
        raise ValueError(f"{name} numeric content must be finite")


def _validate_selection_semantics(
    selection: Mapping[str, Any],
    config: DecorrelationConfig,
    candidates: pd.DataFrame,
    *,
    selected: bool,
    decision: Mapping[str, Any] | None,
) -> str | None:
    _validate_selection_contract(selection, config)
    candidate = selection["selected_candidate"]
    if selected:
        if (
            selection["status"] != "eligible_candidate_test_reported"
            or not isinstance(candidate, str)
            or candidate not in set(candidates["candidate"])
            or selection["test_opened"] is not True
        ):
            raise ValueError("selection contradicts selected artifact set")
        selected_row = candidates.loc[candidates["candidate"] == candidate].iloc[0]
        if not bool(selected_row["eligible"]):
            raise ValueError("selection names an ineligible candidate")
        eligible = candidates.loc[candidates["eligible"].astype(bool)]
        winner = min(
            eligible.to_dict("records"),
            key=lambda row: (
                -float(row["weighted_oof_auc"]),
                float(row["maximum_oof_zz_ks"]),
                float(row["coefficient"]),
            ),
        )
        if candidate != winner["candidate"]:
            raise ValueError(
                "selection does not name the deterministic eligible winner"
            )
    else:
        if (
            selection["status"] != "no_eligible_candidate"
            or candidate is not None
            or selection["test_opened"] is not False
            or candidates["eligible"].astype(bool).any()
        ):
            raise ValueError("selection contradicts no-selection artifact set")
    if decision is not None and any(
        selection[key] != decision[key]
        for key in ("status", "selected_candidate", "test_opened")
    ):
        raise ValueError("selection artifact contradicts manifest decision")
    return candidate


def _validate_test_metrics(
    value: Any,
    config: DecorrelationConfig,
    *,
    test_scores: pd.DataFrame,
    selected_working_points: pd.DataFrame,
) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "weighted_auc",
        "background_score_mass_correlation",
        "working_points",
        "zz_ks_distances",
    }:
        raise ValueError("test_metrics schema does not match the contract")
    if value["schema_version"] != "1.0":
        raise ValueError("test_metrics schema_version must be 1.0")
    _require_finite_numbers(
        (value["weighted_auc"], value["background_score_mass_correlation"]),
        "test_metrics",
    )
    if not 0.0 <= float(value["weighted_auc"]) <= 1.0:
        raise ValueError("test_metrics weighted_auc is outside the approved range")
    if not -1.0 <= float(value["background_score_mass_correlation"]) <= 1.0:
        raise ValueError(
            "test_metrics background correlation is outside the approved range"
        )
    points = value["working_points"]
    distances = value["zz_ks_distances"]
    if (
        not isinstance(points, Mapping)
        or set(points) != set(config.working_points)
        or not isinstance(distances, Mapping)
        or set(distances) != set(config.working_points)
    ):
        raise ValueError("test_metrics working points do not match the contract")
    for name in config.working_points:
        point = points[name]
        if not isinstance(point, Mapping) or set(point) != {
            "threshold",
            "target_background_efficiency",
            "achieved_background_efficiency",
            "signal_efficiency",
        }:
            raise ValueError("test_metrics working-point schema is invalid")
        _require_finite_numbers(tuple(point.values()), "test_metrics")
        if point["target_background_efficiency"] != config.working_points[name]:
            raise ValueError("test_metrics changes a frozen working-point target")
        if any(
            not 0.0 <= float(point[field]) <= 1.0
            for field in (
                "threshold",
                "target_background_efficiency",
                "achieved_background_efficiency",
                "signal_efficiency",
            )
        ):
            raise ValueError(
                "test_metrics working-point value is outside the approved range"
            )
        distance = distances[name]
        if distance is not None:
            _require_finite_numbers((distance,), "test_metrics")
            if not 0.0 <= float(distance) <= 1.0:
                raise ValueError(
                    "test_metrics KS distance is outside the approved range"
                )

    indexed_points = selected_working_points.set_index("working_point")
    if set(indexed_points.index) != set(config.working_points):
        raise ValueError("selected OOF working points are incomplete")
    labels = test_scores["label"].to_numpy(dtype=int)
    scores = test_scores["score"].to_numpy(dtype=float)
    weights = test_scores["physical_weight"].to_numpy(dtype=float)
    masses = test_scores["m4l"].to_numpy(dtype=float)
    if set(labels) != {0, 1}:
        raise ValueError("test_scores must contain both binary classes")
    absolute = np.abs(weights)
    expected_auc = float(
        roc_auc_score(labels, scores, sample_weight=absolute)
    )
    background = labels == 0
    expected_correlation = weighted_pearson(
        scores[background], masses[background], weights[background]
    )
    _require_exact_metric(
        value["weighted_auc"], expected_auc, "weighted_auc"
    )
    _require_exact_metric(
        value["background_score_mass_correlation"],
        expected_correlation,
        "background_score_mass_correlation",
    )
    for name in config.working_points:
        frozen = indexed_points.loc[name]
        point = points[name]
        frozen_threshold = float(frozen["threshold"])
        if float(point["threshold"]) != frozen_threshold:
            raise ValueError(
                "test_metrics changes a frozen selected OOF threshold"
            )
        if float(point["target_background_efficiency"]) != float(
            frozen["target_background_efficiency"]
        ):
            raise ValueError(
                "test_metrics changes a frozen selected OOF target"
            )
        selected_mask = scores >= frozen_threshold
        expected_background = _absolute_efficiency(
            background, selected_mask, weights
        )
        expected_signal = _absolute_efficiency(
            labels == 1, selected_mask, weights
        )
        _require_exact_metric(
            point["achieved_background_efficiency"],
            expected_background,
            f"{name} achieved_background_efficiency",
        )
        _require_exact_metric(
            point["signal_efficiency"],
            expected_signal,
            f"{name} signal_efficiency",
        )
        selected_background = background & selected_mask
        expected_distance = (
            None
            if not selected_background.any()
            else weighted_ks_distance(
                masses[background],
                masses[selected_background],
                weights[background],
                weights[selected_background],
            )
        )
        actual_distance = distances[name]
        if expected_distance is None:
            if actual_distance is not None:
                raise ValueError(
                    f"test_metrics {name} KS distance does not match test_scores"
                )
        elif actual_distance is None:
            raise ValueError(
                f"test_metrics {name} KS distance does not match test_scores"
            )
        else:
            _require_exact_metric(
                actual_distance,
                expected_distance,
                f"{name} zz_ks_distance",
            )


def _absolute_efficiency(
    class_mask: np.ndarray,
    selected_mask: np.ndarray,
    weights: np.ndarray,
) -> float:
    denominator = float(np.abs(weights[class_mask]).sum())
    if denominator <= 0.0:
        raise ValueError("test_scores class weight must be positive")
    return float(
        np.abs(weights[class_mask & selected_mask]).sum() / denominator
    )


def _require_exact_metric(actual: Any, expected: Any, name: str) -> None:
    if float(actual) != float(expected):
        raise ValueError(f"test_metrics {name} does not match test_scores")


def _require_finite_numbers(values: tuple[Any, ...], name: str) -> None:
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not np.isfinite(float(value))
        for value in values
    ):
        raise ValueError(f"{name} numeric content must be finite")


def _validate_png_bytes(payload: bytes, name: str) -> None:
    if not isinstance(payload, bytes) or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"plot output is not a PNG: {name}")
    try:
        from PIL import Image

        with Image.open(io.BytesIO(payload)) as image:
            if image.format != "PNG":
                raise ValueError(f"plot output is not a PNG: {name}")
            image.verify()
    except Exception as error:
        raise ValueError(f"plot output is not a decodable PNG: {name}") from error


def _read_csv_artifact(
    descriptor: int, name: str, *, compression: str | None = None
) -> pd.DataFrame:
    payload, _ = _read_entry_bytes(descriptor, name)
    try:
        return pd.read_csv(
            io.BytesIO(payload),
            compression=compression,
            keep_default_na=False,
            float_precision="round_trip",
        )
    except Exception as error:
        raise ValueError(f"decorrelation CSV is invalid: {name}") from error


def _read_json_artifact(descriptor: int, name: str) -> Mapping[str, Any]:
    payload, _ = _read_entry_bytes(descriptor, name)
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"decorrelation JSON is invalid: {name}") from error
    if not isinstance(value, Mapping):
        raise ValueError(f"decorrelation JSON must contain an object: {name}")
    return value


def _validate_on_disk_artifacts(
    descriptors: Mapping[str, int],
    config: DecorrelationConfig,
    approved_mc: pd.DataFrame,
    *,
    selected: bool,
    decision: Mapping[str, Any],
    trusted_model_sha256: str | None,
) -> None:
    candidates = _read_csv_artifact(
        descriptors["artifacts"], "candidate_results.csv"
    )
    working_points = _read_csv_artifact(
        descriptors["artifacts"], "working_point_metrics.csv"
    )
    _validate_candidate_tables(candidates, working_points, config)
    oof_scores = _read_csv_artifact(
        descriptors["predictions"], "oof_scores.csv.gz", compression="gzip"
    )
    _validate_oof_scores(oof_scores, config)
    _validate_artifact_rows_against_source(
        oof_scores,
        approved_mc,
        allowed_splits={"train", "validation"},
        require_development_fold=True,
    )
    oof_winner = _validate_candidate_metrics_from_oof(
        candidates,
        working_points,
        oof_scores,
        config,
    )
    selection = _read_json_artifact(descriptors["artifacts"], "selection.json")
    selected_candidate = _validate_selection_semantics(
        selection,
        config,
        candidates,
        selected=selected,
        decision=decision,
    )
    if selected_candidate != oof_winner:
        raise ValueError("selection does not match the winner recomputed from OOF scores")
    plot_names = ["candidate_tradeoff.png", "working_point_ks.png"]
    if selected:
        plot_names.append("selected_mass_sculpting.png")
    for name in plot_names:
        payload, _ = _read_entry_bytes(descriptors["plots"], name)
        _validate_png_bytes(payload, name)
    if not selected:
        if trusted_model_sha256 is not None:
            raise ValueError("no-selection publication contains model evidence")
        return
    assert selected_candidate is not None
    selected_oof = _read_csv_artifact(
        descriptors["predictions"],
        "selected_oof_scores.csv.gz",
        compression="gzip",
    )
    test_scores = _read_csv_artifact(
        descriptors["predictions"], "test_scores.csv.gz", compression="gzip"
    )
    _validate_selected_oof_scores(
        selected_oof, oof_scores, selected_candidate
    )
    _validate_test_scores(test_scores)
    _validate_artifact_rows_against_source(
        selected_oof,
        approved_mc,
        allowed_splits={"train", "validation"},
        require_development_fold=True,
    )
    _validate_artifact_rows_against_source(
        test_scores,
        approved_mc,
        allowed_splits={"test"},
        require_development_fold=False,
    )
    selected_points = working_points.loc[
        working_points["candidate"] == selected_candidate
    ]
    _validate_test_metrics(
        _read_json_artifact(descriptors["artifacts"], "test_metrics.json"),
        config,
        test_scores=test_scores,
        selected_working_points=selected_points,
    )
    model_payload, _ = _read_entry_bytes(
        descriptors["model"], "flatness_model.pkl"
    )
    selected_coefficient = decision.get("selected_coefficient")
    if (
        type(selected_coefficient) is not float
        or selected_coefficient not in config.coefficients
    ):
        raise ValueError("selected model coefficient is not approved")
    _validate_model_pickle_semantics(model_payload, selected_coefficient)
    if (
        trusted_model_sha256 is not None
        and (
            not isinstance(trusted_model_sha256, str)
            or hashlib.sha256(model_payload).hexdigest()
            != trusted_model_sha256
        )
    ):
        raise ValueError("published model differs from writer-bound model evidence")


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
        trusted_sources = _independently_resolve_sources(sources)
        approved_mc = _load_approved_mc_frame(trusted_sources)
        _validate_software(software)
        decision = _decision_from_outcome(outcome, trusted_sources.config)
        verified_model_bytes = _validate_receipt_evidence(
            layout,
            receipt,
            selected_coefficient=decision["selected_coefficient"],
        )
        verified_model_sha256 = (
            None
            if verified_model_bytes is None
            else hashlib.sha256(verified_model_bytes).hexdigest()
        )
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
            descriptors["artifacts"], decision, trusted_sources.config
        )
        outputs = _assert_output_receipt(layout, descriptors, receipt)
        _validate_on_disk_artifacts(
            descriptors,
            trusted_sources.config,
            approved_mc,
            selected=receipt.selected,
            decision=decision,
            trusted_model_sha256=verified_model_sha256,
        )
        manifest = {
            "schema_version": "1.0",
            "status": "complete",
            "decision": decision,
            "software": dict(software),
            "sources": _source_manifest_records(trusted_sources),
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
            assert_decorrelation_sources_unchanged(trusted_sources)
            _assert_staged_manifest_unchanged(
                descriptors["artifacts"],
                staged_manifest,
                staged_descriptor,
                staged_identity,
                serialized,
            )
            if _assert_output_receipt(layout, descriptors, receipt) != outputs:
                raise RuntimeError("decorrelation output receipt changed")
            _validate_on_disk_artifacts(
                descriptors,
                trusted_sources.config,
                approved_mc,
                selected=receipt.selected,
                decision=decision,
                trusted_model_sha256=verified_model_sha256,
            )
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
    if sources.records["study_config"].path != _STUDY_CONFIG_PATH:
        raise ValueError(
            "decorrelation config receipt does not use the canonical project study config"
        )
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


def _independently_resolve_sources(
    sources: DecorrelationSources,
) -> DecorrelationSources:
    _validate_source_inventory(sources)
    strict_config = _load_config_bytes(sources.config_bytes)
    trusted = resolve_decorrelation_sources(
        input_run=strict_config.input_run,
        config_path=_STUDY_CONFIG_PATH,
    )
    if (
        sources.config != trusted.config
        or sources.config_bytes != trusted.config_bytes
        or sources.training_input != trusted.training_input
        or dict(sources.records) != dict(trusted.records)
    ):
        raise ValueError(
            "decorrelation capability differs from independently resolved sources"
        )
    return trusted


def _load_approved_mc_frame(sources: DecorrelationSources) -> pd.DataFrame:
    """Load the exact hash-bound MC table and attach stable CSV row ordinals."""
    _validate_source_inventory(sources)
    frame = bind_source_row_ids(load_training_mc_frame(sources.training_input))
    validate_mc_frame(frame)
    return frame


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


def _receipt_content_digest(
    *,
    run_identity: tuple[int, int],
    selected: bool,
    selected_coefficient: float | None,
    outputs: Mapping[str, Mapping[str, Any]],
    model_bytes: bytes | None,
) -> str:
    if (
        not isinstance(run_identity, tuple)
        or len(run_identity) != 2
        or any(type(value) is not int for value in run_identity)
        or type(selected) is not bool
        or not isinstance(outputs, Mapping)
        or (model_bytes is not None and not isinstance(model_bytes, bytes))
    ):
        raise ValueError("artifact receipt content evidence is invalid")
    normalized_outputs = {
        relative: dict(record)
        for relative, record in sorted(outputs.items())
        if isinstance(relative, str) and isinstance(record, Mapping)
    }
    if len(normalized_outputs) != len(outputs):
        raise ValueError("artifact receipt output evidence is invalid")
    evidence = _json_bytes(
        {
            "schema_version": "1.0",
            "run_identity": list(run_identity),
            "selected": selected,
            "selected_coefficient": selected_coefficient,
            "outputs": normalized_outputs,
            "model_sha256": (
                None
                if model_bytes is None
                else hashlib.sha256(model_bytes).hexdigest()
            ),
        }
    )
    return hashlib.sha256(
        b"decorrelation-artifact-receipt-v1\x00" + evidence
    ).hexdigest()


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
            study_config = sources.get("study_config")
            if (
                not isinstance(study_config, Mapping)
                or study_config.get("path") != str(_STUDY_CONFIG_PATH)
            ):
                return False
            resolved_sources = resolve_decorrelation_sources(
                input_run=config.input_run,
                config_path=_STUDY_CONFIG_PATH,
            )
            _validate_source_inventory(resolved_sources)
            assert_decorrelation_sources_unchanged(resolved_sources)
            approved_mc = _load_approved_mc_frame(resolved_sources)
            if (
                resolved_sources.config_bytes != config_bytes
                or dict(sources) != _source_manifest_records(resolved_sources)
            ):
                return False
            _validate_on_disk_artifacts(
                descriptors,
                config,
                approved_mc,
                selected=selected,
                decision=decision,
                trusted_model_sha256=None,
            )
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
