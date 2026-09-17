from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest

from higgsml._manifest import canonical_json_bytes, sha256_file
from higgsml.artifacts import digest_json
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference.seed_evaluation_state import (
    SeedEvaluationBinding,
    claim_seed_evaluation,
    publish_seed_evaluation_terminal,
    read_seed_evaluation_terminal,
    recover_seed_evaluation_publication,
    resolve_seed_evaluation,
)
from higgsml.inference.seed_blocks import canonical_seed_blocks
from higgsml.inference.seed_evaluation import evaluate_seed_t2


def _binding(**changes):
    values = {
        "population_id": "population-1", "freeze_artifact_id": "freeze-1",
        "specification_id": "spec-1", "evaluation_plan_id": "plan-1",
        "pairing_contract": "within_seed", "stage": "assessment", "mu": 1,
        "training_seed": 42,
        "access_receipt": {"receipt_id": "access-1"},
        "budget": {"planned_toys_per_candidate": 3},
        "rng": {"stream_id": "rng-1"},
    }
    values.update(changes)
    if "candidate_ids" not in changes:
        values["candidate_ids"] = next(
            block.candidate_keys for block in canonical_seed_blocks()
            if block.seed == values["training_seed"]
        )
    return SeedEvaluationBinding(**values)


def _terminal(binding, status="valid"):
    completed = 3 if status == "valid" else 0
    return {
        "execution_status": "complete", "scientific_status": status,
        "pairing_scope": "within_seed", "cross_seed_pairing": "none",
        "stage": binding.stage, "training_seed": binding.training_seed,
        "qualification": {"status": status},
        "joint_support": {"qualification": "valid"} if status == "valid" else {},
        "planned_toys_per_candidate": 3,
        "generated_physical_toys": completed,
        "candidate_results": [
            {"candidate_id": candidate, "attempted_fits": 3,
             "completed_fits": completed, "valid_fits": completed,
             "status": status}
            for candidate in binding.candidate_ids
        ],
    }


def _roots(tmp_path):
    lineage, outputs = tmp_path / "lineage", tmp_path / "outputs"
    lineage.mkdir(); outputs.mkdir()
    return lineage, outputs


def _resign(output, mutate):
    payload_path = output / "seed-evaluation.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    mutate(payload)
    unsigned = dict(payload); unsigned.pop("terminal_id")
    payload["terminal_id"] = digest_json(unsigned)
    payload_path.write_bytes(canonical_json_bytes(payload))
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["seed-evaluation.json"] = {
        "sha256": sha256_file(payload_path), "size_bytes": payload_path.stat().st_size,
    }
    unsigned_manifest = dict(manifest); unsigned_manifest.pop("artifact_id")
    manifest["artifact_id"] = digest_json(unsigned_manifest)
    manifest_path.write_bytes(canonical_json_bytes(manifest))


def test_statistical_terminal_is_complete_but_consumer_rejects_it(tmp_path):
    lineage, outputs = _roots(tmp_path)
    binding, output = _binding(), outputs / "cell"
    claim_seed_evaluation(claims_root=lineage, output_dir=output, binding=binding)
    publish_seed_evaluation_terminal(
        output_dir=output, allowed_root=outputs, claims_root=lineage,
        dataset="mc", protocol={}, binding=binding,
        terminal=_terminal(binding, "insufficient_statistics"),
    )
    assert resolve_seed_evaluation(
        output_dir=output, claims_root=lineage, dataset="mc", protocol={}, binding=binding,
    ) == "skip_terminal"
    run, value = read_seed_evaluation_terminal(
        output_dir=output, claims_root=lineage, dataset="mc", protocol={}, binding=binding,
    )
    assert run.manifest["status"] == "complete"
    assert value["scientific_status"] == "insufficient_statistics"
    with pytest.raises(ResearchStateError, match="not scientifically valid"):
        read_seed_evaluation_terminal(
            output_dir=output, claims_root=lineage, dataset="mc", protocol={},
            binding=binding, require_scientific_valid=True,
        )


def test_claimed_crash_and_damaged_output_are_never_retried_or_moved(tmp_path):
    lineage, outputs = _roots(tmp_path)
    binding, output = _binding(), outputs / "cell"
    claim_seed_evaluation(claims_root=lineage, output_dir=output, binding=binding)
    assert resolve_seed_evaluation(
        output_dir=output, claims_root=lineage, dataset="mc", protocol={}, binding=binding,
    ) == "blocked_consumed_budget"
    output.mkdir()
    (output / "manifest.json").write_text("damaged", encoding="utf-8")
    assert resolve_seed_evaluation(
        output_dir=output, claims_root=lineage, dataset="mc", protocol={}, binding=binding,
    ) == "blocked_consumed_budget"
    assert output.is_dir()
    assert not list(outputs.glob("*.invalid"))


