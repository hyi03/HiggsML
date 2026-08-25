"""Sealed MC-only configuration, source binding, and output claim for Angular5."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import errno
import hashlib
import os
from pathlib import Path
import stat
from types import MappingProxyType
from typing import Any, Mapping

import yaml


class _DuplicateKeyError(yaml.constructor.ConstructorError):
    """A YAML mapping contains a key more than once."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader which refuses duplicate keys at every depth."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as error:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error
        if duplicate:
            raise _DuplicateKeyError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate mapping key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


_FROZEN_OUTPUT_RUN = "runs/angular5-mc-363490-2026-08-26"
_SOURCE_RELATIVE_PATHS = {
    "enrichment_config": "config/angular5_mc_dsid363490.yaml",
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
    "processed/mc_events_angular5.csv.gz",
    "artifacts/identity_validation.json",
    "artifacts/angular5_summary.json",
    "artifacts/run_manifest.json",
]
_EXPECTED_SELECTION = {
    "require_exactly_four_leptons": True,
    "allowed_lepton_types": [11, 13],
    "lepton_pt_thresholds_gev": [20.0, 15.0, 10.0, 7.0],
    "electron_max_abs_eta": 2.47,
    "muon_max_abs_eta": 2.7,
    "require_zero_charge": True,
    "min_all_sfos_mass_gev": 5.0,
    "z1_mass_window_gev": [50.0, 106.0],
    "z2_mass": {
        "min_mode": "fixed",
        "fixed_min_gev": 12.0,
        "max_gev": 115.0,
        "sliding": {
            "low_m4l_gev": 140.0,
            "high_m4l_gev": 190.0,
            "low_min_gev": 12.0,
            "high_min_gev": 50.0,
        },
    },
    "m4l_window_gev": [105.0, 160.0],
    "lepton_quality": {
        "enabled": True,
        "require_event_trigger": True,
        "require_trigger_match": True,
        "require_tight_id": True,
        "track_isolation_max": 0.3,
        "calo_isolation_max": 0.3,
        "electron_d0sig_max": 5.0,
        "muon_d0sig_max": 3.0,
        "z0_sintheta_max_mm": 0.5,
    },
}
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
        "higgs": {
            "path": _SOURCE_RELATIVE_PATHS["higgs_root"],
            "sha256": _EXPECTED_SOURCE_HASHES["higgs_root"],
            "channel_numbers": [345060],
            "label": 1,
            "input_profile": "release22",
        },
        "zz": {
            "path": _SOURCE_RELATIVE_PATHS["zz_root"],
            "sha256": _EXPECTED_SOURCE_HASHES["zz_root"],
            "channel_numbers": [363490],
            "label": 0,
            "input_profile": "open_data_2020",
            "normalization": {
                "source": "official_metadata",
                "xsec_pb": 1.2564,
                "k_factor": 1.0,
                "filter_efficiency": 1.0,
                "sum_of_weights": 7538705.808,
            },
        },
    },
    "selection": _EXPECTED_SELECTION,
    "artifacts": _APPROVED_ARTIFACTS,
}


@dataclass(frozen=True)
class Angular5EnrichmentConfig:
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
class Angular5SourceReceipt:
    name: str
    path: Path
    device: int
    inode: int
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class Angular5Sources:
    config: Angular5EnrichmentConfig
    config_bytes: bytes
    project_root: Path
    receipts: Mapping[str, Angular5SourceReceipt]


@dataclass(frozen=True)
class Angular5OutputLayout:
    run_dir: Path
    config_snapshot: Path
    processed_dir: Path
    artifacts_dir: Path
    directory_identities: Mapping[str, tuple[int, int]] | None = None


