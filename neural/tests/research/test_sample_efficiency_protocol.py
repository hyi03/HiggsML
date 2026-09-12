"""Synthetic contracts only: these registration values are not a physics protocol."""
import copy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path

import pytest

from src.research.errors import ResearchError, ResearchStateError
from src.research.protocol import canonical, load_protocol
from src.research.representations import representation_features
from src.research.sample_efficiency_protocol import (
    CompactCandidateFreeze, SampleEfficiencyProtocol, freeze_compact_candidate,
    load_compact_candidate_freeze, load_sample_efficiency_protocol,
)


@pytest.fixture
def registration():
    base = load_protocol()
    metadata = {
        "discovery_prepared_artifact_ids": ["synthetic-discovery-prepared"],
        "discovery_report_artifact_ids": ["synthetic-report"],
        "selection_artifact_ids": ["synthetic-report"],
        "discovery_population_ids": ["synthetic-discovery"],
        "browsed_population_ids": ["synthetic-discovery"],
        "excluded_population_ids": ["synthetic-discovery"],
        "selection_rule_version": "synthetic-selection-v1",
        "selection_reason": "Test fixture; no scientific candidate selected",
        "evidence_status": "exploratory_only",
        "delta_w68": 0.1,
        "delta_source": "synthetic-test-only-not-a-registered-margin",
    }
    freeze = freeze_compact_candidate(metadata, groups=["A", "B"], base_protocol=base)
    raw = {
        "schema_version": "h4l-sample-efficiency-protocol-v1",
        "protocol_id": "synthetic-software-test-only",
        "base_research_protocol_sha256": base.digest,
        "prepared_artifact_id": "synthetic-learning-prepared",
        "population_id": "synthetic-learning",
        "compact_candidate_freeze_artifact_id": "synthetic-freeze-run",
        "compact_candidate_freeze_sha256": freeze.digest,
        "representations": ["decay7", "compact:AB", "engineered19"],
        "sample_fractions": [0.25, 0.5, 1.0],
        "sample_draw_seeds": [100, 101],
        "network_seeds": [42, 43, 44, 45, 46],
        "subset_algorithm": {
            "id": "stratified_group_sha256_prefix_v1", "unit": "event_group_id",
            "stratify_by": "label", "hash": "sha256", "rounding": "floor_per_label",
            "nesting": "shared_sorted_prefix", "full_endpoint": "single_full_identity",
            "min_groups_per_label": 2, "min_effective_count": 2.0,
        },
        "primary_metric": {"id": "W68_Asimov_mu1_T1", "direction": "lower_is_better", "transform": "raw"},
        "pairing_keys": ["sample_fraction", "sample_draw_seed_or_full", "network_seed", "architecture_variant"],
        "template_policy": "batch_common_mass_grid_v1",
        "noninferiority": {
            "delta_w68": metadata["delta_w68"], "delta_source": metadata["delta_source"],
            "confidence_level": 0.95, "ci_algorithm": "paired_event_group_percentile_v1",
            "interval": "two_sided_equal_tailed", "bootstrap_unit": "event_group_id",
            "bootstrap_replicates": 20, "bootstrap_seed": 300,
            "decision": "upper_ci_le_delta",
        },
        "evaluation_uncertainty": {"method": "paired_event_group_bootstrap_v1", "role": "validation",
            "replicates": 20, "seed": 200, "unit": "event_group_id", "metric": "absolute_weight_auc"},
        "calibration_uncertainty": {"method": "not_estimated", "replicates": 0, "seed": None},
        "capacity_control": {"enabled": True, "architecture_variant": "match_engineered19_parameter_count_v1",
            "width_rule": "nearest_positive_integer_ties_lower_5568_over_d_plus_67",
            "sample_fractions": [1.0], "network_seeds": [42]},
        "cdf_check": {"enabled": True, "transform": "physical",
            "representations": ["decay7", "compact:AB", "engineered19"], "sample_fractions": [1.0]},
        "quality_target": {"enabled": False, "w68": None,
            "interpolation": "observed_monotone_linear_no_extrapolation_v1"},
        "assessment_access": {"discovery": "forbidden", "learning_curve": "forbidden",
            "confirmation": "independent_population_claim_before_decode",
            "claim_namespace": "h4l-sample-efficiency-confirmation-v1", "repeat": "same_freeze_explicit_only"},
        "failure_policy": {"failed_cells": "retain", "redraw": False, "impute": False,
            "missing_pair": "paired_cell_missing", "incomplete_ledger": "learning_curve_incomplete",
            "unknown_exception_exit_code": 70},
    }
    bindings = dict(base_protocol=base, prepared_artifact_id=raw["prepared_artifact_id"],
        population_id=raw["population_id"], compact_freeze=freeze,
        compact_freeze_artifact_id=raw["compact_candidate_freeze_artifact_id"])
    return raw, bindings, metadata


