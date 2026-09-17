import pytest
import pandas as pd

from higgsml.artifacts import digest_json
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference.seed_blocks import canonical_seed_blocks, pairing_contract
from higgsml.inference.seed_evaluation import (
    evaluate_seed_block, evaluate_seed_t2, make_t2_outer_multiplicities,
)
from higgsml.inference.likelihood import run_t2_procedure


def inputs(block):
    templates = {key: {"candidate_id": key} for key in block.candidate_keys}
    bundles = {key: {"model_id": key} for key in block.candidate_keys}
    return {"status": "valid", "templates": templates}, bundles


def test_seed_block_envelope_preserves_registered_500_fit_budget(monkeypatch):
    block = canonical_seed_blocks()[0]
    grid, bundles = inputs(block)
    calls = []

    def fake_infer(selected_grid, selected_bundles, parent, protocol, **kwargs):
        calls.append(kwargs)
        assert tuple(selected_grid["templates"]) == block.candidate_keys
        assert kwargs["seed_block"] == block and kwargs["parent_role"] == "template"
        return {key: {"status": "valid", "attempted_fits": 500,
                      "completed_fits": 500, "valid_fits": 500,
                      "missing_fit_indexes": [],
                      "joint_support": {"qualification": "valid"}}
                for key in block.candidate_keys}

    monkeypatch.setattr("higgsml.inference.seed_evaluation.infer_assessment", fake_infer)
    result = evaluate_seed_block(grid, bundles, object(), {}, block=block,
        stage="model-self", mu=1, count=500, toy_base_seed=91, layer="T0",
        t1_validation=None, prepared_id="p", freeze_id="f", workers=4)
    assert result["scientific_status"] == "valid"
    assert result["generated_physical_toys"] == 500
    assert len(result["candidate_results"]) == 16
    assert {row["attempted_fits"] for row in result["candidate_results"]} == {500}
    assert calls[0]["physical_stream_id"] == result["rng"]["stream_id"]


def test_expected_support_failure_is_complete_scientific_terminal(monkeypatch):
    block = canonical_seed_blocks()[0]
    grid, bundles = inputs(block)
    monkeypatch.setattr("higgsml.inference.seed_evaluation.infer_assessment",
        lambda *a, **k: (_ for _ in ()).throw(ResearchStateError(
            "negative process rate", status="insufficient_statistics")))
    result = evaluate_seed_block(grid, bundles, object(), {}, block=block,
        stage="assessment", mu=0, count=3, toy_base_seed=1, layer="T0",
        t1_validation=None, prepared_id="p", freeze_id="f")
    assert result["execution_status"] == "complete"
    assert result["scientific_status"] == "insufficient_statistics"
    assert result["generated_physical_toys"] == 0
    assert all(row["attempted_fits"] == 0 for row in result["candidate_results"])
    assert all(row["missing_fit_indexes"] == [0, 1, 2] for row in result["candidate_results"])


def test_nonwhitelisted_state_is_not_converted_to_success(monkeypatch):
    block = canonical_seed_blocks()[0]
    grid, bundles = inputs(block)
    monkeypatch.setattr("higgsml.inference.seed_evaluation.infer_assessment",
        lambda *a, **k: (_ for _ in ()).throw(ResearchStateError(
            "bad binding", status="input_binding_failure")))
    with pytest.raises(ResearchStateError, match="bad binding"):
        evaluate_seed_block(grid, bundles, object(), {}, block=block,
            stage="assessment", mu=1, count=2, toy_base_seed=1, layer="T0",
            t1_validation=None, prepared_id="p", freeze_id="f")


def test_t2_outer_multiplicities_are_shared_and_deterministic():
    import pandas as pd
    calibration = pd.DataFrame({"event_group_id": ["a", "b", "c"]})
    digest = pairing_contract()["contract_digest"]
    left = make_t2_outer_multiplicities(calibration, contract_digest=digest,
        outer_replicas=20, toy_base_seed=42)
    right = make_t2_outer_multiplicities(calibration, contract_digest=digest,
        outer_replicas=20, toy_base_seed=42)
    assert left == right and len(left["multiplicities"]) == 20
    assert all(sum(row) == 3 for row in left["multiplicities"])