def _exact_value(value: Any, expected: Any) -> bool:
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(value) == set(expected) and all(
            _exact_value(value[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(value) == len(expected) and all(
            _exact_value(item, wanted) for item, wanted in zip(value, expected)
        )
    return value == expected


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _deep_freeze(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _load_config_bytes(payload: bytes) -> Angular5EnrichmentConfig:
    try:
        raw = yaml.load(payload, Loader=_UniqueKeySafeLoader)
    except _DuplicateKeyError as error:
        raise ValueError(
            "Angular5 enrichment config contains a duplicate mapping key"
        ) from error
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ValueError("Angular5 enrichment config is not valid YAML") from error
    if not _exact_value(raw, _EXPECTED_CONFIG):
        raise ValueError("Angular5 enrichment config does not match the exact sealed schema")
    samples = {
        "higgs": MappingProxyType(
            {
                **raw["samples"]["higgs"],
                "channel_numbers": tuple(raw["samples"]["higgs"]["channel_numbers"]),
            }
        ),
        "zz": MappingProxyType(
            {
                **raw["samples"]["zz"],
                "channel_numbers": tuple(raw["samples"]["zz"]["channel_numbers"]),
                "normalization": MappingProxyType(
                    dict(raw["samples"]["zz"]["normalization"])
                ),
            }
        ),
    }
    return Angular5EnrichmentConfig(
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
        selection=_deep_freeze(deepcopy(raw["selection"])),
        artifacts=tuple(_APPROVED_ARTIFACTS),
    )


def load_angular5_enrichment_config(path: str | Path) -> Angular5EnrichmentConfig:
    try:
        payload = Path(path).read_bytes()
    except OSError as error:
        raise ValueError("Angular5 enrichment config is not valid YAML") from error
    return _load_config_bytes(payload)


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)


def _open_source_parent(path: Path, name: str) -> int:
    descriptor = os.open(path.anchor, _directory_flags())
    try:
        for part in path.parent.parts[1:]:
            try:
                child = os.open(part, _directory_flags(), dir_fd=descriptor)
            except FileNotFoundError as error:
                raise FileNotFoundError(
                    f"required Angular5 source is missing: {name}"
                ) from error
            except OSError as error:
                if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise ValueError(
                        f"Angular5 source path contains a symlink: {path}"
                    ) from error
                raise ValueError(f"Angular5 source path is unsafe: {path}") from error
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _stat_signature(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        int(metadata.st_dev),
        int(metadata.st_ino),
        int(metadata.st_mode),
        int(metadata.st_size),
        int(metadata.st_mtime_ns),
        int(metadata.st_ctime_ns),
    )


def _open_regular_at_path(name: str, path: Path) -> tuple[int, int]:
    parent = _open_source_parent(path, name)
    try:
        try:
            descriptor = os.open(
                path.name,
                os.O_RDONLY
                | getattr(os, "O_NONBLOCK", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent,
            )
        except FileNotFoundError as error:
            raise FileNotFoundError(
                f"required Angular5 source is missing: {name}"
            ) from error
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise ValueError(
                    f"Angular5 source path contains a symlink: {path}"
                ) from error
            raise ValueError(f"required Angular5 source is unsafe: {name}") from error
        return parent, descriptor
    except Exception:
        os.close(parent)
        raise


def _assert_path_still_bound(
    name: str, path: Path, expected: os.stat_result
) -> None:
    parent: int | None = None
    descriptor: int | None = None
    try:
        parent, descriptor = _open_regular_at_path(name, path)
        current = os.fstat(descriptor)
        if not stat.S_ISREG(current.st_mode) or _stat_signature(current) != _stat_signature(
            expected
        ):
            raise RuntimeError(f"Angular5 source changed during hashing: {name}")
    except (FileNotFoundError, ValueError) as error:
        raise ValueError(f"Angular5 source path changed or contains a symlink: {name}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent is not None:
            os.close(parent)


def _bind_regular(name: str, path: Path) -> tuple[Angular5SourceReceipt, bytes]:
    absolute = Path(os.path.abspath(path))
    parent, descriptor = _open_regular_at_path(name, absolute)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"required Angular5 source is not a regular file: {name}")
        digest = hashlib.sha256()
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            if name == "enrichment_config":
                chunks.append(chunk)
        final_metadata = os.fstat(descriptor)
        if _stat_signature(final_metadata) != _stat_signature(metadata):
            raise RuntimeError(f"Angular5 source changed during hashing: {name}")
        _assert_path_still_bound(name, absolute, final_metadata)
        payload = b"".join(chunks)
        return (
            Angular5SourceReceipt(
                name=name,
                path=absolute,
                device=int(metadata.st_dev),
                inode=int(metadata.st_ino),
                size_bytes=int(metadata.st_size),
                sha256=digest.hexdigest(),
            ),
            payload,
        )
    finally:
        os.close(descriptor)
        os.close(parent)


def resolve_angular5_sources(
    *, project_root: str | Path, config_path: str | Path
) -> Angular5Sources:
    root = Path(project_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Angular5 project root is not a directory")
    expected_config = root / _SOURCE_RELATIVE_PATHS["enrichment_config"]
    requested_config = Path(os.path.abspath(config_path))
    if requested_config != expected_config:
        raise ValueError("Angular5 enrichment config must use the exact frozen path")

    receipts: dict[str, Angular5SourceReceipt] = {}
    config_bytes = b""
    for name, relative in _SOURCE_RELATIVE_PATHS.items():
        receipt, snapshot = _bind_regular(name, root / relative)
        receipts[name] = receipt
        if name == "enrichment_config":
            config_bytes = snapshot
    config = _load_config_bytes(config_bytes)
    for name, expected_hash in _EXPECTED_SOURCE_HASHES.items():
        if receipts[name].sha256 != expected_hash:
            raise ValueError(f"Angular5 source SHA-256 mismatch: {name}")
    return Angular5Sources(
        config=config,
        config_bytes=config_bytes,
        project_root=root,
        receipts=MappingProxyType(dict(receipts)),
    )


def assert_angular5_sources_unchanged(sources: Angular5Sources) -> None:
    if not isinstance(sources, Angular5Sources):
        raise TypeError("sources must be Angular5Sources")
    for name, original in sources.receipts.items():
        try:
            current, _ = _bind_regular(name, original.path)
        except (FileNotFoundError, ValueError, OSError) as error:
            raise RuntimeError(f"Angular5 source changed before publication: {name}") from error
        if current != original:
            raise RuntimeError(f"Angular5 source changed before publication: {name}")


def _absolute_without_symlinks(path: Path, *, allow_final: bool = False) -> Path:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    parts = absolute.parts[1:]
    for index, part in enumerate(parts):
        current /= part
        if current.is_symlink() and not (allow_final and index == len(parts) - 1):
            raise ValueError(f"Angular5 output path contains a symlink: {current}")
    return absolute


def _is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _open_claim_parent(run_dir: Path) -> int:
    descriptor = os.open(run_dir.anchor, _directory_flags())
    try:
        for part in run_dir.parent.parts[1:]:
            try:
                child = os.open(part, _directory_flags(), dir_fd=descriptor)
            except FileNotFoundError:
                os.mkdir(part, dir_fd=descriptor)
                child = os.open(part, _directory_flags(), dir_fd=descriptor)
            except OSError as error:
                if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise ValueError(
                        f"Angular5 output path contains a symlink: {part}"
                    ) from error
                raise
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _identity(descriptor: int) -> tuple[int, int]:
    metadata = os.fstat(descriptor)
    return int(metadata.st_dev), int(metadata.st_ino)


def claim_angular5_output(
    *,
    sources: Angular5Sources,
    project_root: str | Path,
    working_directory: str | Path,
    run_dir: str | Path,
) -> Angular5OutputLayout:
    if not isinstance(sources, Angular5Sources):
        raise TypeError("sources must be Angular5Sources")
    root = Path(project_root).resolve(strict=True)
    if root != sources.project_root:
        raise ValueError("Angular5 output project does not match the bound sources")
    logical = Path(run_dir)
    unresolved = logical if logical.is_absolute() else Path(working_directory).resolve() / logical
    target = _absolute_without_symlinks(unresolved, allow_final=True)
    protected = [
        root / name
        for name in (
            "data", "outputs", "config", "docs", "src", "scripts", "tests",
            ".git", ".venv",
        )
    ]
    protected.extend(receipt.path for receipt in sources.receipts.values())
    protected.append(root / "runs/full-baseline-363490-2026-08-11-r2")
    if target == root or any(_is_within(target, path) for path in protected):
        raise ValueError("Angular5 output path is inside a protected path")
    expected = root / sources.config.output_run
    if target != expected:
        raise ValueError("Angular5 run directory does not match the frozen output path")
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Angular5 run directory already exists: {logical}")
    assert_angular5_sources_unchanged(sources)

    parent = _open_claim_parent(target)
    root_descriptor: int | None = None
    try:
        try:
            os.mkdir(target.name, dir_fd=parent)
        except FileExistsError as error:
            raise FileExistsError(f"Angular5 run directory already exists: {logical}") from error
        root_descriptor = os.open(target.name, _directory_flags(), dir_fd=parent)
        identities = {".": _identity(root_descriptor)}
        for name in ("processed", "artifacts"):
            os.mkdir(name, dir_fd=root_descriptor)
            child = os.open(name, _directory_flags(), dir_fd=root_descriptor)
            try:
                identities[name] = _identity(child)
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