def test_claim_slot_is_atomic_and_stable_against_changed_receipts(tmp_path):
    lineage, outputs = _roots(tmp_path)
    binding, output = _binding(), outputs / "cell"

    def attempt():
        try:
            claim_seed_evaluation(claims_root=lineage, output_dir=output, binding=binding)
            return "won"
        except ResearchStateError:
            return "blocked"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: attempt(), range(8)))
    assert results.count("won") == 1
    assert results.count("blocked") == 7
    claim_path = next((lineage / ".h4l-mass-off-v2-claims").glob("cell-*.json"))
    original = claim_path.read_bytes()
    changed = _binding(access_receipt={"receipt_id": "different"},
                       evaluation_plan_id="different", budget={"planned_toys_per_candidate": 99})
    assert changed.ledger_key == binding.ledger_key
    with pytest.raises(ResearchStateError, match="already consumed"):
        claim_seed_evaluation(claims_root=lineage, output_dir=outputs / "other", binding=changed)
    assert claim_path.read_bytes() == original


def test_claim_slot_normalizes_mu_and_rejects_invalid_cell_identity(tmp_path):
    lineage, outputs = _roots(tmp_path)
    integer, floating = _binding(mu=1), _binding(mu=1.0)
    assert integer.ledger_key == floating.ledger_key
    assert integer.cell_id == floating.cell_id
    claim_seed_evaluation(claims_root=lineage, output_dir=outputs / "one", binding=integer)
    with pytest.raises(ResearchStateError, match="already consumed"):
        claim_seed_evaluation(claims_root=lineage, output_dir=outputs / "two", binding=floating)
    invalid_candidates = list(integer.candidate_ids); invalid_candidates[-1] = "unregistered"
    for invalid in (_binding(mu=float("nan")), _binding(stage="unknown"),
                    _binding(training_seed=41, candidate_ids=integer.candidate_ids),
                    _binding(candidate_ids=tuple(invalid_candidates))):
        with pytest.raises(ResearchError, match="invalid seed evaluation"):
            invalid.value()


@pytest.mark.parametrize("stage,mu", [
    ("model-self", 0), ("model-self", 1), ("model-self", 2),
    ("assessment", 0), ("assessment", 1), ("assessment", 2),
    ("t2", 1),
])
def test_registered_stage_mu_cells_are_accepted(stage, mu):
    budget = ({"planned_outer": 20, "planned_inner_per_outer": 100}
              if stage == "t2" else {"planned_toys_per_candidate": 500})
    value = _binding(stage=stage, mu=mu, budget=budget).value()
    assert value["stage"] == stage and value["mu"] == float(mu)


@pytest.mark.parametrize("stage,mu", [
    ("model-self", -1), ("model-self", 3),
    ("assessment", -1), ("assessment", 3),
    ("t2", 0), ("t2", 2), ("unknown", 1),
])
def test_unregistered_stage_mu_cells_are_rejected(stage, mu):
    budget = ({"planned_outer": 20, "planned_inner_per_outer": 100}
              if stage == "t2" else {"planned_toys_per_candidate": 500})
    with pytest.raises(ResearchError, match="invalid seed evaluation"):
        _binding(stage=stage, mu=mu, budget=budget).value()


def test_failed_claim_fsync_leaves_consumed_slot_blocked(tmp_path, monkeypatch):
    lineage, outputs = _roots(tmp_path)
    # Establish population history first so the injected failure occurs on the cell record.
    first = _binding(training_seed=43)
    claim_seed_evaluation(claims_root=lineage, output_dir=outputs / "first", binding=first)
    binding = _binding()
    monkeypatch.setattr("higgsml.inference.seed_evaluation_state.os.fsync",
                        lambda _: (_ for _ in ()).throw(OSError("crash")))
    with pytest.raises(OSError, match="crash"):
        claim_seed_evaluation(claims_root=lineage, output_dir=outputs / "cell", binding=binding)
    cell_path = lineage / ".h4l-mass-off-v2-claims" / f"cell-{binding.ledger_key}.json"
    assert cell_path.exists()
    monkeypatch.undo()
    with pytest.raises(ResearchStateError, match="already consumed"):
        claim_seed_evaluation(claims_root=lineage, output_dir=outputs / "cell", binding=binding)
    assert resolve_seed_evaluation(
        output_dir=outputs / "cell", claims_root=lineage,
        dataset="mc", protocol={}, binding=binding,
    ) == "blocked_consumed_budget"