def test_t2_blocks_reuse_outer_plan_but_pass_different_training_seeds(monkeypatch):
    blocks = canonical_seed_blocks()[:2]
    seen = []

    def fake_t2(grid, bundles, calibration, template, mother, protocol, **kwargs):
        seen.append((kwargs["seed_block"].seed, kwargs["outer_multiplicities"]))
        candidates = {key: {"status": "valid", "attempted_fits": 100,
            "completed_fits": 100, "valid_fits": 100,
            "joint_support": {"qualification": "valid"}}
            for key in kwargs["seed_block"].candidate_keys}
        return {"status": "valid", "replicas": [
            {"replica": i, "status": "valid", "bootstrap_group_multiplicities": {"a": 1, "b": 1},
             "result": {"status": "valid", "candidates": candidates}}
            for i in range(20)]}

    monkeypatch.setattr("higgsml.inference.seed_evaluation.run_assessment_t2", fake_t2)
    rows = [[1, 1]] * 20
    outer = {"groups": ["a", "b"], "multiplicities": rows,
             "multiplicity_plan_digest": digest_json(rows)}
    protocol = {"inference": {"inner_toys": 100}}
    for block in blocks:
        grid, bundles = inputs(block)
        result = evaluate_seed_t2(grid, bundles, object(), object(), object(), protocol,
            block=block, mu=1, toy_base_seed=42, layer="T0", t1_validation=None,
            prepared_id="p", freeze_id="f", outer_multiplicities=outer)
        assert result["planned_outer"] == 20 and result["planned_inner_per_outer"] == 100
        assert all(row["attempted_fits"] == 2000 for row in result["candidate_results"])
        assert result["planned_toys_per_candidate"] == result["generated_physical_toys"] == 2000
        assert result["joint_support"]["qualification"] == "valid"
    assert seen == [(42, outer), (43, outer)]


def test_t2_outer_gate_failure_retains_planned_denominator_with_zero_attempts(monkeypatch):
    block = canonical_seed_blocks()[0]
    grid, bundles = inputs(block)
    monkeypatch.setattr("higgsml.inference.seed_evaluation.run_assessment_t2",
        lambda *a, **k: {"status": "inference_incomplete", "replicas": [
            {"replica": i, "status": "insufficient_statistics", "error": "mapping failed",
             "bootstrap_group_multiplicities": {"a": 1, "b": 1}}
            for i in range(20)]})
    rows = [[1, 1]] * 20
    outer = {"groups": ["a", "b"], "multiplicities": rows,
             "multiplicity_plan_digest": digest_json(rows)}
    result = evaluate_seed_t2(grid, bundles, object(), object(), object(),
        {"inference": {"inner_toys": 100}}, block=block, mu=1, toy_base_seed=42,
        layer="T0", t1_validation=None, prepared_id="p", freeze_id="f",
        outer_multiplicities=outer)
    assert result["planned_toys_per_candidate"] == 2000
    assert result["generated_physical_toys"] == 0
    assert all(row["attempted_fits"] == row["completed_fits"] == row["valid_fits"] == 0
               for row in result["candidate_results"])


def test_candidate_setup_and_fit_failure_counts_are_not_planned_counts(monkeypatch):
    block = canonical_seed_blocks()[0]
    grid, bundles = inputs(block)
    returned = {}
    for index, key in enumerate(block.candidate_keys):
        returned[key] = {"status": "inference_incomplete", "attempted_fits": int(index > 0),
                         "completed_fits": 0, "valid_fits": 0,
                         "missing_fit_indexes": [0, 1],
                         "joint_support": {"qualification": "valid"}}
    monkeypatch.setattr("higgsml.inference.seed_evaluation.infer_assessment",
                        lambda *a, **k: returned)
    result = evaluate_seed_block(grid, bundles, object(), {}, block=block,
        stage="assessment", mu=1, count=2, toy_base_seed=1, layer="T0",
        t1_validation=None, prepared_id="p", freeze_id="f")
    assert result["candidate_results"][0]["attempted_fits"] == 0
    assert result["candidate_results"][1]["attempted_fits"] == 1


def test_t2_shared_plan_binds_group_identity_order():
    calibration = pd.DataFrame({"role": ["calibration", "calibration"],
                                "event_group_id": [2, 10], "physical_weight": [1., 1.]})
    template = pd.DataFrame({"role": ["template"], "event_group_id": ["t"]})
    mother = pd.DataFrame({"role": ["assessment"], "event_group_id": ["m"]})
    plan = make_t2_outer_multiplicities(calibration,
        contract_digest=pairing_contract()["contract_digest"], outer_replicas=1, toy_base_seed=4)
    kwargs = dict(fit_mapping=lambda frame: {"mapping_id": "map", "bundles": {}},
        apply_mapping=lambda mapping, frame: frame,
        evaluate=lambda *args: {"status": "valid"}, outer_replicas=1, inner_toys=1,
        seed=4, model_id="model", mother_id="mother", outer_multiplicities=plan,
        inner_seed_factory=lambda outer: 7)
    assert run_t2_procedure(calibration, template, mother, **kwargs)["status"] == "valid"
    bad = {**plan, "groups": list(reversed(plan["groups"]))}
    with pytest.raises(ResearchError, match="group identity"):
        run_t2_procedure(calibration, template, mother, **{**kwargs, "outer_multiplicities": bad})
