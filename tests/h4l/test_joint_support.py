import json

import pandas as pd
import pytest
from jsonschema import validate

from higgsml.errors import ResearchError
from higgsml.inference.joint_support import (
    bernoulli_group_thinning, diagnose_joint_support, run_j0, run_j1,
)
from higgsml.inference.seed_blocks import canonical_seed_blocks, pairing_contract, stream_identity

ROOT = __import__("pathlib").Path(__file__).parents[2]


def fixture(seed=42, negative=False):
    block = next(block for block in canonical_seed_blocks() if block.seed == seed)
    columns = {key: f"c{i}" for i, key in enumerate(block.candidate_keys)}
    rows = []
    for process in (0, 1):
        for group in range(4):
            row = {"event_group_id": f"{process}-{group}", "label": process, "m4l": 120.,
                   "physical_weight": 99.,
                   "yield_weight": -3. if negative and process == 0 and group == 0 else 1.}
            row.update({column: (group + i) % 2 for i, column in enumerate(columns.values())})
            rows.append(row)
    return pd.DataFrame(rows), block, columns


def args(seed=42, negative=False):
    frame, block, columns = fixture(seed, negative)
    return frame, {"block": block, "category_columns": columns, "mass_edges": [105., 140.]}


def gate_inputs(*, negative=False, process_column=None):
    parent, _ = args(42, negative)
    inputs = {}
    for seed in range(42, 47):
        _, arguments = args(seed, negative)
        if process_column:
            arguments["process_column"] = process_column
        inputs[seed] = arguments
    return parent, inputs


def test_signed_support_projection_and_parent_specific_marginals():
    frame, arguments = args()
    result = diagnose_joint_support(frame, **arguments)
    json.dumps(result, allow_nan=False)
    assert result["summary"]["qualification"] == "valid"
    assert result["summary"]["maximum_projection_error"] == 0
    # A different valid parent is checked against its own direct histogram.
    other = frame.assign(yield_weight=frame.yield_weight * 2)
    assert diagnose_joint_support(other, **arguments)["summary"]["qualification"] == "valid"
    bogus = {("missing", 0, 0, 0): 1.}
    assert "projection_mismatch" in diagnose_joint_support(frame, expected_marginals=bogus, **arguments)["summary"]["failures"]


def test_negative_process_cell_fails_without_signal_cancellation_or_clipping():
    frame, arguments = args(negative=True)
    result = diagnose_joint_support(frame, **arguments)
    assert "negative_process_rate" in result["summary"]["failures"]
    assert min(cell["signed_sum"] for cell in result["cells"]) == -2.


def test_group_split_and_accidental_zero_are_explicit():
    frame, arguments = args()
    duplicated = pd.concat([frame, frame.iloc[[0]].assign(yield_weight=-2.)], ignore_index=True)
    zero = diagnose_joint_support(duplicated, **arguments)
    assert any(cell["zero_class"] == "accidental_cancellation" for cell in zero["cells"])
    split = pd.concat([frame, frame.iloc[[0]].assign(c0=1-frame.iloc[0].c0)], ignore_index=True)
    assert diagnose_joint_support(split, **arguments)["summary"]["qualification"] == "template_stat_model_unvalidated"


def test_process_cross_product_records_no_events_and_rejects_mixed_labels():
    frame, arguments = args()
    frame.loc[0, "c0"] = 7
    result = diagnose_joint_support(frame, **arguments)
    assert any(cell["zero_class"] == "no_events" for cell in result["cells"])
    explicit = frame.assign(process="background")
    assert diagnose_joint_support(explicit, process_column="process", **arguments)["summary"]["qualification"] == "template_stat_model_unvalidated"


def test_j0_requires_all_five_valid_blocks():
    parent, arguments = gate_inputs()
    inputs = {seed: value | {"parent": parent} for seed, value in arguments.items()}
    result = run_j0(inputs)
    assert result["status"] == "passed"
    schema = json.loads((ROOT / "config/schemas/h4l_joint_support_v1.schema.json").read_text())
    validate(result, schema)
    with pytest.raises(ResearchError, match="canonical seeds"):
        run_j0({42: inputs[42]})
    copied = {seed: inputs[42] for seed in range(42, 47)}
    with pytest.raises(ResearchError, match="seed/block binding"):
        run_j0(copied)
    different_grid = {**inputs, 46: {**inputs[46], "mass_edges": [105., 130., 140.]}}
    with pytest.raises(ResearchError, match="one nominal mass grid"):
        run_j0(different_grid)


def test_group_thinning_q_rules_and_j1_fixed_budget():
    frame, block_inputs = gate_inputs()
    stream = stream_identity(contract_digest=pairing_contract()["contract_digest"], stage="support-j1",
                             mu=0, training_seed=42, outer_index=None,
                             stream_kind="physical_group_thinning", replica_index=0, toy_base_seed=42001)
    same, summary = bernoulli_group_thinning(frame, q=1, stream=stream)
    assert summary["design"] == "degenerate_q1_all_groups"
    assert same.yield_weight.tolist() == frame.yield_weight.tolist()
    half, _ = bernoulli_group_thinning(frame, q=.5, stream=stream)
    assert set(half.event_group_id).issubset(frame.event_group_id)
    assert set(half.yield_weight) <= {2.}
    with pytest.raises(ResearchError, match="screening_design_unavailable"):
        bernoulli_group_thinning(frame, q=1.5, stream=stream)
    with pytest.raises(ResearchError, match="200-replica"):
        run_j1(frame, block_inputs=block_inputs, q=.5,
               contract_digest=pairing_contract()["contract_digest"], replicas=2)
    screening = run_j1(frame, block_inputs=block_inputs, q=1,
                       contract_digest=pairing_contract()["contract_digest"])
    assert screening["replicas"] == len(screening["records"]) == 200
    assert all(row["selection"]["stream_id"] for row in screening["records"])
    schema = json.loads((ROOT / "config/schemas/h4l_joint_support_v1.schema.json").read_text())
    validate(screening, schema)
    thinned = run_j1(frame, block_inputs=block_inputs, q=.5,
                     contract_digest=pairing_contract()["contract_digest"])
    assert all(set(record["seeds"]) == {"42", "43", "44", "45", "46"}
               for record in thinned["records"])
    assert len({record["selection"]["stream_id"] for record in thinned["records"]}) == 200


def test_j1_custom_process_source_and_failure_evidence_are_lossless():
    parent, block_inputs = gate_inputs(process_column="process_id")
    parent["process_id"] = parent.label.map({0: "qqZZ", 1: "ggH"})
    result = run_j1(parent, block_inputs=block_inputs, q=1,
                    contract_digest=pairing_contract()["contract_digest"], toy_base_seed=987)
    assert result["status"] == "passed"
    assert result["toy_base_seed"] == 987
    assert {row["process"] for row in result["records"][0]["seeds"]["42"]["processes"]} == {"qqZZ", "ggH"}
    assert result["records"][0]["selection"]["stream"]["toy_base_seed"] == 987

    failed_parent, failed_inputs = gate_inputs(negative=True)
    failed = run_j1(failed_parent, block_inputs=failed_inputs, q=1,
                    contract_digest=pairing_contract()["contract_digest"])
    evidence = failed["records"][0]["failure_diagnostics"]["42"]
    assert any(cell["signed_sum"] < 0 and "group_occupancy" in cell for cell in evidence["cells"])
    json.dumps(failed, allow_nan=False)