def test_population_history_spans_freezes_and_reads_v1_history(tmp_path):
    lineage, outputs = _roots(tmp_path)
    first = _binding()
    claim_seed_evaluation(claims_root=lineage, output_dir=outputs / "one", binding=first)
    with pytest.raises(ResearchStateError, match="another freeze"):
        claim_seed_evaluation(
            claims_root=lineage, output_dir=outputs / "two",
            binding=_binding(freeze_artifact_id="freeze-2", training_seed=43),
        )

    other_lineage = tmp_path / "other-lineage"
    other_lineage.mkdir(); legacy = other_lineage / ".research-claims"; legacy.mkdir()
    (legacy / "history.json").write_text(json.dumps({
        "population_id": "population-1", "freeze_artifact_id": "old-freeze",
    }), encoding="utf-8")
    with pytest.raises(ResearchStateError, match="another freeze"):
        claim_seed_evaluation(
            claims_root=other_lineage, output_dir=outputs / "three", binding=first,
        )


def test_model_self_claim_does_not_consume_or_check_assessment_history(tmp_path):
    lineage, outputs = _roots(tmp_path)
    legacy = lineage / ".research-claims"; legacy.mkdir()
    (legacy / "history.json").write_text(json.dumps({
        "population_id": "population-1", "freeze_artifact_id": "old-freeze",
    }), encoding="utf-8")
    model_self = _binding(stage="model-self")
    claim_seed_evaluation(
        claims_root=lineage, output_dir=outputs / "model-self", binding=model_self,
    )
    claim_dir = lineage / ".h4l-mass-off-v2-claims"
    assert not list(claim_dir.glob("population-*.json"))
    with pytest.raises(ResearchStateError, match="another freeze"):
        claim_seed_evaluation(
            claims_root=lineage, output_dir=outputs / "assessment", binding=_binding(),
        )


def test_only_complete_verified_staging_can_be_published(tmp_path):
    lineage, outputs = _roots(tmp_path)
    binding, output = _binding(), outputs / "cell"
    claim_seed_evaluation(claims_root=lineage, output_dir=output, binding=binding)
    publish_seed_evaluation_terminal(
        output_dir=output, allowed_root=outputs, claims_root=lineage,
        dataset="mc", protocol={}, binding=binding, terminal=_terminal(binding),
    )
    staging = outputs / f".{output.name}.crash.failed"
    output.rename(staging)
    assert resolve_seed_evaluation(
        output_dir=output, claims_root=lineage, dataset="mc", protocol={}, binding=binding,
    ) == "recover_publication"
    recovered = recover_seed_evaluation_publication(
        output_dir=output, allowed_root=outputs, claims_root=lineage,
        dataset="mc", protocol={}, binding=binding,
    )
    assert recovered.path == output.resolve()
    assert not staging.exists()


def test_resigned_terminal_with_wrong_candidate_is_rejected(tmp_path):
    lineage, outputs = _roots(tmp_path)
    binding, output = _binding(), outputs / "cell"
    claim_seed_evaluation(claims_root=lineage, output_dir=output, binding=binding)
    publish_seed_evaluation_terminal(
        output_dir=output, allowed_root=outputs, claims_root=lineage,
        dataset="mc", protocol={}, binding=binding, terminal=_terminal(binding),
    )
    _resign(output, lambda payload: payload["candidate_results"][0].update(
        candidate_id="unregistered"))
    with pytest.raises(ResearchError, match="candidate identity mismatch"):
        read_seed_evaluation_terminal(
            output_dir=output, claims_root=lineage, dataset="mc", protocol={}, binding=binding,
        )
    assert resolve_seed_evaluation(
        output_dir=output, claims_root=lineage, dataset="mc", protocol={}, binding=binding,
    ) == "blocked_consumed_budget"


@pytest.mark.parametrize("mutation,match", [
    (lambda value: value.update(planned_toys_per_candidate=4), "budget differs"),
    (lambda value: value["candidate_results"][0].update(valid_fits=-1), "minimum"),
    (lambda value: [row.update(attempted_fits=0, completed_fits=0, valid_fits=0)
                    for row in value["candidate_results"]], "scientifically valid terminal is incomplete"),
])
def test_resigned_budget_and_count_tampering_is_rejected(tmp_path, mutation, match):
    lineage, outputs = _roots(tmp_path)
    binding, output = _binding(), outputs / "cell"
    claim_seed_evaluation(claims_root=lineage, output_dir=output, binding=binding)
    publish_seed_evaluation_terminal(
        output_dir=output, allowed_root=outputs, claims_root=lineage,
        dataset="mc", protocol={}, binding=binding, terminal=_terminal(binding),
    )
    _resign(output, mutation)
    with pytest.raises(ResearchError, match=match):
        read_seed_evaluation_terminal(
            output_dir=output, claims_root=lineage, dataset="mc", protocol={}, binding=binding,
            require_scientific_valid=True,
        )


