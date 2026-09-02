from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any

import yaml


class ExitCode(IntEnum):
    SUCCESS = 0
    USAGE = 2
    INPUT_BINDING = 3
    TRANSACTION = 4
    REFUSED = 5
    INTERNAL_ERROR = 70


class InputBindingError(ValueError):
    """Raised when an input, schema, hash, or protocol binding fails."""

    exit_code = ExitCode.INPUT_BINDING


class TestOpeningRefused(RuntimeError):
    """Raised when the one-shot test-opening gate refuses an invocation."""

    exit_code = ExitCode.REFUSED


class TestOpeningFailure(RuntimeError):
    """Sanitized post-claim failure safe for receipts and logs."""

    def __init__(self, stage: str, exit_code: ExitCode) -> None:
        self.stage = stage
        self.exit_code = exit_code
        super().__init__(f"test-opening failed at stage: {stage}")


class _UniqueLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: _UniqueLoader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise InputBindingError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def _yaml(path: str | Path) -> tuple[dict[str, Any], bytes]:
    source = Path(path)
    try:
        payload = source.read_bytes()
        value = yaml.load(payload, Loader=_UniqueLoader)
    except InputBindingError:
        raise
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise InputBindingError(f"cannot load YAML: {source}") from error
    if not isinstance(value, dict):
        raise InputBindingError("YAML root must be a mapping")
    return value, payload


@dataclass(frozen=True)
class SampleProtocol:
    source_sample: str
    dsid: int
    label: int
    sha256: str
    input_profile: str
    tree_name: str
    momentum_unit: str
    expected_entry_count: int
    normalization_in_events: bool
    branches: dict[str, str]
    normalization: dict[str, float] | None


@dataclass(frozen=True)
class PreprocessProtocol:
    protocol_id: str
    samples: dict[str, SampleProtocol]
    selection: dict[str, Any]
    output_columns: tuple[str, ...]
    luminosity_pb: float
    float_rtol: float
    float_atol: float
    raw: dict[str, Any]
    payload: bytes


@dataclass(frozen=True)
class PreprocessRunConfig:
    sample_paths: dict[str, Path]
    chunk_size_events: int
    payload: bytes


_OUTPUT_COLUMNS = (
    "lep1_pt", "lep2_pt", "lep3_pt", "lep4_pt",
    "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta",
    "mZ1", "mZ2", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
    "cos_theta_star", "cos_theta_1", "cos_theta_2", "phi_decay_planes",
    "phi_production_plane", "m4l", "label", "split", "physical_weight",
    "train_weight", "source_sample", "source_entry", "runNumber", "eventNumber",
    "channelNumber",
)

_COMMON_BRANCHES = {
    "runNumber": "runNumber", "eventNumber": "eventNumber",
    "channelNumber": "channelNumber", "lep_n": "lep_n", "lep_pt": "lep_pt",
    "lep_eta": "lep_eta", "lep_phi": "lep_phi", "lep_charge": "lep_charge",
    "lep_type": "lep_type", "trigE": "trigE", "trigM": "trigM",
    "lep_isTightID": "lep_isTightID", "lep_z0": "lep_z0", "mcWeight": "mcWeight",
}
_HIGGS_BRANCHES = {
    **_COMMON_BRANCHES, "lep_e": "lep_e", "lep_isTrigMatched": "lep_isTrigMatched",
    "lep_track_iso": "lep_ptvarcone30", "lep_calo_iso": "lep_topoetcone20",
    "lep_d0sig": "lep_d0sig", "xsec": "xsec", "kfac": "kfac",
    "filteff": "filteff", "sum_of_weights": "sum_of_weights",
}
_ZZ_BRANCHES = {
    **_COMMON_BRANCHES, "lep_e": "lep_E", "lep_isTrigMatched": "lep_trigMatched",
    "lep_track_iso": "lep_ptcone30", "lep_calo_iso": "lep_etcone20",
    "lep_d0sig": "lep_tracksigd0pvunbiased",
}
_SELECTION = {
    "lepton_pt_thresholds_gev": [20.0, 15.0, 10.0, 7.0],
    "electron_max_abs_eta": 2.47, "muon_max_abs_eta": 2.7,
    "track_isolation_max": 0.3, "calo_isolation_max": 0.3,
    "electron_d0sig_max": 5.0, "muon_d0sig_max": 3.0,
    "z0_sintheta_max_mm": 0.5, "min_all_sfos_mass_gev": 5.0,
    "z1_mass_window_gev": [50.0, 106.0], "z2_mass_window_gev": [12.0, 115.0],
    "m4l_window_gev": [105.0, 160.0], "z2_min_mode": "fixed",
    "sliding_z2": {
        "low_m4l_gev": 140.0, "high_m4l_gev": 190.0, "low_min_gev": 12.0,
        "high_min_gev": 50.0, "max_gev": 115.0,
    },
}
_SPLIT = {
    "hash": "blake2b", "digest_size": 8, "byte_order": "big", "modulo": 10,
    "train_buckets": [0, 1, 2, 3, 4, 5], "validation_buckets": [6, 7],
    "test_buckets": [8, 9],
}
_SERIALIZATION = {
    "encoding": "utf-8", "line_ending": "LF", "float_format": ".17g",
    "gzip_compresslevel": 9, "gzip_mtime": 0,
}
_GOLDEN = {
    "authoritative_platform": "osx-arm64",
    "identity_manifest_path": "xgboost/runs/angular5-identity-mc-363490-2026-08-26-r3-arm64/artifacts/run_manifest.json",
    "identity_manifest_sha256": "74ebc01ee452bf2f6a7a792d14ed1a62eefefffc6bb090a498fb76abe20273a0",
    "identity_table_path": "xgboost/runs/angular5-identity-mc-363490-2026-08-26-r3-arm64/processed/mc_events_source_identity.csv.gz",
    "identity_table_sha256": "a3ffd8c53aca90dc1813d4f88f9d12113b1918a6f193b8f8ee792cdfd4621f94",
    "enrichment_manifest_path": "xgboost/runs/angular5-mc-363490-2026-08-26-r3-arm64/artifacts/run_manifest.json",
    "enrichment_manifest_sha256": "ab5e283f4b6a2038a100a2a9d4e6745cccc3ee7f400ef056bcd05d3c22f28ad5",
    "baseline_manifest_path": "xgboost/runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json",
    "baseline_manifest_sha256": "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8",
    "table_path": "xgboost/runs/angular5-mc-363490-2026-08-26-r3-arm64/processed/mc_events_angular5.csv.gz",
    "table_sha256": "bc31f4e65ccecc0a1962648cfe240b67d8ecc6df8eda2478b3f46c93d2f34f09",
    "float_rtol": 1e-12, "float_atol": 1e-12, "structural_exact": True,
    "expected_counts": {
        "higgs_345060": {"read": 419943, "selected": 187128, "train": 112502, "validation": 37290, "test": 37336},
        "zz_363490": {"read": 554279, "selected": 11976, "train": 7174, "validation": 2429, "test": 2373},
        "total": {"read": 974222, "selected": 199104, "train": 119676, "validation": 39719, "test": 39709},
    },
    "expected_legacy_duplicates": {"groups": 2, "rows": 4},
}


