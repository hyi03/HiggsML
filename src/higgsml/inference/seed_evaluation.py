"""Pure per-seed evaluation envelopes for the v2 within-seed contract."""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference.assessment import infer_assessment, run_assessment_t2
from higgsml.inference.seed_blocks import SeedBlockSpec, canonical_seed_blocks, stream_identity
from higgsml.artifacts import digest_json
from higgsml.protocol import protocol_dict

EXPECTED_SCIENTIFIC_STATES = {
    "insufficient_statistics", "unsupported_assessment_support",
    "template_stat_model_unvalidated", "inference_incomplete",
}
STAGES = {"model-self": "template", "assessment": "assessment"}


def _validate_block(block):
    if not isinstance(block, SeedBlockSpec) or block not in canonical_seed_blocks():
        raise ResearchError("noncanonical seed evaluation block")


def _block_inputs(grid, bundles, block):
    _validate_block(block)
    keys = set(block.candidate_keys)
    if not keys <= set(grid.get("templates", {})) or not keys <= set(bundles):
        raise ResearchError("seed evaluation inputs do not cover the block")
    selected_grid = deepcopy(grid)
    selected_grid["templates"] = {key: deepcopy(grid["templates"][key]) for key in block.candidate_keys}
    return selected_grid, {key: bundles[key] for key in block.candidate_keys}


def _candidate_rows(block, results, planned):
    rows = []
    for key in block.candidate_keys:
        result = results.get(key, {})
        rows.append({"candidate_id": key,
                     "attempted_fits": int(result.get("attempted_fits", 0)),
                     "completed_fits": int(result.get("completed_fits", 0)),
                     "valid_fits": int(result.get("valid_fits", 0)),
                     "missing_fit_indexes": result.get("missing_fit_indexes", list(range(planned))),
                     "status": result.get("status", "not_run"), "result": result})
    return rows


def _failure_envelope(*, stage, block, planned, status, reason, stream, support=None):
    return {"execution_status": "complete", "scientific_status": status,
            "pairing_scope": "within_seed", "cross_seed_pairing": "none",
            "stage": stage, "training_seed": block.seed, "block_id": block.block_id,
            "planned_toys_per_candidate": planned, "generated_physical_toys": 0,
            "candidate_results": _candidate_rows(block, {}, planned),
            "joint_support": support or {},
            "qualification": {"status": status, "reason": reason},
            "rng": stream}


def evaluate_seed_block(grid, bundles, parent, protocol, *, block, stage, mu, count,
                        toy_base_seed, layer, t1_validation, prepared_id, freeze_id,
                        workers=1, worker_threads=1, progress=None, categorize=None):
    """Evaluate one complete 16-candidate block with shared physical draws."""
    if stage not in STAGES or type(count) is not int or count < 1:
        raise ResearchError("invalid seed evaluation stage or budget")
    selected_grid, selected_bundles = _block_inputs(grid, bundles, block)
    physical = stream_identity(contract_digest=block.pairing_contract_digest, stage=stage,
        mu=mu, training_seed=block.seed, outer_index=None, stream_kind="physical_poisson",
        toy_base_seed=toy_base_seed)
    auxiliary = {key: stream_identity(contract_digest=block.pairing_contract_digest,
        stage=stage, mu=mu, training_seed=block.seed, outer_index=None,
        stream_kind="candidate_auxiliary", candidate_if_auxiliary=key,
        toy_base_seed=toy_base_seed) for key in block.candidate_keys}
    try:
        results = infer_assessment(selected_grid, selected_bundles, parent, protocol,
            layer=layer, t1_validation=t1_validation, mu=mu, count=count,
            seed=physical["seed"], prepared_id=prepared_id, freeze_id=freeze_id,
            parent_role=STAGES[stage], seed_block=block,
            physical_stream_id=physical["stream_id"], workers=workers,
            worker_threads=worker_threads, progress=progress,
            auxiliary_streams=auxiliary, categorize=categorize)
    except ResearchStateError as exc:
        if exc.status not in EXPECTED_SCIENTIFIC_STATES:
            raise
        return _failure_envelope(stage=stage, block=block, planned=count,
            status=exc.status, reason=str(exc), stream=physical,
            support=getattr(exc, "joint_support", None))
    rows = _candidate_rows(block, results, count)
    statuses = {row["status"] for row in rows}
    scientific = "valid" if statuses == {"valid"} else "inference_incomplete"
    support = next((r["result"].get("joint_support") for r in rows
                    if r["result"].get("joint_support")), {})
    return {"execution_status": "complete", "scientific_status": scientific,
            "pairing_scope": "within_seed", "cross_seed_pairing": "none",
            "stage": stage, "training_seed": block.seed, "block_id": block.block_id,
            "planned_toys_per_candidate": count, "generated_physical_toys": count,
            "candidate_results": rows, "joint_support": support,
            "qualification": {"status": scientific}, "rng": physical,
            "auxiliary_rng": auxiliary}


