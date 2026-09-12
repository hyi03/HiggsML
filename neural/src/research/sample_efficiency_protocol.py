"""Strict sample-efficiency metadata contracts, without experiment execution.

Payload validation proves internal consistency, not the provenance of caller-supplied
artifact IDs. A future workflow must verify receipts before using these contracts.
No event reader, assessment claim, model fitting, or scientific default lives here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from .errors import ResearchError
from .protocol import ResearchProtocol, canonical, validate_protocol
from .representations import representation_features


PROTOCOL_SCHEMA = "h4l-sample-efficiency-protocol-v1"
FREEZE_SCHEMA = "h4l-compact-candidate-freeze-v1"
_FREEZE_METADATA = (
    "discovery_prepared_artifact_ids", "discovery_report_artifact_ids", "selection_artifact_ids",
    "discovery_population_ids", "browsed_population_ids", "excluded_population_ids",
    "selection_rule_version", "selection_reason", "evidence_status", "delta_w68", "delta_source",
)
_OVERLAY_KEYS = (
    "schema_version", "protocol_id", "base_research_protocol_sha256", "prepared_artifact_id",
    "population_id", "compact_candidate_freeze_artifact_id", "compact_candidate_freeze_sha256",
    "representations", "sample_fractions", "sample_draw_seeds", "network_seeds", "subset_algorithm",
    "primary_metric", "pairing_keys", "template_policy", "noninferiority", "evaluation_uncertainty",
    "calibration_uncertainty", "capacity_control", "cdf_check", "quality_target",
    "assessment_access", "failure_policy",
)


def _json_value(value):
    """Reject Python coercions before serialization can turn them into valid JSON."""
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_value(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_value(item)
        return
    raise ResearchError("sample-efficiency payload must contain finite JSON values")


def _copy(value):
    _json_value(value)
    try:
        return json.loads(canonical(value))
    except (ValueError, TypeError, OverflowError) as exc:
        raise ResearchError("invalid sample-efficiency JSON value") from exc


def _keys(value, expected, name):
    if type(value) is not dict or set(value) != set(expected):
        raise ResearchError(f"{name} has missing or unknown fields")


def _equal(value, expected, name):
    # In particular, False must not stand in for 0, nor 70.0 for exit code 70.
    if canonical(value) != canonical(expected):
        raise ResearchError(f"unsupported {name}")


def _text(value, name):
    if type(value) is not str or not value or value.strip() != value:
        raise ResearchError(f"{name} must be nonempty text without surrounding whitespace")


def _sha(value, name):
    _text(value, name)
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ResearchError(f"{name} must be a lowercase SHA-256 digest")


def _number(value, name, *, minimum=0, maximum=None, integer=False, strict=True):
    if type(value) not in (int, float) or (integer and type(value) is not int):
        raise ResearchError(f"{name} has invalid numeric type")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ResearchError(f"{name} must be finite")
    if (value <= minimum if strict else value < minimum) or (maximum is not None and value > maximum):
        raise ResearchError(f"{name} outside registered range")


def _seed(value, name):
    _number(value, name, integer=True, strict=False, maximum=2**32 - 1)


def _ordered_list(value, name, check, *, minimum_length=1):
    if type(value) is not list or len(value) < minimum_length:
        raise ResearchError(f"{name} must be an explicit ordered list")
    for item in value:
        check(item, name)
    if any(a >= b for a, b in zip(value, value[1:])):
        raise ResearchError(f"{name} must be strictly increasing without duplicates")


def _fixed_object(value, fixed, name, extra=()):
    _keys(value, (*fixed, *extra), name)
    for key, expected in fixed.items():
        _equal(value[key], expected, f"{name}.{key}")


def _base_digest(base_protocol):
    if not isinstance(base_protocol, ResearchProtocol):
        raise ResearchError("base_protocol must be a validated ResearchProtocol")
    try:
        raw = _copy(base_protocol.to_dict())
        if type(raw) is not dict:
            raise ResearchError("base protocol must be an object")
        validate_protocol(raw, raw.get("dataset"))
        return hashlib.sha256(canonical(raw)).hexdigest()
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        if isinstance(exc, ResearchError):
            raise
        raise ResearchError("invalid base research protocol") from exc


def _candidate(groups):
    if (type(groups) is not list or not 0 < len(groups) < 4
            or any(type(g) is not str or g not in "ABCD" or len(g) != 1 for g in groups)
            or groups != sorted(set(groups))):
        raise ResearchError("compact groups must be a canonical nonempty proper ABCD subset")
    inputs = list(representation_features("engineered19", groups=groups))
    return dict(representation_id="compact:" + "".join(groups), representation="engineered19",
                groups=groups, ordered_inputs=inputs, input_dimension=len(inputs))


def _freeze_digest(raw):
    return hashlib.sha256(canonical({k: v for k, v in raw.items() if k != "payload_sha256"})).hexdigest()


def _validate_freeze(raw, base_protocol):
    _keys(raw, (*_FREEZE_METADATA, "schema_version", "status", "base_research_protocol_sha256",
                "candidate", "reference_representation", "payload_sha256"), "compact freeze")
    _equal(raw["schema_version"], FREEZE_SCHEMA, "freeze schema")
    _equal(raw["status"], "frozen", "freeze status")
    _sha(raw["base_research_protocol_sha256"], "freeze base digest")
    _equal(raw["base_research_protocol_sha256"], _base_digest(base_protocol), "freeze base binding")
    _keys(raw["candidate"], ("representation_id", "representation", "groups", "ordered_inputs", "input_dimension"), "candidate")
    _equal(raw["candidate"], _candidate(raw["candidate"]["groups"]), "candidate registry binding")
    _equal(raw["reference_representation"], "engineered19", "reference representation")
    _equal(raw["evidence_status"], "exploratory_only", "freeze evidence status")
    for field in _FREEZE_METADATA[:6]:
        _ordered_list(raw[field], field, _text)
    if not set(raw["discovery_report_artifact_ids"]) <= set(raw["selection_artifact_ids"]):
        raise ResearchError("selection history omits discovery reports")
    if not (set(raw["discovery_population_ids"]) <= set(raw["browsed_population_ids"])
            <= set(raw["excluded_population_ids"])):
        raise ResearchError("population history is not contained in confirmation exclusions")
    for key in ("selection_rule_version", "selection_reason", "delta_source"):
        _text(raw[key], key)
    _number(raw["delta_w68"], "freeze delta_w68")
    _sha(raw["payload_sha256"], "freeze payload digest")
    _equal(raw["payload_sha256"], _freeze_digest(raw), "freeze payload digest")


@dataclass(frozen=True, init=False)
class CompactCandidateFreeze:
    """Immutable, validated payload; digest excludes its own payload_sha256 field."""

    payload: bytes

    def __init__(self, raw, *, base_protocol):
        snapshot = _copy(raw)
        _validate_freeze(snapshot, base_protocol)
        object.__setattr__(self, "payload", canonical(snapshot))

    def to_dict(self):
        return json.loads(self.payload)

    def __getitem__(self, key):
        return self.to_dict()[key]

    @property
    def digest(self):
        return self["payload_sha256"]


def freeze_compact_candidate(metadata, *, groups, base_protocol):
    """Build from explicit metadata and groups; never select from a result report."""
    raw = _copy(metadata)
    _keys(raw, _FREEZE_METADATA, "freeze metadata")
    raw.update(schema_version=FREEZE_SCHEMA, status="frozen",
               base_research_protocol_sha256=_base_digest(base_protocol),
               candidate=_candidate(_copy(groups)), reference_representation="engineered19")
    raw["payload_sha256"] = _freeze_digest(raw)
    return CompactCandidateFreeze(raw, base_protocol=base_protocol)


def _fractions(value, name, *, minimum_length=1):
    def check_fraction(item, item_name):
        if type(item) is not float:
            raise ResearchError(f"{item_name} entries must be JSON floats")
        _number(item, item_name, maximum=1)

    _ordered_list(value, name, check_fraction, minimum_length=minimum_length)


def _control_points(control, grid, name):
    if type(control["enabled"]) is not bool:
        raise ResearchError(f"{name}.enabled must be boolean")
    points = control["sample_fractions"]
    if not control["enabled"]:
        _equal(points, [], f"disabled {name} points")
        return
    _fractions(points, f"{name} fractions")
    if len(points) > 2 or not set(points) <= set(grid):
        raise ResearchError(f"{name} requires at most two registered grid points")


def _validate_overlay(raw, *, base_protocol, prepared_artifact_id, population_id,
                      compact_freeze, compact_freeze_artifact_id):
    if compact_freeze is None:
        raise ResearchError("compact candidate must be explicitly frozen", status="compact_candidate_not_frozen")
    if not isinstance(compact_freeze, CompactCandidateFreeze):
        raise ResearchError("compact_freeze must be a validated CompactCandidateFreeze")
    _keys(raw, _OVERLAY_KEYS, "sample-efficiency protocol")
    _equal(raw["schema_version"], PROTOCOL_SCHEMA, "sample-efficiency schema")
    _text(raw["protocol_id"], "protocol_id")
    freeze = compact_freeze.to_dict()
    _validate_freeze(freeze, base_protocol)
    _sha(raw["base_research_protocol_sha256"], "overlay base digest")
    _sha(raw["compact_candidate_freeze_sha256"], "overlay freeze digest")
    bindings = dict(base_research_protocol_sha256=_base_digest(base_protocol),
                    prepared_artifact_id=prepared_artifact_id, population_id=population_id,
                    compact_candidate_freeze_artifact_id=compact_freeze_artifact_id,
                    compact_candidate_freeze_sha256=compact_freeze.digest)
    for field, expected in bindings.items():
        _text(expected, f"expected {field}")
        _text(raw[field], field)
        _equal(raw[field], expected, f"{field} binding")
    if raw["compact_candidate_freeze_artifact_id"] == raw["compact_candidate_freeze_sha256"]:
        raise ResearchError("freeze artifact ID cannot substitute the freeze payload digest")
    representations = ["decay7", freeze["candidate"]["representation_id"], "engineered19"]
    _equal(raw["representations"], representations, "three frozen representations")
    _fractions(raw["sample_fractions"], "sample_fractions", minimum_length=2)
    if raw["sample_fractions"][-1] != 1:
        raise ResearchError("sample_fractions must include the full endpoint")
    _ordered_list(raw["sample_draw_seeds"], "sample_draw_seeds", _seed)
    _equal(raw["network_seeds"], [42, 43, 44, 45, 46], "network seeds")
    subset = raw["subset_algorithm"]
    _fixed_object(subset, {
        "id": "stratified_group_sha256_prefix_v1", "unit": "event_group_id",
        "stratify_by": "label", "hash": "sha256", "rounding": "floor_per_label",
        "nesting": "shared_sorted_prefix", "full_endpoint": "single_full_identity",
    }, "subset_algorithm", ("min_groups_per_label", "min_effective_count"))
    _number(subset["min_groups_per_label"], "min_groups_per_label", integer=True)
    _number(subset["min_effective_count"], "min_effective_count")
    _fixed_object(raw["primary_metric"], {"id": "W68_Asimov_mu1_T1", "direction": "lower_is_better", "transform": "raw"}, "primary_metric")
    _equal(raw["pairing_keys"], ["sample_fraction", "sample_draw_seed_or_full", "network_seed", "architecture_variant"], "pairing_keys")
    _equal(raw["template_policy"], "batch_common_mass_grid_v1", "template_policy")
    noninf = raw["noninferiority"]
    _fixed_object(noninf, {
        "ci_algorithm": "paired_event_group_percentile_v1", "interval": "two_sided_equal_tailed",
        "bootstrap_unit": "event_group_id", "decision": "upper_ci_le_delta",
    }, "noninferiority", ("delta_w68", "delta_source", "confidence_level", "bootstrap_replicates", "bootstrap_seed"))
    _number(noninf["delta_w68"], "delta_w68")
    _text(noninf["delta_source"], "delta_source")
    if noninf["delta_w68"] != freeze["delta_w68"] or noninf["delta_source"] != freeze["delta_source"]:
        raise ResearchError("noninferiority margin/source differs from compact freeze")
    _number(noninf["confidence_level"], "confidence_level", maximum=1)
    if noninf["confidence_level"] == 1:
        raise ResearchError("confidence_level must be below one")
    _number(noninf["bootstrap_replicates"], "bootstrap_replicates", minimum=1, integer=True)
    _seed(noninf["bootstrap_seed"], "bootstrap_seed")
    evaluation = raw["evaluation_uncertainty"]
    _fixed_object(evaluation, {"method": "paired_event_group_bootstrap_v1", "role": "validation",
        "unit": "event_group_id", "metric": "absolute_weight_auc"}, "evaluation_uncertainty", ("replicates", "seed"))
    _number(evaluation["replicates"], "evaluation replicates", minimum=1, integer=True)
    _seed(evaluation["seed"], "evaluation seed")
    seeds = raw["sample_draw_seeds"] + raw["network_seeds"] + [noninf["bootstrap_seed"], evaluation["seed"]]
    if len(seeds) != len(set(seeds)):
        raise ResearchError("draw, network, evaluation and confirmation seeds must be separate")
    _fixed_object(raw["calibration_uncertainty"], {"method": "not_estimated", "replicates": 0, "seed": None}, "calibration_uncertainty")
    capacity = raw["capacity_control"]
    _fixed_object(capacity, {"architecture_variant": "match_engineered19_parameter_count_v1",
        "width_rule": "nearest_positive_integer_ties_lower_5568_over_d_plus_67"},
        "capacity_control", ("enabled", "sample_fractions", "network_seeds"))
    _control_points(capacity, raw["sample_fractions"], "capacity")
    if capacity["enabled"]:
        _ordered_list(capacity["network_seeds"], "capacity network_seeds", _seed)
        if not set(capacity["network_seeds"]) <= set(raw["network_seeds"]):
            raise ResearchError("capacity seeds outside registered network seeds")
    else:
        _equal(capacity["network_seeds"], [], "disabled capacity seeds")
    cdf = raw["cdf_check"]
    _fixed_object(cdf, {"transform": "physical", "representations": representations}, "cdf_check", ("enabled", "sample_fractions"))
    _control_points(cdf, raw["sample_fractions"], "CDF")
    if cdf["enabled"] and cdf["sample_fractions"][-1] != 1:
        raise ResearchError("CDF points must include full endpoint")
    target = raw["quality_target"]
    _fixed_object(target, {"interpolation": "observed_monotone_linear_no_extrapolation_v1"}, "quality_target", ("enabled", "w68"))
    if type(target["enabled"]) is not bool:
        raise ResearchError("quality_target.enabled must be boolean")
    if target["enabled"]:
        _number(target["w68"], "quality target W68")
    else:
        _equal(target["w68"], None, "disabled quality target")
    _fixed_object(raw["assessment_access"], {
        "discovery": "forbidden", "learning_curve": "forbidden",
        "confirmation": "independent_population_claim_before_decode",
        "claim_namespace": "h4l-sample-efficiency-confirmation-v1", "repeat": "same_freeze_explicit_only",
    }, "assessment_access")
    _fixed_object(raw["failure_policy"], {
        "failed_cells": "retain", "redraw": False, "impute": False,
        "missing_pair": "paired_cell_missing", "incomplete_ledger": "learning_curve_incomplete",
        "unknown_exception_exit_code": 70,
    }, "failure_policy")


@dataclass(frozen=True, init=False)
class SampleEfficiencyProtocol:
    """Construction requires all bindings; payload bytes cannot bypass validation."""

    payload: bytes

    def __init__(self, raw, *, base_protocol, prepared_artifact_id, population_id,
                 compact_freeze, compact_freeze_artifact_id):
        snapshot = _copy(raw)
        _validate_overlay(snapshot, base_protocol=base_protocol, prepared_artifact_id=prepared_artifact_id,
                          population_id=population_id, compact_freeze=compact_freeze,
                          compact_freeze_artifact_id=compact_freeze_artifact_id)
        object.__setattr__(self, "payload", canonical(snapshot))

    def to_dict(self):
        return json.loads(self.payload)

    def __getitem__(self, key):
        return self.to_dict()[key]

    @property
    def digest(self):
        return hashlib.sha256(self.payload).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResearchError("duplicate sample-efficiency JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ResearchError("nonfinite sample-efficiency JSON value")


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                          object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (OSError, ValueError, TypeError) as exc:
        if isinstance(exc, ResearchError):
            raise
        raise ResearchError("invalid sample-efficiency JSON input") from exc


def load_compact_candidate_freeze(path, *, base_protocol):
    return CompactCandidateFreeze(_read_json(path), base_protocol=base_protocol)


def load_sample_efficiency_protocol(path, *, base_protocol, prepared_artifact_id, population_id,
                                    compact_freeze, compact_freeze_artifact_id):
    return SampleEfficiencyProtocol(_read_json(path), base_protocol=base_protocol,
        prepared_artifact_id=prepared_artifact_id, population_id=population_id,
        compact_freeze=compact_freeze, compact_freeze_artifact_id=compact_freeze_artifact_id)