def test_bound_roundtrip_digest_and_defensive_copies(registration, tmp_path):
    raw, bindings, _ = registration
    original = copy.deepcopy(raw)
    protocol = SampleEfficiencyProtocol(raw, **bindings)
    assert protocol.digest == hashlib.sha256(canonical(original)).hexdigest()
    assert SampleEfficiencyProtocol(dict(reversed(list(raw.items()))), **bindings).digest == protocol.digest
    raw["sample_draw_seeds"].append(102)
    detached = protocol.to_dict()
    detached["sample_draw_seeds"].clear()
    assert protocol["sample_draw_seeds"] == [100, 101]
    with pytest.raises(FrozenInstanceError):
        protocol.payload = b"{}"
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(original), encoding="utf-8")
    assert load_sample_efficiency_protocol(path, **bindings) == protocol
    freeze = bindings["compact_freeze"]
    path.write_text(json.dumps(freeze.to_dict()), encoding="utf-8")
    assert load_compact_candidate_freeze(path, base_protocol=bindings["base_protocol"]) == freeze
    assert freeze["candidate"]["ordered_inputs"] == list(representation_features("engineered19", groups=["A", "B"]))
    assert freeze["candidate"]["input_dimension"] == 13


def dict_paths(value, prefix=()):
    yield prefix
    for key, child in value.items():
        if isinstance(child, dict):
            yield from dict_paths(child, prefix + (key,))


def at(value, path):
    for key in path:
        value = value[key]
    return value


def test_all_object_levels_reject_unknown_and_every_missing_field(registration):
    raw, bindings, _ = registration
    for path in dict_paths(raw):
        broken = copy.deepcopy(raw)
        at(broken, path)["surprise"] = 1
        with pytest.raises(ResearchError):
            SampleEfficiencyProtocol(broken, **bindings)
        for key in at(raw, path):
            broken = copy.deepcopy(raw)
            del at(broken, path)[key]
            with pytest.raises(ResearchError):
                SampleEfficiencyProtocol(broken, **bindings)