def evaluate_seed_t2(grid, bundles, calibration, template, mother, protocol, *, block,
                     mu, toy_base_seed, layer, t1_validation, prepared_id, freeze_id,
                     workers=1, worker_threads=1, progress=None, outer_multiplicities=None):
    """Run the registered T2 procedure for one block on an optional shared outer plan."""
    selected_grid, selected_bundles = _block_inputs(grid, bundles, block)
    if outer_multiplicities is None:
        raise ResearchError("T2 v2 requires the shared outer multiplicity plan")
    try:
        result = run_assessment_t2(selected_grid, selected_bundles, calibration, template, mother,
            protocol, layer=layer, t1_validation=t1_validation, mu=mu,
            seed=toy_base_seed, prepared_id=prepared_id, freeze_id=freeze_id,
            workers=workers, worker_threads=worker_threads, progress=progress,
            seed_block=block, outer_multiplicities=outer_multiplicities)
    except ResearchStateError as exc:
        if exc.status not in EXPECTED_SCIENTIFIC_STATES:
            raise
        result = {"status": exc.status, "replicas": [], "reason": str(exc)}
    replicas = result.get("replicas", [])
    for row in replicas:
        row["multiplicity_digest"] = digest_json(row["bootstrap_group_multiplicities"])
        if "mappings" in row:
            row["mapping_digest"] = digest_json(row["mappings"])
    cfg = protocol_dict(protocol)["inference"]
    inner = cfg["inner_toys"]
    multiplicities = outer_multiplicities["multiplicities"]
    planned = len(multiplicities) * inner
    generated = sum(inner for outer in replicas if "result" in outer)
    support_records = []
    candidates = []
    for key in block.candidate_keys:
        completed = valid = 0
        for outer in replicas:
            candidate = outer.get("result", {}).get("candidates", {}).get(key, {})
            completed += candidate.get("completed_fits", 0)
            valid += candidate.get("valid_fits", 0)
            if candidate.get("joint_support"):
                support_records.append({"outer": outer["replica"], "candidate_id": key,
                                        "summary": candidate["joint_support"]})
        attempted = sum(outer.get("result", {}).get("candidates", {}).get(key, {}).get("attempted_fits", 0)
                        for outer in replicas)
        candidates.append({"candidate_id": key, "attempted_fits": attempted,
                           "completed_fits": completed, "valid_fits": valid})
    scientific = result.get("status", "inference_incomplete")
    support_valid = bool(support_records) and all(
        row["summary"].get("qualification") == "valid" for row in support_records)
    joint_support = {"status": "valid" if support_valid else "incomplete",
                     "qualification": "valid" if support_valid else "incomplete",
                     "outer_records": support_records}
    return {"execution_status": "complete", "scientific_status": result.get("status", "inference_incomplete"),
            "pairing_scope": "within_seed", "cross_seed_pairing": "none", "stage": "t2",
            "training_seed": block.seed, "block_id": block.block_id,
            "planned_outer": len(multiplicities), "planned_inner_per_outer": inner,
            "planned_toys_per_candidate": planned, "generated_physical_toys": generated,
            "outer_multiplicity_plan_digest": outer_multiplicities["multiplicity_plan_digest"],
            "outer_records": replicas, "candidate_results": candidates,
            "joint_support": joint_support,
            "qualification": {"status": scientific}}


def make_t2_outer_multiplicities(calibration, *, contract_digest, outer_replicas,
                                 toy_base_seed):
    """Create the one outer calibration bootstrap plan shared by all five blocks."""
    groups = sorted(calibration.event_group_id.unique(), key=str)
    if not groups or type(outer_replicas) is not int or outer_replicas < 1:
        raise ResearchError("invalid T2 outer plan inputs")
    if len(set(map(str, groups))) != len(groups):
        raise ResearchError("ambiguous T2 calibration group identities")
    stream = stream_identity(contract_digest=contract_digest, stage="t2", mu=1,
        training_seed=42, outer_index=None, stream_kind="shared_calibration_multiplicities",
        toy_base_seed=toy_base_seed)
    rng = np.random.default_rng(stream["seed"])
    probabilities = np.full(len(groups), 1 / len(groups))
    multiplicities = [rng.multinomial(len(groups), probabilities).tolist()
                      for _ in range(outer_replicas)]
    return {"groups": list(map(str, groups)), "multiplicities": multiplicities,
            "stream": stream, "multiplicity_plan_digest": digest_json(multiplicities)}
