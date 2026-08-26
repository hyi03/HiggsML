"""Sealed source binding, identity reconstruction, and publication for R2."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path
import stat
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd
import yaml

from . import angular5_enrichment as _publication
from . import angular5_enrichment_run as _binding
from . import full_training_run as _safety
from .angular5_enrichment_run import Angular5OutputLayout, Angular5SourceReceipt
from .angular5_identity import (
    SOURCE_IDENTITY,
    IdentityOutcome,
    build_source_identity_baseline,
)
from .features import build_candidate_features
from .input_profiles import resolve_input_profile
from .io import iter_events, validate_channel_numbers
from .selection import SelectionConfig, select_event
from .split import event_split
from .weights import MCNormalization, physical_event_weight, training_weights


TABLE_NAME = "mc_events_source_identity.csv.gz"
IDENTITY_NAME = "identity_validation.json"
MANIFEST_NAME = "run_manifest.json"
_FROZEN_OUTPUT_RUN = "runs/angular5-identity-mc-363490-2026-08-26-r2"
_SOURCE_RELATIVE_PATHS = {
    "identity_config": "config/angular5_identity_mc_dsid363490_r2.yaml",
    "frozen_config": "config/dsid363490.yaml",
    "task4a_manifest": (
        "runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json"
    ),
    "task4a_mc": (
        "runs/full-baseline-363490-2026-08-11-r2/processed/mc_events.csv.gz"
    ),
    "higgs_root": "data/raw/higgs.root",
    "zz_root": "data/raw/zz_363490.root",
}
_EXPECTED_SOURCE_HASHES = {
    "frozen_config": "0282cfa965228e036f4ada3c010bd7d40b1b14e56c2aa33551784683237cd320",
    "task4a_manifest": "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8",
    "task4a_mc": "1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e",
    "higgs_root": "5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0",
    "zz_root": "76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07",
}
_APPROVED_ARTIFACTS = [
    "config.yaml",
    f"processed/{TABLE_NAME}",
    f"artifacts/{IDENTITY_NAME}",
    f"artifacts/{MANIFEST_NAME}",
]


def _sample_config(
    *,
    source_sample: str,
    path: str,
    sha256: str,
    channel: int,
    label: int,
    profile: str,
    normalization: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    sample: dict[str, Any] = {
        "source_sample": source_sample,
        "path": path,
        "sha256": sha256,
        "channel_numbers": [channel],
        "label": label,
        "input_profile": profile,
    }
    if normalization is not None:
        sample["normalization"] = dict(normalization)
    return sample


_EXPECTED_CONFIG = {
    "schema_version": "1.0",
    "output_run": _FROZEN_OUTPUT_RUN,
    "frozen_reference": {
        "path": _SOURCE_RELATIVE_PATHS["frozen_config"],
        "sha256": _EXPECTED_SOURCE_HASHES["frozen_config"],
    },
    "authoritative_mc": {
        "manifest_path": _SOURCE_RELATIVE_PATHS["task4a_manifest"],
        "manifest_sha256": _EXPECTED_SOURCE_HASHES["task4a_manifest"],
        "table_path": _SOURCE_RELATIVE_PATHS["task4a_mc"],
        "table_sha256": _EXPECTED_SOURCE_HASHES["task4a_mc"],
    },
    "tree_name": "analysis",
    "momentum_unit": "GeV",
    "entry_stop": None,
    "chunk_size_events": 50000,
    "luminosity_pb": 10000.0,
    "samples": {
        "higgs": _sample_config(
            source_sample="higgs_345060",
            path=_SOURCE_RELATIVE_PATHS["higgs_root"],
            sha256=_EXPECTED_SOURCE_HASHES["higgs_root"],
            channel=345060,
            label=1,
            profile="release22",
        ),
        "zz": _sample_config(
            source_sample="zz_363490",
            path=_SOURCE_RELATIVE_PATHS["zz_root"],
            sha256=_EXPECTED_SOURCE_HASHES["zz_root"],
            channel=363490,
            label=0,
            profile="open_data_2020",
            normalization={
                "source": "official_metadata",
                "xsec_pb": 1.2564,
                "k_factor": 1.0,
                "filter_efficiency": 1.0,
                "sum_of_weights": 7538705.808,
            },
        ),
    },
    "selection": deepcopy(_binding._EXPECTED_SELECTION),
    "artifacts": _APPROVED_ARTIFACTS,
}


@dataclass(frozen=True)
class IdentityConfig:
    schema_version: str
    output_run: str
    frozen_reference: Mapping[str, str]
    authoritative_mc: Mapping[str, str]
    tree_name: str
    momentum_unit: str
    entry_stop: None
    chunk_size_events: int
    luminosity_pb: float
    samples: Mapping[str, Mapping[str, Any]]
    selection: Mapping[str, Any]
    artifacts: tuple[str, ...]


@dataclass(frozen=True)
class IdentitySources:
    config: IdentityConfig
    config_bytes: bytes
    project_root: Path
    receipts: Mapping[str, Angular5SourceReceipt]


def _load_config_bytes(payload: bytes) -> IdentityConfig:
    try:
        raw = yaml.load(payload, Loader=_binding._UniqueKeySafeLoader)
    except _binding._DuplicateKeyError as error:
        raise ValueError("Angular5 identity config contains a duplicate mapping key") from error
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ValueError("Angular5 identity config is not valid YAML") from error
    if not _binding._exact_value(raw, _EXPECTED_CONFIG):
        raise ValueError("Angular5 identity config does not match the exact sealed schema")
    samples: dict[str, Mapping[str, Any]] = {}
    for key in ("higgs", "zz"):
        sample = dict(raw["samples"][key])
        sample["channel_numbers"] = tuple(sample["channel_numbers"])
        if "normalization" in sample:
            sample["normalization"] = MappingProxyType(dict(sample["normalization"]))
        samples[key] = MappingProxyType(sample)
    return IdentityConfig(
        schema_version="1.0",
        output_run=_FROZEN_OUTPUT_RUN,
        frozen_reference=MappingProxyType(dict(raw["frozen_reference"])),
        authoritative_mc=MappingProxyType(dict(raw["authoritative_mc"])),
        tree_name="analysis",
        momentum_unit="GeV",
        entry_stop=None,
        chunk_size_events=50000,
        luminosity_pb=10000.0,
        samples=MappingProxyType(samples),
        selection=_binding._deep_freeze(deepcopy(raw["selection"])),
        artifacts=tuple(_APPROVED_ARTIFACTS),
    )


def load_identity_config(path: str | Path) -> IdentityConfig:
    try:
        payload = Path(path).read_bytes()
    except OSError as error:
        raise ValueError("Angular5 identity config is not valid YAML") from error
    return _load_config_bytes(payload)


def _rename_receipt(
    receipt: Angular5SourceReceipt, name: str
) -> Angular5SourceReceipt:
    return Angular5SourceReceipt(
        name=name,
        path=receipt.path,
        device=receipt.device,
        inode=receipt.inode,
        size_bytes=receipt.size_bytes,
        sha256=receipt.sha256,
    )


def _bind_source(name: str, path: Path) -> tuple[Angular5SourceReceipt, bytes]:
    binding_name = "enrichment_config" if name == "identity_config" else name
    receipt, payload = _binding._bind_regular(binding_name, path)
    return _rename_receipt(receipt, name), payload


def resolve_identity_sources(
    *, project_root: str | Path, config_path: str | Path
) -> IdentitySources:
    root = Path(project_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Angular5 identity project root is not a directory")
    expected_config = root / _SOURCE_RELATIVE_PATHS["identity_config"]
    if Path(os.path.abspath(config_path)) != expected_config:
        raise ValueError("Angular5 identity config must use the exact frozen path")
    receipts: dict[str, Angular5SourceReceipt] = {}
    config_bytes = b""
    for name, relative in _SOURCE_RELATIVE_PATHS.items():
        receipt, snapshot = _bind_source(name, root / relative)
        receipts[name] = receipt
        if name == "identity_config":
            config_bytes = snapshot
    config = _load_config_bytes(config_bytes)
    for name, expected in _EXPECTED_SOURCE_HASHES.items():
        if receipts[name].sha256 != expected:
            raise ValueError(f"Angular5 identity source SHA-256 mismatch: {name}")
    return IdentitySources(
        config=config,
        config_bytes=config_bytes,
        project_root=root,
        receipts=MappingProxyType(dict(receipts)),
    )


def assert_identity_sources_unchanged(sources: IdentitySources) -> None:
    if not isinstance(sources, IdentitySources):
        raise TypeError("sources must be IdentitySources")
    for name, original in sources.receipts.items():
        try:
            current, _ = _bind_source(name, original.path)
        except (FileNotFoundError, ValueError, OSError) as error:
            raise RuntimeError(
                f"Angular5 identity source changed before publication: {name}"
            ) from error
        if current != original:
            raise RuntimeError(
                f"Angular5 identity source changed before publication: {name}"
            )


def claim_identity_output(
    *,
    sources: IdentitySources,
    project_root: str | Path,
    working_directory: str | Path,
    run_dir: str | Path,
) -> Angular5OutputLayout:
    if not isinstance(sources, IdentitySources):
        raise TypeError("sources must be IdentitySources")
    root = Path(project_root).resolve(strict=True)
    if root != sources.project_root:
        raise ValueError("Angular5 identity output project does not match sources")
    logical = Path(run_dir)
    unresolved = (
        logical
        if logical.is_absolute()
        else Path(working_directory).resolve() / logical
    )
    target = _binding._absolute_without_symlinks(unresolved, allow_final=True)
    protected = [
        root / name
        for name in (
            "data",
            "outputs",
            "config",
            "docs",
            "src",
            "scripts",
            "tests",
            ".git",
            ".venv",
        )
    ]
    protected.extend(receipt.path for receipt in sources.receipts.values())
    protected.append(root / "runs/full-baseline-363490-2026-08-11-r2")
    if target == root or any(_binding._is_within(target, path) for path in protected):
        raise ValueError("Angular5 identity output path is inside a protected path")
    if target != root / sources.config.output_run:
        raise ValueError("Angular5 identity run directory does not match frozen output path")
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Angular5 identity run directory already exists: {logical}")
    assert_identity_sources_unchanged(sources)

    parent = _binding._open_claim_parent(target)
    root_descriptor: int | None = None
    try:
        try:
            os.mkdir(target.name, dir_fd=parent)
        except FileExistsError as error:
            raise FileExistsError(
                f"Angular5 identity run directory already exists: {logical}"
            ) from error
        root_descriptor = os.open(target.name, _binding._directory_flags(), dir_fd=parent)
        identities = {".": _binding._identity(root_descriptor)}
        for name in ("processed", "artifacts"):
            os.mkdir(name, dir_fd=root_descriptor)
            child = os.open(name, _binding._directory_flags(), dir_fd=root_descriptor)
            try:
                identities[name] = _binding._identity(child)
            finally:
                os.close(child)
        return Angular5OutputLayout(
            run_dir=target,
            config_snapshot=target / "config.yaml",
            processed_dir=target / "processed",
            artifacts_dir=target / "artifacts",
            directory_identities=MappingProxyType(identities),
        )
    finally:
        if root_descriptor is not None:
            os.close(root_descriptor)
        os.close(parent)


def _normalization_override(sample: Mapping[str, Any]) -> MCNormalization | None:
    raw = sample.get("normalization")
    if raw is None:
        return None
    return MCNormalization(
        raw["xsec_pb"],
        raw["k_factor"],
        raw["filter_efficiency"],
        raw["sum_of_weights"],
    )


def _reconstruct_sample(
    sources: IdentitySources,
    *,
    sample_key: str,
    selection: SelectionConfig,
    root_snapshot,
) -> pd.DataFrame:
    sample = sources.config.samples[sample_key]
    profile = resolve_input_profile(sample["input_profile"])
    normalization = _normalization_override(sample)
    observed_channels: set[int] = set()
    rows: list[dict[str, Any]] = []
    source_entries: list[int] = []
    for event in iter_events(
        root_snapshot,
        profile.tree_name,
        is_data=False,
        entry_stop=sources.config.entry_stop,
        chunk_size_events=sources.config.chunk_size_events,
        profile=profile,
        extra_canonical_branches=selection.required_canonical_branches,
        include_source_entry=True,
    ):
        event["source_sample"] = sample["source_sample"]
        channel = int(event["channelNumber"])
        observed_channels.add(channel)
        if normalization is None:
            normalization = MCNormalization.from_event(event)
        weight = physical_event_weight(
            event,
            sources.config.luminosity_pb,
            normalization=normalization,
            require_event_normalization=profile.normalization_in_events,
        )
        selected = select_event(event, selection, profile.momentum_unit)
        if not selected.accepted:
            continue
        if selected.candidate is None:
            raise ValueError("selected identity event has no reconstructed candidate")
        row = build_candidate_features(event, selected.candidate)
        if sample.get("normalization") is not None:
            row.update(
                xsec=normalization.xsec_pb,
                kfac=normalization.k_factor,
                filteff=normalization.filter_efficiency,
                sum_of_weights=normalization.sum_of_weights,
            )
        row["physical_weight"] = weight
        rows.append(row)
        source_entries.append(int(event["source_entry"]))
    if normalization is None:
        raise ValueError(f"{sample_key}: no MC events were read")
    validate_channel_numbers(
        observed_channels,
        sample["channel_numbers"],
        sample["source_sample"],
    )
    if not rows:
        raise ValueError(f"{sample_key}: no events passed the frozen selection")
    frame = pd.DataFrame(rows)
    frame["label"] = int(sample["label"])
    frame["train_weight"] = training_weights(frame["physical_weight"])
    frame["split"] = [
        event_split(event, channel)
        for event, channel in zip(frame["eventNumber"], frame["channelNumber"])
    ]
    frame["source_sample"] = sample["source_sample"]
    frame["source_entry"] = source_entries
    return frame


def _source_binding(sources: IdentitySources) -> tuple[tuple[Any, ...], ...]:
    records = tuple(
        (
            name,
            str(receipt.path),
            receipt.device,
            receipt.inode,
            receipt.size_bytes,
            receipt.sha256,
        )
        for name, receipt in sorted(sources.receipts.items())
    )
    return records + (("config_bytes", hashlib.sha256(sources.config_bytes).hexdigest()),)


_RUN_OUTCOME_TOKEN = object()


@dataclass(frozen=True, init=False)
class IdentityRunOutcome:
    _identity: IdentityOutcome
    _source_binding: tuple[tuple[Any, ...], ...]

    def __new__(
        cls,
        token: object = None,
        identity: IdentityOutcome | None = None,
        source_binding: tuple[tuple[Any, ...], ...] | None = None,
    ):
        if token is not _RUN_OUTCOME_TOKEN or identity is None or source_binding is None:
            raise TypeError("IdentityRunOutcome is returned by build_identity_mc")
        return super().__new__(cls)

    def __init__(
        self,
        token: object,
        identity: IdentityOutcome,
        source_binding: tuple[tuple[Any, ...], ...],
    ) -> None:
        object.__setattr__(self, "_identity", identity)
        object.__setattr__(self, "_source_binding", source_binding)

    @property
    def frame(self) -> pd.DataFrame:
        return self._identity.frame

    @property
    def evidence(self) -> Mapping[str, Any]:
        return self._identity.evidence

    @property
    def table_payload(self) -> bytes:
        return self._identity.table_payload


def build_identity_mc(sources: IdentitySources) -> IdentityRunOutcome:
    if not isinstance(sources, IdentitySources):
        raise TypeError("sources must be IdentitySources")
    assert_identity_sources_unchanged(sources)
    authoritative = _publication._read_receipt_snapshot(
        sources.receipts["task4a_mc"]
    )
    selection = SelectionConfig.from_mapping(sources.config.selection)
    reconstructed: dict[str, pd.DataFrame] = {}
    for sample_key in ("higgs", "zz"):
        with _publication._receipt_file_snapshot(
            sources.receipts[f"{sample_key}_root"]
        ) as root_snapshot:
            sample = _reconstruct_sample(
                sources,
                sample_key=sample_key,
                selection=selection,
                root_snapshot=root_snapshot,
            )
        reconstructed[sources.config.samples[sample_key]["source_sample"]] = sample
    identity = build_source_identity_baseline(authoritative, reconstructed)
    assert_identity_sources_unchanged(sources)
    return IdentityRunOutcome(_RUN_OUTCOME_TOKEN, identity, _source_binding(sources))


_RECEIPT_TOKEN = object()


@dataclass(frozen=True, init=False)
class IdentityArtifactReceipt:
    _run_identity: tuple[int, int]
    _records: Mapping[str, Mapping[str, Any]]
    _identities: Mapping[str, tuple[int, int]]

    def __new__(
        cls,
        token: object = None,
        run_identity: tuple[int, int] | None = None,
        records: Mapping[str, Mapping[str, Any]] | None = None,
        identities: Mapping[str, tuple[int, int]] | None = None,
    ):
        if (
            token is not _RECEIPT_TOKEN
            or run_identity is None
            or records is None
            or identities is None
        ):
            raise TypeError("IdentityArtifactReceipt is returned by write_identity_artifacts")
        return super().__new__(cls)

    def __init__(
        self,
        token: object,
        run_identity: tuple[int, int],
        records: Mapping[str, Mapping[str, Any]],
        identities: Mapping[str, tuple[int, int]],
    ) -> None:
        object.__setattr__(self, "_run_identity", run_identity)
        object.__setattr__(self, "_records", records)
        object.__setattr__(self, "_identities", identities)


def _open_claimed(layout: Angular5OutputLayout) -> dict[str, int]:
    expected = layout.directory_identities
    if expected is None:
        raise RuntimeError("Angular5 identity output has not been claimed")
    descriptors: dict[str, int] = {}
    try:
        root = _safety._open_absolute_directory_no_follow(layout.run_dir)
        descriptors["."] = root
        if _safety._identity(root) != expected.get("."):
            raise ValueError("Angular5 identity run ownership changed")
        for name in ("processed", "artifacts"):
            child = os.open(name, _safety._directory_flags(), dir_fd=root)
            descriptors[name] = child
            if _safety._identity(child) != expected.get(name):
                raise ValueError(f"Angular5 identity child ownership changed: {name}")
        return descriptors
    except Exception:
        _publication._close_descriptors(descriptors)
        raise


def _assert_layout(
    descriptors: Mapping[str, int], *, state: str, terminal_lock: bool = False
) -> None:
    root_expected = {"processed", "artifacts"}
    if state != "empty":
        root_expected.add("config.yaml")
    if terminal_lock:
        root_expected.add(".terminal.lock")
    if set(os.listdir(descriptors["."])) != root_expected:
        raise FileExistsError("Angular5 identity run root contract mismatch")
    processed_expected = set() if state == "empty" else {TABLE_NAME}
    artifacts_expected = {
        "empty": set(),
        "artifacts": {IDENTITY_NAME},
        "complete": {IDENTITY_NAME, MANIFEST_NAME},
    }[state]
    if set(os.listdir(descriptors["processed"])) != processed_expected:
        raise FileExistsError("Angular5 identity processed contract mismatch")
    if set(os.listdir(descriptors["artifacts"])) != artifacts_expected:
        raise FileExistsError("Angular5 identity artifact contract mismatch")


def _output_records(
    layout: Angular5OutputLayout, descriptors: Mapping[str, int]
) -> tuple[dict[str, dict[str, Any]], dict[str, tuple[int, int]]]:
    mapping = {
        "config.yaml": (".", "config.yaml", False),
        f"processed/{TABLE_NAME}": ("processed", TABLE_NAME, True),
        f"artifacts/{IDENTITY_NAME}": ("artifacts", IDENTITY_NAME, False),
    }
    records: dict[str, dict[str, Any]] = {}
    identities: dict[str, tuple[int, int]] = {}
    for relative, (directory, name, csv_rows) in mapping.items():
        payload, identity = _publication._read_regular(descriptors[directory], name)
        record: dict[str, Any] = {
            "path": str(layout.run_dir / relative),
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        if csv_rows:
            try:
                record["row_count"] = len(
                    pd.read_csv(io.BytesIO(payload), compression="gzip")
                )
            except Exception as error:
                raise ValueError("published source-identity CSV is invalid") from error
        records[relative] = record
        identities[relative] = identity
    return records, identities


def _source_records(sources: IdentitySources) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "path": str(receipt.path),
            "device": receipt.device,
            "inode": receipt.inode,
            "size_bytes": receipt.size_bytes,
            "sha256": receipt.sha256,
        }
        for name, receipt in sources.receipts.items()
    }


def _open_verified_root(layout: Angular5OutputLayout) -> int:
    if layout.directory_identities is None:
        raise RuntimeError("Angular5 identity output has not been claimed")
    root = _safety._open_absolute_directory_no_follow(layout.run_dir)
    if _safety._identity(root) != layout.directory_identities.get("."):
        os.close(root)
        raise ValueError("Angular5 identity run ownership changed")
    return root


def _manifest_present(root: int) -> bool:
    try:
        artifacts = os.open("artifacts", _safety._directory_flags(), dir_fd=root)
    except OSError:
        return False
    try:
        return _safety._entry_exists(artifacts, MANIFEST_NAME)
    finally:
        os.close(artifacts)


def _install_failure_locked(root: int, run_dir: Path, error: BaseException) -> None:
    if _manifest_present(root):
        return
    try:
        os.mkdir(".terminal.failed", dir_fd=root)
    except FileExistsError:
        pass
    if _safety._entry_exists(root, "failure.json"):
        return
    try:
        _publication._atomic_publish_bytes(
            root,
            run_dir,
            "failure.json",
            _publication._json_bytes(
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "message": str(error),
                }
            ),
        )
    except BaseException:
        pass


def record_identity_failure(layout: Angular5OutputLayout, error: BaseException) -> None:
    try:
        root = _open_verified_root(layout)
    except BaseException:
        return
    locked = False
    try:
        _safety._terminal_lock_acquire(root)
        locked = True
        _install_failure_locked(root, layout.run_dir, error)
    except BaseException:
        pass
    finally:
        if locked:
            _safety._terminal_lock_release(root)
        os.close(root)


def _validate_outcome(
    outcome: IdentityRunOutcome, sources: IdentitySources
) -> pd.DataFrame:
    if not isinstance(outcome, IdentityRunOutcome):
        raise TypeError("outcome must be IdentityRunOutcome")
    if outcome._source_binding != _source_binding(sources):
        raise ValueError("identity outcome does not belong to bound sources")
    frame = outcome.frame
    if frame.columns[-2:].tolist() != list(SOURCE_IDENTITY):
        raise ValueError("identity outcome column contract mismatch")
    if frame[list(SOURCE_IDENTITY)].isna().any().any():
        raise ValueError("identity outcome contains invalid identity")
    if frame.duplicated(list(SOURCE_IDENTITY)).any():
        raise ValueError("identity outcome contains duplicate identity")
    evidence = outcome.evidence
    if (
        tuple(evidence["appended_columns"]) != SOURCE_IDENTITY
        or evidence["old_columns_exact"] is not True
        or int(evidence["matched_rows"]) != len(frame)
    ):
        raise ValueError("identity evidence disagrees with final payload")
    return frame


def write_identity_artifacts(
    layout: Angular5OutputLayout,
    *,
    sources: IdentitySources,
    outcome: IdentityRunOutcome,
) -> IdentityArtifactReceipt:
    descriptors: dict[str, int] | None = None
    try:
        descriptors = _open_claimed(layout)
        root = descriptors["."]
        if _safety._entry_exists(root, ".terminal.failed") or _safety._entry_exists(
            root, "failure.json"
        ):
            raise RuntimeError("cannot write a failed identity run")
        _assert_layout(descriptors, state="empty")
        final = _validate_outcome(outcome, sources)
        serialized = {
            "config.yaml": sources.config_bytes,
            TABLE_NAME: outcome.table_payload,
            IDENTITY_NAME: _publication._json_bytes(outcome.evidence),
        }
        assert_identity_sources_unchanged(sources)
        _publication._atomic_publish_bytes(
            root, layout.run_dir, "config.yaml", serialized["config.yaml"]
        )
        _publication._atomic_publish_bytes(
            descriptors["processed"],
            layout.processed_dir,
            TABLE_NAME,
            serialized[TABLE_NAME],
        )
        _publication._atomic_publish_bytes(
            descriptors["artifacts"],
            layout.artifacts_dir,
            IDENTITY_NAME,
            serialized[IDENTITY_NAME],
        )
        _assert_layout(descriptors, state="artifacts")
        records, identities = _output_records(layout, descriptors)
        if records[f"processed/{TABLE_NAME}"]["row_count"] != len(final):
            raise RuntimeError("identity output row count changed during publication")
        frozen_records = MappingProxyType(
            {
                name: MappingProxyType(dict(record))
                for name, record in records.items()
            }
        )
        return IdentityArtifactReceipt(
            _RECEIPT_TOKEN,
            layout.directory_identities["."],
            frozen_records,
            MappingProxyType(identities),
        )
    except BaseException as error:
        record_identity_failure(layout, error)
        raise
    finally:
        _publication._close_descriptors(descriptors)


def publish_identity_manifest(
    layout: Angular5OutputLayout,
    *,
    sources: IdentitySources,
    receipt: IdentityArtifactReceipt,
    software: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(receipt, IdentityArtifactReceipt):
        raise TypeError("publisher requires an IdentityArtifactReceipt")
    if (
        layout.directory_identities is None
        or receipt._run_identity != layout.directory_identities.get(".")
    ):
        raise ValueError("identity artifact receipt does not belong to this run")
    descriptors: dict[str, int] | None = None
    locked = False
    staged: str | None = None
    try:
        descriptors = _open_claimed(layout)
        root = descriptors["."]
        _safety._terminal_lock_acquire(root)
        locked = True
        if _safety._entry_exists(root, ".terminal.failed") or _safety._entry_exists(
            root, "failure.json"
        ):
            raise RuntimeError("cannot publish a failed identity run")
        _assert_layout(descriptors, state="artifacts", terminal_lock=True)
        records, identities = _output_records(layout, descriptors)
        if records != dict(receipt._records) or identities != dict(receipt._identities):
            raise RuntimeError("identity output changed before manifest publication")
        manifest = {
            "schema_version": "1.0",
            "status": "complete",
            "role": "MC-only Angular5 source-identity baseline",
            "join_key": list(SOURCE_IDENTITY),
            "appended_columns": list(SOURCE_IDENTITY),
            "software": dict(software),
            "inputs": _source_records(sources),
            "outputs": records,
        }
        payload = _publication._json_bytes(manifest)
        staged = _publication._stage_bytes(
            descriptors["artifacts"], MANIFEST_NAME, payload
        )
        _publication._before_final_source_revalidation()

        def final_check() -> None:
            assert_identity_sources_unchanged(sources)
            current_records, current_identities = _output_records(layout, descriptors)
            if current_records != records or current_identities != identities:
                raise RuntimeError("identity output changed before manifest publication")
            current = _open_claimed(layout)
            _publication._close_descriptors(current)

        _publication._promote_no_clobber(
            descriptors["artifacts"],
            layout.artifacts_dir,
            staged,
            MANIFEST_NAME,
            immediate_check=final_check,
        )
        staged = None
        _assert_layout(descriptors, state="complete", terminal_lock=True)
        return manifest
    except BaseException as error:
        if descriptors is not None:
            _safety._cleanup_staged(descriptors["artifacts"], staged)
            staged = None
            if locked:
                _install_failure_locked(descriptors["."], layout.run_dir, error)
            else:
                record_identity_failure(layout, error)
        else:
            record_identity_failure(layout, error)
        raise
    finally:
        if descriptors is not None:
            _safety._cleanup_staged(descriptors["artifacts"], staged)
            if locked:
                _safety._terminal_lock_release(descriptors["."])
        _publication._close_descriptors(descriptors)