def load_preprocess_protocol(path: str | Path) -> PreprocessProtocol:
    raw, payload = _yaml(path)
    required = {"schema_version", "protocol_id", "luminosity_pb", "samples", "selection", "split", "output_columns", "golden", "serialization"}
    if set(raw) != required or raw.get("schema_version") != "1.0" or raw.get("protocol_id") != "higgsml-preprocess-v1":
        raise InputBindingError("protocol does not match the sealed v1 schema")
    if tuple(raw["samples"]) != ("higgs", "zz") or tuple(raw["output_columns"]) != _OUTPUT_COLUMNS:
        raise InputBindingError("protocol samples or output columns changed")
    expected_samples = {
        "higgs": {
            "source_sample": "higgs_345060", "dsid": 345060, "label": 1,
            "sha256": "5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0",
            "input_profile": "release22", "tree_name": "analysis", "momentum_unit": "GeV",
            "expected_entry_count": 419943, "normalization_in_events": True,
            "branches": _HIGGS_BRANCHES,
        },
        "zz": {
            "source_sample": "zz_363490", "dsid": 363490, "label": 0,
            "sha256": "76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07",
            "input_profile": "open_data_2020", "tree_name": "mini", "momentum_unit": "MeV",
            "expected_entry_count": 554279, "normalization_in_events": False,
            "branches": _ZZ_BRANCHES,
            "normalization": {
                "xsec_pb": 1.2564, "k_factor": 1.0, "filter_efficiency": 1.0,
                "sum_of_weights": 7538705.808,
            },
        },
    }
    samples = {}
    for key, value in raw["samples"].items():
        if value != expected_samples[key]:
            raise InputBindingError(f"protocol sample binding changed: {key}")
        samples[key] = SampleProtocol(
            source_sample=str(value["source_sample"]), dsid=int(value["dsid"]), label=int(value["label"]),
            sha256=str(value["sha256"]), input_profile=str(value["input_profile"]), tree_name=str(value["tree_name"]),
            momentum_unit=str(value["momentum_unit"]), expected_entry_count=int(value["expected_entry_count"]),
            normalization_in_events=bool(value["normalization_in_events"]),
            branches=dict(value["branches"]), normalization=(dict(value["normalization"]) if "normalization" in value else None),
        )
    golden = raw["golden"]
    if golden != _GOLDEN:
        raise InputBindingError("golden authority changed")
    if raw["selection"] != _SELECTION:
        raise InputBindingError("selection protocol changed")
    if raw["split"] != _SPLIT:
        raise InputBindingError("split protocol changed")
    if raw["serialization"] != _SERIALIZATION:
        raise InputBindingError("serialization protocol changed")
    if float(raw["luminosity_pb"]) != 10000.0:
        raise InputBindingError("luminosity protocol changed")
    return PreprocessProtocol(
        raw["protocol_id"], samples, dict(raw["selection"]), tuple(raw["output_columns"]),
        float(raw["luminosity_pb"]), float(golden["float_rtol"]), float(golden["float_atol"]), raw, payload,
    )


def load_preprocess_run_config(path: str | Path) -> PreprocessRunConfig:
    raw, payload = _yaml(path)
    if set(raw) != {"schema_version", "samples", "resources"} or raw.get("schema_version") != "1.0":
        raise InputBindingError("run config does not match the sealed schema")
    if tuple(raw.get("samples", {})) != ("higgs", "zz"):
        raise InputBindingError("run config samples must be exactly higgs and zz")
    paths = {}
    for key, value in raw["samples"].items():
        if not isinstance(value, dict) or set(value) != {"path"}:
            raise InputBindingError(f"run config samples.{key} must contain only path")
        paths[key] = Path(value["path"])
    if not isinstance(raw["resources"], dict) or set(raw["resources"]) != {"chunk_size_events"}:
        raise InputBindingError("run config resources must contain only chunk_size_events")
    chunk = raw["resources"]["chunk_size_events"]
    if isinstance(chunk, bool) or not isinstance(chunk, int) or chunk <= 0:
        raise InputBindingError("chunk_size_events must be a positive integer")
    return PreprocessRunConfig(paths, chunk, payload)
