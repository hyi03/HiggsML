"""Sealed R3-ARM64 Angular5 source binding and output claim."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

from . import angular5_enrichment_run as _base
from .angular5_identity_run import assert_native_arm64


OUTPUT_RUN = "runs/angular5-mc-363490-2026-08-26-r3-arm64"
SOURCE_IDENTITY_RUN = "runs/angular5-identity-mc-363490-2026-08-26-r3-arm64"
SOURCE_PATHS = {
    "enrichment_config": "config/angular5_mc_dsid363490_r3_arm64.yaml",
    "frozen_config": "config/dsid363490.yaml",
    "identity_manifest": f"{SOURCE_IDENTITY_RUN}/artifacts/run_manifest.json",
    "identity_table": f"{SOURCE_IDENTITY_RUN}/processed/mc_events_source_identity.csv.gz",
    "higgs_root": "data/raw/higgs.root",
    "zz_root": "data/raw/zz_363490.root",
}
HASHES = {
    "frozen_config": "0282cfa965228e036f4ada3c010bd7d40b1b14e56c2aa33551784683237cd320",
    "identity_manifest": "74ebc01ee452bf2f6a7a792d14ed1a62eefefffc6bb090a498fb76abe20273a0",
    "identity_table": "a3ffd8c53aca90dc1813d4f88f9d12113b1918a6f193b8f8ee792cdfd4621f94",
    "higgs_root": "5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0",
    "zz_root": "76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07",
}
ARTIFACTS = (
    "config.yaml",
    "processed/mc_events_angular5.csv.gz",
    "artifacts/identity_validation.json",
    "artifacts/angular5_summary.json",
    "artifacts/run_manifest.json",
)
EXPECTED = {
    "schema_version": "1.0",
    "output_run": OUTPUT_RUN,
    "frozen_reference": {"path": SOURCE_PATHS["frozen_config"], "sha256": HASHES["frozen_config"]},
    "authoritative_identity": {
        "manifest_path": SOURCE_PATHS["identity_manifest"],
        "manifest_sha256": HASHES["identity_manifest"],
        "table_path": SOURCE_PATHS["identity_table"],
        "table_sha256": HASHES["identity_table"],
    },
    "tree_name": "analysis",
    "momentum_unit": "GeV",
    "entry_stop": None,
    "chunk_size_events": 50000,
    "luminosity_pb": 10000.0,
    "samples": {
        "higgs": {
            "source_sample": "higgs_345060", "path": SOURCE_PATHS["higgs_root"],
            "sha256": HASHES["higgs_root"], "channel_numbers": [345060],
            "label": 1, "input_profile": "release22",
        },
        "zz": {
            "source_sample": "zz_363490", "path": SOURCE_PATHS["zz_root"],
            "sha256": HASHES["zz_root"], "channel_numbers": [363490],
            "label": 0, "input_profile": "open_data_2020",
            "normalization": {"source": "official_metadata", "xsec_pb": 1.2564,
                              "k_factor": 1.0, "filter_efficiency": 1.0,
                              "sum_of_weights": 7538705.808},
        },
    },
    "selection": deepcopy(_base._EXPECTED_SELECTION),
    "artifacts": list(ARTIFACTS),
}


@dataclass(frozen=True)
class Angular5R3Arm64Config:
    schema_version: str
    output_run: str
    frozen_reference: Mapping[str, str]
    authoritative_identity: Mapping[str, str]
    tree_name: str
    momentum_unit: str
    entry_stop: None
    chunk_size_events: int
    luminosity_pb: float
    samples: Mapping[str, Mapping[str, Any]]
    selection: Mapping[str, Any]
    artifacts: tuple[str, ...]


@dataclass(frozen=True)
class Angular5R3Arm64Sources:
    config: Angular5R3Arm64Config
    config_bytes: bytes
    project_root: Path
    receipts: Mapping[str, _base.Angular5SourceReceipt]


def _load_config_bytes(payload: bytes) -> Angular5R3Arm64Config:
    try:
        raw = yaml.load(payload, Loader=_base._UniqueKeySafeLoader)
    except _base._DuplicateKeyError as error:
        raise ValueError("R3 Angular5 config contains a duplicate mapping key") from error
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ValueError("R3 Angular5 config is not valid YAML") from error
    if not _base._exact_value(raw, EXPECTED):
        raise ValueError("R3 Angular5 config does not match the exact sealed schema")
    samples: dict[str, Mapping[str, Any]] = {}
    for name in ("higgs", "zz"):
        sample = dict(raw["samples"][name])
        sample["channel_numbers"] = tuple(sample["channel_numbers"])
        if "normalization" in sample:
            sample["normalization"] = MappingProxyType(dict(sample["normalization"]))
        samples[name] = MappingProxyType(sample)
    return Angular5R3Arm64Config(
        schema_version="1.0", output_run=OUTPUT_RUN,
        frozen_reference=MappingProxyType(dict(raw["frozen_reference"])),
        authoritative_identity=MappingProxyType(dict(raw["authoritative_identity"])),
        tree_name="analysis", momentum_unit="GeV", entry_stop=None,
        chunk_size_events=50000, luminosity_pb=10000.0,
        samples=MappingProxyType(samples), selection=_base._deep_freeze(deepcopy(raw["selection"])),
        artifacts=ARTIFACTS,
    )


def load_angular5_r3_arm64_config(path: str | Path) -> Angular5R3Arm64Config:
    try:
        return _load_config_bytes(Path(path).read_bytes())
    except OSError as error:
        raise ValueError("R3 Angular5 config is not valid YAML") from error


def resolve_angular5_r3_arm64_sources(*, project_root: str | Path, config_path: str | Path) -> Angular5R3Arm64Sources:
    root = Path(project_root).resolve(strict=True)
    expected = root / SOURCE_PATHS["enrichment_config"]
    if Path(os.path.abspath(config_path)) != expected:
        raise ValueError("R3 Angular5 config must use the exact frozen path")
    receipts: dict[str, _base.Angular5SourceReceipt] = {}
    config_bytes = b""
    for name, relative in SOURCE_PATHS.items():
        receipt, snapshot = _base._bind_regular(name, root / relative)
        receipts[name] = receipt
        if name == "enrichment_config":
            config_bytes = snapshot
    config = _load_config_bytes(config_bytes)
    for name, expected_hash in HASHES.items():
        if receipts[name].sha256 != expected_hash:
            raise ValueError(f"R3 Angular5 source SHA-256 mismatch: {name}")
    return Angular5R3Arm64Sources(config, config_bytes, root, MappingProxyType(receipts))


def assert_angular5_r3_arm64_sources_unchanged(sources: Angular5R3Arm64Sources) -> None:
    if not isinstance(sources, Angular5R3Arm64Sources):
        raise TypeError("sources must be Angular5R3Arm64Sources")
    for name, original in sources.receipts.items():
        try:
            current, _ = _base._bind_regular(name, original.path)
        except (FileNotFoundError, ValueError, OSError) as error:
            raise RuntimeError(f"R3 Angular5 source changed before publication: {name}") from error
        if current != original:
            raise RuntimeError(f"R3 Angular5 source changed before publication: {name}")


def claim_angular5_r3_arm64_output(*, sources: Angular5R3Arm64Sources, project_root: str | Path, working_directory: str | Path, run_dir: str | Path) -> _base.Angular5OutputLayout:
    if not isinstance(sources, Angular5R3Arm64Sources):
        raise TypeError("sources must be Angular5R3Arm64Sources")
    assert_native_arm64()
    root = Path(project_root).resolve(strict=True)
    if root != sources.project_root:
        raise ValueError("R3 Angular5 output project does not match sources")
    logical = Path(run_dir)
    target = _base._absolute_without_symlinks(
        logical if logical.is_absolute() else Path(working_directory).resolve() / logical,
        allow_final=True,
    )
    protected = [root / name for name in ("data", "outputs", "config", "docs", "src", "scripts", "tests", ".git", ".venv")]
    protected.extend(receipt.path for receipt in sources.receipts.values())
    protected.extend((root / "runs/angular5-identity-mc-363490-2026-08-26-r2", root / SOURCE_IDENTITY_RUN))
    if target == root or any(_base._is_within(target, path) for path in protected):
        raise ValueError("R3 Angular5 output path is inside a protected path")
    if target != root / OUTPUT_RUN:
        raise ValueError("R3 Angular5 run directory does not match the frozen output path")
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"R3 Angular5 run directory already exists: {logical}")
    assert_angular5_r3_arm64_sources_unchanged(sources)
    parent = _base._open_claim_parent(target)
    root_descriptor: int | None = None
    try:
        os.mkdir(target.name, dir_fd=parent)
        root_descriptor = os.open(target.name, _base._directory_flags(), dir_fd=parent)
        identities = {".": _base._identity(root_descriptor)}
        for name in ("processed", "artifacts"):
            os.mkdir(name, dir_fd=root_descriptor)
            child = os.open(name, _base._directory_flags(), dir_fd=root_descriptor)
            try:
                identities[name] = _base._identity(child)
            finally:
                os.close(child)
        return _base.Angular5OutputLayout(target, target / "config.yaml", target / "processed", target / "artifacts", MappingProxyType(identities))
    finally:
        if root_descriptor is not None:
            os.close(root_descriptor)
        os.close(parent)