@pytest.mark.parametrize("path,value", [
    (("schema_version",), "h4l-sample-efficiency-protocol-v2"),
    (("sample_fractions",), [0.5, 0.25, 1.0]), (("sample_fractions",), [0.5, 0.5, 1.0]),
    (("sample_fractions",), [0.25, 0.5]), (("sample_fractions",), [1.0]),
    (("sample_fractions",), [0, 1.0]), (("sample_fractions",), [0.25, 1]),
    (("sample_fractions",), [True, 1.0]),
    (("sample_fractions",), [float("nan"), 1.0]), (("sample_fractions",), [0.5, float("inf")]),
    (("sample_draw_seeds",), [100, 100]), (("sample_draw_seeds",), []),
    (("sample_draw_seeds",), [101, 100]), (("sample_draw_seeds",), [42]),
    (("sample_draw_seeds",), [-1]), (("sample_draw_seeds",), [2**32]),
    (("network_seeds",), [42]), (("network_seeds",), [42, 43, 44, 45, 47]),
    (("representations",), ["decay7", "compact:CD", "engineered19"]),
    (("representations",), ["compact:" + x for x in ["A", "B", "C", "D", "AB", "AC", "AD", "BC", "BD", "CD", "ABC", "ABD", "ACD", "BCD", "ABCD"]]),
    (("subset_algorithm", "rounding"), "ceil"), (("subset_algorithm", "unit"), "row"),
    (("subset_algorithm", "min_groups_per_label"), True), (("subset_algorithm", "min_effective_count"), 0),
    (("noninferiority", "delta_w68"), 0.2), (("noninferiority", "delta_source"), "another"),
    (("noninferiority", "confidence_level"), 1.0), (("noninferiority", "bootstrap_replicates"), 1),
    (("noninferiority", "bootstrap_seed"), 200), (("noninferiority", "ci_algorithm"), "unknown"),
    (("evaluation_uncertainty", "seed"), 100), (("evaluation_uncertainty", "seed"), 42),
    (("evaluation_uncertainty", "role"), "assessment"), (("evaluation_uncertainty", "metric"), "W68"),
    (("calibration_uncertainty", "replicates"), False), (("calibration_uncertainty", "seed"), 200),
    (("capacity_control", "width_rule"), [64, 128]), (("capacity_control", "network_seeds"), [99]),
    (("capacity_control", "sample_fractions"), [0.1]), (("capacity_control", "enabled"), 1),
    (("cdf_check", "sample_fractions"), [0.25, 0.5, 1.0]), (("cdf_check", "sample_fractions"), [0.5]),
    (("cdf_check", "representations"), ["compact:AB"]), (("cdf_check", "enabled"), False),
    (("quality_target", "w68"), 1.0), (("quality_target", "interpolation"), "power_law"),
    (("assessment_access", "learning_curve"), "allowed"), (("failure_policy", "redraw"), True),
    (("failure_policy", "unknown_exception_exit_code"), 70.0),
])
def test_rejects_changed_rules_and_invalid_values(registration, path, value):
    raw, bindings, _ = registration
    at(raw, path[:-1])[path[-1]] = value
    with pytest.raises(ResearchError):
        SampleEfficiencyProtocol(raw, **bindings)


@pytest.mark.parametrize("field", ["base_research_protocol_sha256", "prepared_artifact_id", "population_id",
    "compact_candidate_freeze_artifact_id", "compact_candidate_freeze_sha256"])
def test_binding_mismatches(registration, field):
    raw, bindings, _ = registration
    raw[field] = "e" * 64
    with pytest.raises(ResearchError):
        SampleEfficiencyProtocol(raw, **bindings)


def test_missing_freeze_has_explicit_input_failure(registration):
    raw, bindings, _ = registration
    bindings["compact_freeze"] = None
    with pytest.raises(ResearchError) as raised:
        SampleEfficiencyProtocol(raw, **bindings)
    assert not isinstance(raised.value, ResearchStateError)
    assert raised.value.status == "compact_candidate_not_frozen"
    assert raised.value.exit_code == 3


def test_freeze_payload_digest_cannot_substitute_artifact_identity(registration):
    raw, bindings, _ = registration
    # Both supplied and expected IDs match; simple per-field binding is insufficient.
    raw["compact_candidate_freeze_artifact_id"] = bindings["compact_freeze"].digest
    bindings["compact_freeze_artifact_id"] = bindings["compact_freeze"].digest
    with pytest.raises(ResearchError, match="cannot substitute"):
        SampleEfficiencyProtocol(raw, **bindings)


def test_explicit_optional_controls_and_digest_changes(registration):
    raw, bindings, _ = registration
    before = SampleEfficiencyProtocol(raw, **bindings)
    raw["capacity_control"].update(enabled=False, sample_fractions=[], network_seeds=[])
    raw["cdf_check"].update(enabled=False, sample_fractions=[])
    raw["quality_target"].update(enabled=True, w68=1.5)
    raw["sample_draw_seeds"] = [102]
    assert SampleEfficiencyProtocol(raw, **bindings).digest != before.digest


