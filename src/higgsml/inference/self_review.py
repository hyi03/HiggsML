"""Generate and validate non-independent single-researcher access reviews."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import uuid

from higgsml.artifacts import digest_json, read_json, sha256_file
from higgsml.errors import ResearchError


MODE = "single_researcher_self_review"
STATUS = "validated_for_self_reviewed_exploratory_access"
CONCLUSIONS = "exploratory_self_reviewed_not_independently_validated"
EVIDENCE_SCHEMA = "h4l-off-self-review-evidence-v1"


def _artifact_id(path: Path) -> str:
    value = read_json(path / "manifest.json")
    artifact_id = value.get("artifact_id")
    if not isinstance(artifact_id, str) or len(artifact_id) != 64:
        raise ResearchError(f"invalid artifact manifest: {path}")
    return artifact_id


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _receipt(path: Path) -> dict:
    return {"path": path.name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def generate_self_review(run_root, prepared_root, *, reviewer: str) -> Path:
    """Publish a local exploratory source review bound to the current Stage B."""
    run_root, prepared_root = Path(run_root).resolve(), Path(prepared_root).resolve()
    reviewer = reviewer.strip()
    if not reviewer or "automat" in reviewer.lower():
        raise ResearchError("a named local researcher is required")
    output = run_root / "source-access-review"
    if output.exists():
        raise ResearchError(f"source access review already exists: {output}")

    prepared_id = _artifact_id(prepared_root)
    freeze_id = _artifact_id(run_root / "freeze")
    registration = read_json(run_root / "register" / "registration.json")
    freeze = read_json(run_root / "freeze" / "freeze.json")
    protocol = read_json(run_root / "freeze" / "protocol.json")
    plan = read_json(run_root / "evaluation-plan" / "evaluation-plan.json")
    protocol_sha256 = digest_json(protocol)
    if (registration.get("prepared_artifact_id") != prepared_id
            or registration.get("protocol_sha256") != protocol_sha256
            or freeze.get("prepared_artifact_id") != prepared_id
            or freeze.get("protocol_sha256") != protocol_sha256
            or plan.get("inputs", {}).get("prepared_artifact_id") != prepared_id
            or plan.get("inputs", {}).get("freeze_artifact_id") != freeze_id):
        raise ResearchError("Stage B artifacts are not consistently bound")

    p0_source = prepared_root / "p0-validation.json"
    t1_source = run_root / "source-nominal" / "t1-validation.json"
    if not p0_source.is_file() or not t1_source.is_file():
        raise ResearchError("bound automated P0/T1 material is missing")

    staging = run_root / f".source-access-review.{uuid.uuid4().hex}.staging"
    staging.mkdir()
    try:
        bindings = {
            "prepared_artifact_id": prepared_id,
            "population_id": registration["population_id"],
            "protocol_sha256": protocol_sha256,
            "freeze_artifact_id": freeze_id,
        }
        common = {
            "schema_version": EVIDENCE_SCHEMA,
            "review_mode": MODE,
            "reviewer": reviewer,
            "independent": False,
            **bindings,
            "limitations": ["single researcher self-review; not independently validated"],
        }
        p0_path = staging / "self-reviewed-p0-applicability.json"
        t1_path = staging / "self-reviewed-signed-mc-t1.json"
        _write(p0_path, {**common, "evidence_kind": "p0", "source": str(p0_source),
                         "source_sha256": sha256_file(p0_source)})
        _write(t1_path, {**common, "evidence_kind": "signed_mc_t1", "source": str(t1_source),
                         "source_sha256": sha256_file(t1_source)})
        review = {
            "schema_version": "h4l-off-assessment-access-v1",
            "status": STATUS,
            "review_mode": MODE,
            "independent": False,
            "reviewer": reviewer,
            **bindings,
            "history_review": "self_reviewed_unused_assessment_population",
            "role_isolation": "self_reviewed_physical_groups_disjoint",
            "allowed_conclusions": CONCLUSIONS,
            "p0_reference": _receipt(p0_path),
            "t1_reference": _receipt(t1_path),
        }
        access = staging / "validated-off-assessment-access.json"
        _write(access, review)
        validate_self_review_access(review, staging)
        staging.rename(output)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return output / "validated-off-assessment-access.json"


def validate_self_review_access(review: dict, package_root) -> dict:
    expected = {"schema_version", "status", "review_mode", "independent", "reviewer",
                "prepared_artifact_id", "population_id", "protocol_sha256", "freeze_artifact_id",
                "history_review", "role_isolation", "allowed_conclusions", "p0_reference", "t1_reference"}
    if (not isinstance(review, dict) or set(review) != expected
            or review["schema_version"] != "h4l-off-assessment-access-v1"
            or review["status"] != STATUS or review["review_mode"] != MODE
            or review["independent"] is not False or not review["reviewer"]
            or review["history_review"] != "self_reviewed_unused_assessment_population"
            or review["role_isolation"] != "self_reviewed_physical_groups_disjoint"
            or review["allowed_conclusions"] != CONCLUSIONS):
        raise ResearchError("invalid single-researcher assessment access review")
    root = Path(package_root).resolve()
    for field, kind in (("p0_reference", "p0"), ("t1_reference", "signed_mc_t1")):
        receipt = review[field]
        if not isinstance(receipt, dict) or set(receipt) != {"path", "sha256", "size_bytes"}:
            raise ResearchError("self-review evidence needs a file receipt")
        relative = Path(receipt["path"])
        target = (root / relative).resolve()
        if (relative.is_absolute() or not target.is_relative_to(root) or target.is_symlink()
                or not target.is_file() or target.stat().st_size != receipt["size_bytes"]
                or sha256_file(target) != receipt["sha256"]):
            raise ResearchError("self-review evidence receipt mismatch")
        evidence = read_json(target)
        if (evidence.get("schema_version") != EVIDENCE_SCHEMA or evidence.get("evidence_kind") != kind
                or evidence.get("review_mode") != MODE or evidence.get("independent") is not False
                or evidence.get("reviewer") != review["reviewer"]
                or any(evidence.get(key) != review[key] for key in
                       ("prepared_artifact_id", "population_id", "protocol_sha256", "freeze_artifact_id"))
                or evidence.get("limitations") != ["single researcher self-review; not independently validated"]):
            raise ResearchError("self-review evidence identity/scope mismatch")
    return review
