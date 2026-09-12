import json

import pytest
import torch

from src.artifacts.manifest import sha256_file
from src.research.artifacts import ResearchRun, digest_json, read_run
from src.research.errors import ResearchError
from src.research.protocol import canonical
from src.research.sample_efficiency_workflow import (
    build_learning_curve_plan,
    execute_learning_curve,
    read_learning_curve_batch,
)

from sample_efficiency_support import build_sample_efficiency_fixture


@pytest.fixture(autouse=True)
def single_thread():
    old = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


def t1_evidence(base):
    return {"schema_version": "h4l-t1-validation-v1", "status": "validated",
            "dataset": base["dataset"], "protocol_sha256": base.digest,
            "independent_reference": "synthetic-independent-reference",
            "validation_summary": {"reviewed_by": "synthetic-reviewer",
                                   "reviewed_at": "2026-09-12T00:00:00Z",
                                   "numerical_tests": ["synthetic-contract-test"]},
            "correlation": "independent_process_bins",
            "auxiliary": "poisson_tau_gamma", "modifier": "shapesys",
            "pyhf_version": "0.7.6", "evidence_id": "synthetic-t1"}


def publish_gate(root, prepared, base, evidence=None):
    evidence = evidence or t1_evidence(base)
    with ResearchRun(root, allowed_root=root.parent, stage="templates", dataset=base["dataset"],
                     protocol=base.to_dict(), upstreams=[prepared]) as run:
        run.write_json("g1.json", {"status": "passed", "reasons": [],
                                    "allowed_roles": ["calibration", "template"],
                                    "assessment_used": False})
        run.write_json("t1-validation.json", evidence)
    return read_run(root, dataset=base["dataset"], protocol=base.to_dict(), stages=("templates",))


def resign_batch_json(run_path, filename, mutate):
    payload_path = run_path / filename
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    mutate(payload)
    if filename == "batch-ledger.json":
        payload["ledger_id"] = digest_json({key: value for key, value in payload.items()
                                             if key != "ledger_id"})
    payload_path.write_bytes(canonical(payload))
    manifest_path = run_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][filename] = {"sha256": sha256_file(payload_path),
                                    "size_bytes": payload_path.stat().st_size}
    manifest["artifact_id"] = digest_json({key: value for key, value in manifest.items()
                                            if key != "artifact_id"})
    manifest_path.write_bytes(canonical(manifest))


def test_plan_is_deterministic_full_deduplicated_and_zero_write(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path)
    gate = publish_gate(tmp_path / "gate", prepared, base)
    output = tmp_path / "never-created"
    kwargs = dict(prepared=prepared, freeze_run=freeze, subset_run=subsets, gate_run=gate,
                  t1_validation=t1_evidence(base), base=base, overlay=overlay,
                  output_root=output, output_name="batch", resources={"workers": 1},
                  progress=False)
    first = build_learning_curve_plan(**kwargs)
    second = build_learning_curve_plan(**kwargs)
    assert first == second and not output.exists()
    assert build_learning_curve_plan(**{**kwargs, "progress": True})["execution_plan_id"] == first["execution_plan_id"]
    assert first["planned_alias_count"] == 60
    assert first["canonical_cell_count"] == 45
    assert len(first["cells"]) == 45
    assert len({cell["experiment_cell_id"] for cell in first["cells"]}) == 45
    full = [cell for cell in first["cells"] if cell["sample_fraction_target"] == 1.0]
    assert len(full) == 15 and {cell["sample_draw_seed_or_full"] for cell in full} == {"full"}


def test_plan_rejects_gate_or_t1_and_workers_before_payload_execution(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path)
    bad = publish_gate(tmp_path / "gate", prepared, base,
                       {**t1_evidence(base), "modifier": "histosys"})
    with pytest.raises(ResearchError) as error:
        build_learning_curve_plan(prepared=prepared, freeze_run=freeze, subset_run=subsets,
            gate_run=bad, t1_validation=t1_evidence(base), base=base, overlay=overlay,
            output_root=tmp_path / "runs", output_name="batch",
            resources={"workers": 1})
    assert error.value.status == "training_subset_binding_mismatch"
    gate = publish_gate(tmp_path / "good-gate", prepared, base)
    with pytest.raises(ResearchError):
        build_learning_curve_plan(prepared=prepared, freeze_run=freeze, subset_run=subsets,
            gate_run=gate, t1_validation=t1_evidence(base), base=base, overlay=overlay,
            output_root=tmp_path / "runs", output_name="batch",
            resources={"workers": 2})

    extra = {**t1_evidence(base), "unregistered": True}
    extra_gate = publish_gate(tmp_path / "extra-gate", prepared, base, extra)
    with pytest.raises(ResearchError):
        build_learning_curve_plan(prepared=prepared, freeze_run=freeze, subset_run=subsets,
            gate_run=extra_gate, t1_validation=extra, base=base, overlay=overlay,
            output_root=tmp_path / "runs", output_name="batch", resources={"workers": 1})


def test_synthetic_batch_e2e_and_reader_rejects_receipt_tamper(tmp_path):
    (tmp_path / "inputs").mkdir()
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(
        tmp_path / "inputs", fractions=(0.5, 1.0), draws=(100,), template_groups=400)
    gate = publish_gate(tmp_path / "inputs" / "gate", prepared, base)
    runs = tmp_path / "runs"
    runs.mkdir()
    result = execute_learning_curve(prepared=prepared, freeze_run=freeze, subset_run=subsets,
        gate_run=gate, t1_validation=t1_evidence(base), base=base, overlay=overlay,
        output_root=runs, output_name="batch", resources={"workers": 1}, progress=False)
    assert result.summary["canonical_cell_count"] == 30
    assert result.summary["complete_count"] == 30
    assert result.summary["terminal_count"] == 0
    loaded = read_learning_curve_batch(result.path, prepared=prepared, freeze_run=freeze,
        subset_run=subsets, gate_run=gate, t1_validation=t1_evidence(base), base=base, overlay=overlay)
    assert loaded.summary == result.summary
    assert len({row["stage_artifact_ids"]["template"] for row in loaded.ledger["cells"]}) == 30
    assert len({row["grid_id"] for row in loaded.ledger["cells"]}) == 1

    ledger_path = result.run.file("batch-ledger.json")
    resign_batch_json(result.path / "batch", "batch-ledger.json",
                      lambda payload: payload["cells"][0].update(grid_id=None))
    with pytest.raises(ResearchError):
        read_learning_curve_batch(result.path, prepared=prepared, freeze_run=freeze,
            subset_run=subsets, gate_run=gate, t1_validation=t1_evidence(base), base=base, overlay=overlay)
