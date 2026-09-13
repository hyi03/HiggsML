from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
import hashlib
from higgsml.data_contract import DATASET_NAMES
from higgsml.resource_seals import RESOURCE_HASHES


class InputBindingError(ValueError):
    """Raised when an input, schema, hash, or protocol binding fails."""

    exit_code = 3


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
class H4lSelectionProtocol:
    protocol_id: str
    selection: dict[str, Any]
    raw: dict[str, Any]
    payload: bytes


def load_selection_protocol(path: str | Path, *, dataset: str) -> H4lSelectionProtocol:
    raw, payload = _yaml(path)
    resource = "protocols/h4l_selection_v1.yaml"
    if (dataset not in DATASET_NAMES
            or raw.get("protocol_id") != "higgsml-h4l-selection-v1"
            or hashlib.sha256(payload).hexdigest() != RESOURCE_HASHES[resource]):
        raise InputBindingError("sealed H4l selection protocol changed")
    if not isinstance(raw.get("selection"), dict):
        raise InputBindingError("H4l selection rules are missing")
    return H4lSelectionProtocol(raw["protocol_id"], raw["selection"], raw, payload)
