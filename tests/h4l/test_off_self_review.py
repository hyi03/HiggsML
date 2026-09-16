import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from higgsml.artifacts import digest_json, sha256_file
from higgsml.errors import ResearchError


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_generate_self_review_binds_stage_b_and_automated_materials(tmp_path):
    from higgsml.inference.self_review import generate_self_review

    prepared = tmp_path / "prepare"
    run = tmp_path / "h4l-off-study"
    protocol = {"dataset": "atlas2020_4lep", "id": "test", "inference": {}}
    _write(prepared / "manifest.json", {"artifact_id": "1" * 64})
    _write(prepared / "protocol.json", {"dataset": "atlas2020_4lep", "id": "legacy", "inference": {}})
    _write(prepared / "p0-validation.json", {"schema_version": "h4l-p0-validation-v1"})
    _write(run / "register" / "manifest.json", {"artifact_id": "2" * 64})
    _write(run / "register" / "registration.json", {
        "prepared_artifact_id": "1" * 64, "population_id": "3" * 64,
        "protocol_sha256": digest_json(protocol),
    })
    _write(run / "nominal" / "manifest.json", {"artifact_id": "4" * 64})
    _write(run / "nominal" / "t1-validation.json", {"schema_version": "h4l-t1-validation-v1"})
    _write(run / "freeze" / "manifest.json", {"artifact_id": "5" * 64})
    _write(run / "freeze" / "protocol.json", protocol)
    _write(run / "freeze" / "freeze.json", {
        "prepared_artifact_id": "1" * 64, "template_artifact_id": "4" * 64,
        "protocol_sha256": digest_json(protocol),
    })
    _write(run / "report-B" / "evaluation-plan.json", {
        "inputs": {"prepared_artifact_id": "1" * 64, "template_artifact_id": "4" * 64,
                   "freeze_artifact_id": "5" * 64}
    })

    access = generate_self_review(run, prepared, reviewer="Solo Researcher")

    assert access.name == "validated-off-assessment-access.json"
    review = json.loads(access.read_text(encoding="utf-8"))
    assert review["review_mode"] == "single_researcher_self_review"
    assert review["independent"] is False
    assert review["allowed_conclusions"] == "exploratory_self_reviewed_not_independently_validated"
    assert review["freeze_artifact_id"] == "5" * 64
    for key in ("p0_reference", "t1_reference"):
        receipt = review[key]
        target = access.parent / receipt["path"]
        assert target.is_file()
        assert receipt == {"path": target.name, "sha256": sha256_file(target),
                           "size_bytes": target.stat().st_size}


def test_self_review_gate_allows_access_without_claiming_independence(monkeypatch, tmp_path):
    from higgsml.inference import attribution_workflow as workflow
    from higgsml.inference.self_review import validate_self_review_access

    protocol = {"dataset": "atlas2020_4lep", "id": "test", "inference": {}}
    prepared_path = tmp_path / "old" / "prepare"
    prepared_path.mkdir(parents=True)
    _write(prepared_path / "p0-validation.json", {})
    prepared = SimpleNamespace(path=prepared_path, manifest={"artifact_id": "1" * 64},
                               file=lambda n: prepared_path / n,
                               read_json=lambda n: protocol)
    frozen = SimpleNamespace(manifest={"artifact_id": "2" * 64},
                             read_json=lambda n: {"template_artifact_id": "3" * 64})
    overlay = {"population_id": "4" * 64}
    for name, source in (("self-reviewed-p0-applicability.json", "p0-validation.json"),
                         ("self-reviewed-signed-mc-t1.json", "t1-validation.json")):
        _write(tmp_path / name, {"schema_version": "h4l-off-self-review-evidence-v1",
                                "evidence_kind": "p0" if "p0" in name else "signed_mc_t1",
                                "review_mode": "single_researcher_self_review", "reviewer": "Solo",
                                "independent": False, "source": source,
                                "prepared_artifact_id": "1" * 64,
                                "population_id": "4" * 64,
                                "protocol_sha256": digest_json(protocol),
                                "freeze_artifact_id": "2" * 64,
                                "limitations": ["single researcher self-review; not independently validated"]})
    def receipt(name):
        path = tmp_path / name
        return {"path": name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    review = {
        "schema_version": "h4l-off-assessment-access-v1", "status": "validated_for_self_reviewed_exploratory_access",
        "review_mode": "single_researcher_self_review", "independent": False, "reviewer": "Solo",
        "prepared_artifact_id": "1" * 64, "population_id": "4" * 64,
        "protocol_sha256": digest_json(protocol), "freeze_artifact_id": "2" * 64,
        "history_review": "self_reviewed_unused_assessment_population",
        "role_isolation": "self_reviewed_physical_groups_disjoint",
        "allowed_conclusions": "exploratory_self_reviewed_not_independently_validated",
        "p0_reference": receipt("self-reviewed-p0-applicability.json"),
        "t1_reference": receipt("self-reviewed-signed-mc-t1.json"),
    }
    access = tmp_path / "access.json"
    _write(access, review)
    monkeypatch.setattr(workflow, "load_research_data", lambda *a, **k: "frame")
    monkeypatch.setattr(workflow, "_claim_assessment", lambda *a, **k: None, raising=False)

    assert validate_self_review_access(review, access.parent)["independent"] is False
    assert workflow._assessment_frame(prepared, overlay, frozen, protocol, access, "assessment-mu1") == "frame"
