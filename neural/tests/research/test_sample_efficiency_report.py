import json

import pytest
import torch

from src.artifacts.manifest import sha256_file
from src.research.artifacts import ResearchRun, digest_json, read_run
from src.research.errors import ResearchError
from src.research.protocol import canonical
from src.research.sample_efficiency import (publish_sample_efficiency_report,
                                             read_sample_efficiency_report,
                                             weighted_auc, _quality_targets)
from src.research.sample_efficiency_workflow import execute_learning_curve
from sample_efficiency_support import build_sample_efficiency_fixture


@pytest.fixture(autouse=True)
def single_thread():
    old = torch.get_num_threads(); torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


def evidence(base):
    return {"schema_version": "h4l-t1-validation-v1", "status": "validated",
        "dataset": base["dataset"], "protocol_sha256": base.digest,
        "evidence_id": "synthetic-t1", "independent_reference": "synthetic-reference",
        "correlation": "independent_process_bins", "auxiliary": "poisson_tau_gamma",
        "modifier": "shapesys", "pyhf_version": "0.7.6",
        "validation_summary": {"reviewed_by": "synthetic-reviewer",
            "reviewed_at": "2026-09-12T00:00:00Z", "numerical_tests": ["synthetic"]}}


def gate(path, prepared, base, t1):
    with ResearchRun(path, allowed_root=path.parent, stage="templates", dataset=base["dataset"],
                     protocol=base.to_dict(), upstreams=[prepared]) as run:
        run.write_json("g1.json", {"status": "passed", "reasons": [],
            "allowed_roles": ["calibration", "template"], "assessment_used": False})
        run.write_json("t1-validation.json", t1)
    return read_run(path, dataset=base["dataset"], protocol=base.to_dict(), stages=("templates",))


def resign_file(run_path, filename, payload):
    path = run_path / filename; path.write_bytes(payload)
    manifest_path = run_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][filename] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    manifest["artifact_id"] = digest_json({key: value for key, value in manifest.items()
                                            if key != "artifact_id"})
    manifest_path.write_bytes(canonical(manifest) + b"\n")


def add_signed_file(run_path, filename, payload):
    path = run_path / filename; path.write_bytes(payload)
    manifest_path = run_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][filename] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    manifest["artifact_id"] = digest_json({key: value for key, value in manifest.items()
                                            if key != "artifact_id"})
    manifest_path.write_bytes(canonical(manifest) + b"\n")


def test_weighted_auc_has_frozen_half_tie_semantics():
    assert weighted_auc([0, 1], [0.0, 1.0], [2.0, 3.0]) == 1.0
    assert weighted_auc([0, 1], [0.5, 0.5], [2.0, 3.0]) == 0.5
    assert weighted_auc([0, 0], [0.0, 1.0], [1.0, 1.0]) is None
    with pytest.raises(ResearchError):
        weighted_auc([0, 1], [0.0, 1.0], [1e308, 1e308])


def test_quality_target_never_extrapolates_and_rejects_duplicate_counts():
    class Overlay(dict):
        pass
    overlay = Overlay(representations=["compact"], quality_target={"enabled": True, "w68": 2.0})
    rows = []
    for count, value in ((10, 3.0), (20, 1.0)):
        rows.append({"representation_id": "compact", "actual_train_group_count": count,
            "means": {"w68": value}, "counts": {"complete_count": 2, "planned_count": 2},
            "curve_row_id": str(count)})
    result = _quality_targets(rows, overlay)[0]
    assert result["status"] == "reached_interpolated" and result["estimated_group_count"] == 15.0
    rows[1]["actual_train_group_count"] = 10
    assert _quality_targets(rows, overlay)[0]["status"] == "ambiguous_duplicate_actual_count"
    rows[1]["actual_train_group_count"] = 20; rows[1]["means"]["w68"] = 2.5
    assert _quality_targets(rows, overlay)[0]["status"] == "not_reached_within_study_range"