def test_terminal_must_match_claimed_budget_before_publication(tmp_path):
    lineage, outputs = _roots(tmp_path)
    binding, output = _binding(), outputs / "cell"
    claim_seed_evaluation(claims_root=lineage, output_dir=output, binding=binding)
    bad = _terminal(binding); bad["planned_toys_per_candidate"] = 999
    with pytest.raises(ResearchError, match="budget differs"):
        publish_seed_evaluation_terminal(
            output_dir=output, allowed_root=outputs, claims_root=lineage,
            dataset="mc", protocol={}, binding=binding, terminal=bad,
        )
    assert not output.exists()


def test_t2_terminal_enforces_outer_inner_claim(tmp_path):
    lineage, outputs = _roots(tmp_path)
    binding = _binding(stage="t2", budget={"planned_outer": 2, "planned_inner_per_outer": 3})
    output = outputs / "t2"
    claim_seed_evaluation(claims_root=lineage, output_dir=output, binding=binding)
    terminal = _terminal(binding)
    terminal.update(planned_outer=2, planned_inner_per_outer=3,
                    planned_toys_per_candidate=6, generated_physical_toys=6)
    for row in terminal["candidate_results"]:
        row.update(attempted_fits=6, completed_fits=6, valid_fits=6)
    publish_seed_evaluation_terminal(
        output_dir=output, allowed_root=outputs, claims_root=lineage,
        dataset="mc", protocol={}, binding=binding, terminal=terminal,
    )
    _, value = read_seed_evaluation_terminal(
        output_dir=output, claims_root=lineage, dataset="mc", protocol={}, binding=binding,
        require_scientific_valid=True,
    )
    assert value["planned_toys_per_candidate"] == 6


@pytest.mark.parametrize("failed", [False, True])
def test_t2_evaluator_envelope_publishes_directly(tmp_path, monkeypatch, failed):
    lineage, outputs = _roots(tmp_path)
    block = canonical_seed_blocks()[0]
    grid = {"templates": {key: {"candidate_id": key} for key in block.candidate_keys}}
    bundles = {key: {"model_id": key} for key in block.candidate_keys}
    plan = {"groups": ["a", "b"], "multiplicities": [[1, 1], [2, 0]],
            "multiplicity_plan_digest": digest_json([[1, 1], [2, 0]])}

    def fake_t2(*args, **kwargs):
        if failed:
            raise ResearchStateError("outer support failed", status="insufficient_statistics")
        candidates = {key: {"attempted_fits": 2, "completed_fits": 2, "valid_fits": 2,
                            "joint_support": {"qualification": "valid"}}
                      for key in block.candidate_keys}
        return {"status": "valid", "replicas": [
            {"replica": index, "bootstrap_group_multiplicities": multiplicity,
             "result": {"candidates": candidates}}
            for index, multiplicity in enumerate(plan["multiplicities"])
        ]}

    monkeypatch.setattr("higgsml.inference.seed_evaluation.run_assessment_t2", fake_t2)
    terminal = evaluate_seed_t2(
        grid, bundles, object(), object(), object(), {"inference": {"inner_toys": 2}},
        block=block, mu=1, toy_base_seed=42, layer="T0", t1_validation=None,
        prepared_id="prepared", freeze_id="freeze-1", outer_multiplicities=plan,
    )
    binding = _binding(stage="t2", candidate_ids=block.candidate_keys,
                       budget={"planned_outer": 2, "planned_inner_per_outer": 2})
    output = outputs / ("failed-t2" if failed else "valid-t2")
    claim_seed_evaluation(claims_root=lineage, output_dir=output, binding=binding)
    publish_seed_evaluation_terminal(
        output_dir=output, allowed_root=outputs, claims_root=lineage,
        dataset="mc", protocol={}, binding=binding, terminal=terminal,
    )
    _, value = read_seed_evaluation_terminal(
        output_dir=output, claims_root=lineage, dataset="mc", protocol={}, binding=binding,
        require_scientific_valid=not failed,
    )
    assert value["scientific_status"] == ("insufficient_statistics" if failed else "valid")
    assert value["generated_physical_toys"] == (0 if failed else 4)