def reseal(raw):
    raw["payload_sha256"] = hashlib.sha256(canonical({k: v for k, v in raw.items() if k != "payload_sha256"})).hexdigest()
    return raw


def test_freeze_rejects_tampering_even_with_recomputed_digest(registration):
    _, bindings, _ = registration
    frozen = bindings["compact_freeze"].to_dict()
    constructor = lambda raw: CompactCandidateFreeze(raw, base_protocol=bindings["base_protocol"])
    for path in dict_paths(frozen):
        broken = copy.deepcopy(frozen)
        at(broken, path)["unknown"] = 1
        with pytest.raises(ResearchError): constructor(reseal(broken))
        for key in at(frozen, path):
            broken = copy.deepcopy(frozen)
            del at(broken, path)[key]
            with pytest.raises(ResearchError): constructor(broken)
    for path, value in [
        (("candidate", "input_dimension"), 12), (("candidate", "input_dimension"), 13.0),
        (("candidate", "groups"), ["B", "A"]), (("candidate", "groups"), []),
        (("candidate", "groups"), list("ABCD")), (("candidate", "ordered_inputs"), ["m4l"]),
        (("candidate", "representation_id"), "compact:AC"),
        (("status",), "selected"), (("evidence_status",), "confirmed"),
        (("delta_w68",), 0), (("delta_source",), " "),
        (("excluded_population_ids",), ["unrelated"]), (("browsed_population_ids",), ["unrelated"]),
        (("selection_artifact_ids",), ["unrelated"]), (("discovery_prepared_artifact_ids",), []),
    ]:
        broken = copy.deepcopy(frozen)
        at(broken, path[:-1])[path[-1]] = value
        with pytest.raises(ResearchError): constructor(reseal(broken))
    frozen["selection_reason"] = "tampered"
    with pytest.raises(ResearchError): constructor(frozen)


def test_new_self_consistent_freeze_cannot_change_overlay_margin_or_candidate(registration):
    raw, bindings, metadata = registration
    metadata["delta_w68"] = 0.2
    new = freeze_compact_candidate(metadata, groups=["A"], base_protocol=bindings["base_protocol"])
    bindings["compact_freeze"] = new
    raw["compact_candidate_freeze_sha256"] = new.digest
    with pytest.raises(ResearchError): SampleEfficiencyProtocol(raw, **bindings)
    raw["representations"][1] = "compact:A"
    raw["cdf_check"]["representations"][1] = "compact:A"
    with pytest.raises(ResearchError): SampleEfficiencyProtocol(raw, **bindings)


def test_json_errors_and_duplicates_at_all_levels(registration, tmp_path):
    raw, bindings, _ = registration
    path = tmp_path / "bad.json"
    for obj in [raw, bindings["compact_freeze"].to_dict()]:
        loader = (lambda: load_sample_efficiency_protocol(path, **bindings)) if "protocol_id" in obj else (
            lambda: load_compact_candidate_freeze(path, base_protocol=bindings["base_protocol"]))
        for object_path in dict_paths(obj):
            key = next(iter(at(obj, object_path)))
            token = json.dumps(key) + ":"
            encoded = json.dumps(obj).replace(token, token + "null," + token, 1)
            path.write_text(encoded, encoding="utf-8")
            with pytest.raises(ResearchError): loader()
        for encoded in ['{"x": NaN}', '{"x": Infinity}', '{', '[]', 'null']:
            path.write_text(encoded, encoding="utf-8")
            with pytest.raises(ResearchError): loader()
    path.unlink()
    with pytest.raises(ResearchError): load_sample_efficiency_protocol(path, **bindings)


def test_unfilled_template_is_not_a_protocol(registration):
    _, bindings, _ = registration
    template = Path(__file__).resolve().parents[2] / "config/research_sample_efficiency_protocol_v1.json"
    with pytest.raises(ResearchError): load_sample_efficiency_protocol(template, **bindings)