def test_report_e2e_preserves_all_cells_and_replays_human_outputs(tmp_path):
    inputs = tmp_path / "inputs"; inputs.mkdir()
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(
        inputs, fractions=(0.5, 1.0), draws=(100,), template_groups=320,
        minimum_groups=20)
    t1 = evidence(base); gate_run = gate(inputs / "gate", prepared, base, t1)
    runs = tmp_path / "runs"; runs.mkdir()
    batch = execute_learning_curve(prepared=prepared, freeze_run=freeze, subset_run=subsets,
        gate_run=gate_run, t1_validation=t1, base=base, overlay=overlay,
        output_root=runs, output_name="batch", resources={"workers": 1})
    report = publish_sample_efficiency_report(runs / "report", allowed_root=runs,
        batch_path=batch.path, prepared=prepared, freeze_run=freeze, subset_run=subsets,
        gate_run=gate_run, t1_validation=t1, base=base, overlay=overlay)
    assert len(report.records) == batch.plan["canonical_cell_count"] == 30
    assert all(row["actual_train_group_count"] > 0 for row in report.records)
    assert {row["cell_status"] for row in report.records} == {"complete", "scientific_terminal"}
    assert {row["pair_status"] for row in report.records} == {"paired", "paired_cell_missing"}
    assert all(row["subset_uncertainty"]["w68"]["status"] == "not_estimated"
               for row in report.summary["curve_rows"])
    assert any(row["network_uncertainty"]["w68"]["status"] == "estimated"
               for row in report.summary["curve_rows"])
    assert {item["status"] for item in report.summary["quality_targets"]} == {"disabled"}
    assert set(report.run.manifest["files"]) >= {"sample-efficiency-records.jsonl",
        "sample-efficiency-summary.json", "sample-efficiency-curves.csv",
        "sample-efficiency-curves.png", "sample-efficiency-report.md", "report-contract.json",
        "protocol.json"}
    loaded = read_sample_efficiency_report(report.path, batch_path=batch.path,
        prepared=prepared, freeze_run=freeze, subset_run=subsets, gate_run=gate_run,
        t1_validation=t1, base=base, overlay=overlay)
    assert loaded.summary == report.summary

    summary_path = report.run.file("sample-efficiency-summary.json")
    original_summary = summary_path.read_bytes()
    changed_summary = json.loads(original_summary)
    changed_summary["record_count"] += 1
    changed_summary["summary_id"] = digest_json({key: value for key, value in changed_summary.items()
                                                   if key != "summary_id"})
    resign_file(report.path, summary_path.name, canonical(changed_summary) + b"\n")
    with pytest.raises(ResearchError) as summary_error:
        read_sample_efficiency_report(report.path, batch_path=batch.path,
            prepared=prepared, freeze_run=freeze, subset_run=subsets, gate_run=gate_run,
            t1_validation=t1, base=base, overlay=overlay)
    assert summary_error.value.status == "learning_curve_incomplete"
    resign_file(report.path, summary_path.name, original_summary)

    png = report.run.file("sample-efficiency-curves.png")
    original_png = png.read_bytes()
    resign_file(report.path, png.name, b"not-a-bound-plot")
    with pytest.raises(ResearchError) as png_error:
        read_sample_efficiency_report(report.path, batch_path=batch.path,
            prepared=prepared, freeze_run=freeze, subset_run=subsets, gate_run=gate_run,
            t1_validation=t1, base=base, overlay=overlay)
    assert png_error.value.status == "training_subset_binding_mismatch"
    resign_file(report.path, png.name, original_png)

    resign_file(report.path, "sample-efficiency-report.md", b"misleading measurement claim")
    with pytest.raises(ResearchError) as markdown_error:
        read_sample_efficiency_report(report.path, batch_path=batch.path,
            prepared=prepared, freeze_run=freeze, subset_run=subsets, gate_run=gate_run,
            t1_validation=t1, base=base, overlay=overlay)
    assert markdown_error.value.status == "learning_curve_incomplete"

    add_signed_file(report.path, "extra-report.md", b"extra")
    with pytest.raises(ResearchError) as extra_error:
        read_sample_efficiency_report(report.path, batch_path=batch.path,
            prepared=prepared, freeze_run=freeze, subset_run=subsets, gate_run=gate_run,
            t1_validation=t1, base=base, overlay=overlay)
    assert extra_error.value.status == "training_subset_binding_mismatch"
