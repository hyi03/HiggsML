import json
from pathlib import Path

from higgsml.artifacts import digest_json, sha256_file


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_generate_default_self_review_binds_current_stage_b(tmp_path):
    from higgsml.inference.self_review import generate_self_review

    prepared = tmp_path / "prepare"
    run = tmp_path / "h4l-off-study"
    protocol = {"dataset": "atlas2020_4lep", "id": "test"}
    _write(prepared / "manifest.json", {"artifact_id": "1" * 64})
    _write(prepared / "p0-validation.json", {"schema_version": "h4l-p0-validation-v1"})
    _write(run / "register" / "registration.json", {
        "prepared_artifact_id": "1" * 64,
        "population_id": "2" * 64,
        "protocol_sha256": digest_json(protocol),
    })
    _write(run / "freeze" / "manifest.json", {"artifact_id": "3" * 64})
    _write(run / "freeze" / "protocol.json", protocol)
    _write(run / "freeze" / "freeze.json", {
        "prepared_artifact_id": "1" * 64,
        "protocol_sha256": digest_json(protocol),
    })
    _write(run / "source-nominal" / "t1-validation.json", {
        "schema_version": "h4l-t1-validation-v1",
    })
    _write(run / "evaluation-plan" / "evaluation-plan.json", {
        "inputs": {
            "prepared_artifact_id": "1" * 64,
            "freeze_artifact_id": "3" * 64,
        }
    })

    access = generate_self_review(run, prepared, reviewer="Local Researcher")

    review = json.loads(access.read_text(encoding="utf-8"))
    assert review["review_mode"] == "single_researcher_self_review"
    assert review["independent"] is False
    assert review["allowed_conclusions"] == "exploratory_self_reviewed_not_independently_validated"
    assert review["freeze_artifact_id"] == "3" * 64
    for key in ("p0_reference", "t1_reference"):
        receipt = review[key]
        target = access.parent / receipt["path"]
        assert receipt == {
            "path": target.name,
            "sha256": sha256_file(target),
            "size_bytes": target.stat().st_size,
        }
