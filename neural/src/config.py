from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any

import yaml
import hashlib
from src.dataset_binding import DatasetContext, dataset_context
from src.resource_seals import RESOURCE_HASHES


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
    source_file_id: str = ""


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
    dataset: DatasetContext


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
    "channelNumber", "source_file_id", "event_group_id",
)

def load_preprocess_protocol(path: str | Path, *, dataset: str) -> PreprocessProtocol:
    raw, payload = _yaml(path)
    is_debug = raw.get("protocol_id") == "higgsml-preprocess-debug"
    if not is_debug and hashlib.sha256(payload).hexdigest() != RESOURCE_HASHES["preprocess_protocol_v2.yaml"]:
        raise InputBindingError("sealed v2 preprocess protocol changed; old mixed inputs are unsupported")
    if is_debug and raw.get("protocol_id") != "higgsml-preprocess-debug":
        raise InputBindingError("invalid preprocess debug protocol")
    context = dataset_context(dataset)
    profile = context.profile
    samples = {}
    for role, value in context.samples.items():
        norm = context.science["normalization"][dataset][role]
        samples[role] = SampleProtocol(
            source_sample=f"{role}_{value['dsid']}", dsid=value["dsid"], label=value["label"],
            sha256=value["sha256"], input_profile=profile["input_profile"],
            tree_name=profile["tree_name"], momentum_unit=profile["momentum_unit"],
            expected_entry_count=value["entry_count"], normalization_in_events=norm is None,
            branches=profile["branches"], normalization=norm, source_file_id=value["file_id"],
        )
    return PreprocessProtocol(raw["protocol_id"], samples, raw["selection"], tuple(raw["output_columns"]),
                              raw["luminosity_pb"], 1e-12, 1e-12, raw, payload, context)


def load_preprocess_run_config(path: str | Path, *, dataset: str) -> PreprocessRunConfig:
    raw, payload = _yaml(path)
    if set(raw) != {"schema_version", "data_root", "resources"} or raw["schema_version"] != "2.0":
        raise InputBindingError("run config requires v2 data_root; independent sample paths are forbidden")
    if not isinstance(raw["resources"], dict) or set(raw["resources"]) != {"chunk_size_events"}:
        raise InputBindingError("run config resources changed")
    chunk = raw["resources"]["chunk_size_events"]
    if type(chunk) is not int or chunk <= 0 or type(raw["data_root"]) is not str:
        raise InputBindingError("invalid data root or chunk size")
    context = dataset_context(dataset)
    root = Path(raw["data_root"])
    root = root if root.is_absolute() else Path(path).absolute().parent / root
    paths = {role: root / dataset / value["filename"] for role, value in context.samples.items()}
    return PreprocessRunConfig(paths, chunk, payload)
