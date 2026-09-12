"""Strict experiment lineage shared by sample-efficiency downstream artifacts."""
from __future__ import annotations

from dataclasses import dataclass
import json
import weakref

from .errors import ResearchError
from .protocol import canonical


LINEAGE_SCHEMA = "h4l-experiment-lineage-v1"
LINEAGE_FIELDS = (
    "schema_version", "source_model_artifact_id", "model_id", "base_research_protocol_sha256",
    "sample_efficiency_protocol_sha256", "prepared_artifact_id", "population_id",
    "training_subset_artifact_id", "training_subset_id", "membership_digest", "representation_id",
    "sample_fraction_target", "sample_draw_seed", "sample_draw_seed_or_full", "network_seed",
    "architecture_variant", "transform", "experiment_cell_id", "pairing_id",
)
_MINT_TOKEN = object()
_MINTED = weakref.WeakSet()


def _fail(message):
    raise ResearchError(message, status="training_subset_binding_mismatch")


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True, init=False)
class ExperimentLineage:
    payload: bytes

    def __init__(self, raw, *, _token=None):
        if _token is not _MINT_TOKEN:
            _fail("experiment lineage must come from a verified model-run reader")
        if type(raw) is not dict or tuple(sorted(raw)) != tuple(sorted(LINEAGE_FIELDS)):
            _fail("invalid experiment lineage schema")
        if raw.get("schema_version") != LINEAGE_SCHEMA or raw.get("transform") != "raw":
            _fail("unsupported experiment lineage stage")
        for field in ("source_model_artifact_id", "model_id", "base_research_protocol_sha256",
                      "sample_efficiency_protocol_sha256", "prepared_artifact_id", "population_id",
                      "training_subset_artifact_id", "training_subset_id", "membership_digest",
                      "experiment_cell_id", "pairing_id"):
            if not _sha(raw.get(field)):
                _fail(f"invalid experiment lineage digest: {field}")
        if (type(raw.get("representation_id")) is not str or not raw["representation_id"]
                or type(raw.get("sample_fraction_target")) is not float
                or type(raw.get("network_seed")) is not int
                or type(raw.get("architecture_variant")) is not str):
            _fail("invalid experiment lineage value type")
        full = raw["sample_fraction_target"] == 1.0
        if ((full and (raw["sample_draw_seed"] is not None or raw["sample_draw_seed_or_full"] != "full"))
                or (not full and (type(raw["sample_draw_seed"]) is not int
                                  or raw["sample_draw_seed_or_full"] != raw["sample_draw_seed"]))):
            _fail("experiment lineage draw canonicalization mismatch")
        object.__setattr__(self, "payload", canonical(raw))
        _MINTED.add(self)

    def to_dict(self):
        return json.loads(self.payload)

    def __getitem__(self, key):
        return self.to_dict()[key]


def _lineage_from_verified_model(model, *, source_model_artifact_id):
    raw = {"schema_version": LINEAGE_SCHEMA, "source_model_artifact_id": source_model_artifact_id,
           "model_id": model["model_id"], "base_research_protocol_sha256": model["base_research_protocol_sha256"],
           "sample_efficiency_protocol_sha256": model["sample_efficiency_protocol_sha256"],
           "prepared_artifact_id": model["prepared_artifact_id"], "population_id": model["population_id"],
           "training_subset_artifact_id": model["training_subset_artifact_id"],
           "training_subset_id": model["training_subset_id"], "membership_digest": model["membership_digest"],
           "representation_id": model["representation_id"], "sample_fraction_target": model["sample_fraction_target"],
           "sample_draw_seed": model["sample_draw_seed"], "sample_draw_seed_or_full": model["sample_draw_seed_or_full"],
           "network_seed": model["network_seed"], "architecture_variant": model["architecture_variant"],
           "transform": "raw", "experiment_cell_id": model["experiment_cell_id"], "pairing_id": model["pairing_id"]}
    return ExperimentLineage(raw, _token=_MINT_TOKEN)


def is_trusted_lineage(value):
    return isinstance(value, ExperimentLineage) and value in _MINTED


def bind_experiment_lineage(payload, lineage, *, transform="raw"):
    if not is_trusted_lineage(lineage) or transform != "raw":
        _fail("sample-efficiency lineage supports raw stage only")
    if type(payload) is not dict or "experiment_lineage" in payload:
        _fail("invalid downstream payload for experiment lineage")
    return {**payload, "experiment_lineage": lineage.to_dict()}


def require_experiment_lineage(payload, expected):
    if not is_trusted_lineage(expected) or type(payload) is not dict:
        _fail("trusted experiment lineage is required")
    actual = payload.get("experiment_lineage")
    if type(actual) is not dict or canonical(actual) != expected.payload:
        _fail("downstream experiment lineage mismatch")
    return expected
