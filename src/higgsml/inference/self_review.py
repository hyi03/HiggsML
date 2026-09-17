"""Generate and validate explicitly non-independent single-researcher access reviews."""
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


def _manifest(path: Path) -> dict:
    value = read_json(path / "manifest.json")
    artifact_id = value.get("artifact_id")
    if not isinstance(artifact_id, str) or len(artifact_id) != 64:
        raise ResearchError(f"invalid artifact manifest: {path}")
    return value


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _receipt(path: Path) -> dict:
    return {"path": path.name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def generate_self_review(run_root, prepared_root, *, reviewer: str, evaluation_version='v1') -> Path:
    """Publish a self-review package without representing it as independent evidence."""
    run_root, prepared_root = Path(run_root).resolve(), Path(prepared_root).resolve()
    reviewer = reviewer.strip()
    if not reviewer or "automat" in reviewer.lower():
        raise ResearchError("a named human single researcher is required")
    if evaluation_version not in {'v1','v2'}:
        raise ResearchError('unsupported self-review evaluation version')
    output = run_root / ('source-access-review' if evaluation_version == 'v2' else 'access-review')
    if output.exists():
        raise ResearchError(f"access-review already exists and will not be overwritten: {output}")

    prepared = _manifest(prepared_root)
    registration = read_json(run_root / "register" / "registration.json")
    nominal = _manifest(run_root / "nominal")
    frozen_manifest = _manifest(run_root / "freeze")
    frozen = read_json(run_root / "freeze" / "freeze.json")
    plan = read_json(run_root / ('evaluation-plan' if evaluation_version == 'v2' else 'report-B') / "evaluation-plan.json")
    # Stage B owns the evaluation protocol. A forced debug run may reuse a
    # prepared artifact whose historical protocol snapshot intentionally differs.
    protocol = read_json(run_root / "freeze" / "protocol.json")
    protocol_sha256 = digest_json(protocol)
    bindings = {
        "prepared_artifact_id": prepared["artifact_id"],
        "population_id": registration.get("population_id"),
        "protocol_sha256": protocol_sha256,
        "freeze_artifact_id": frozen_manifest["artifact_id"],
    }
    if (registration.get("prepared_artifact_id") != bindings["prepared_artifact_id"]
            or registration.get("protocol_sha256") != protocol_sha256
            or frozen.get("prepared_artifact_id") != bindings["prepared_artifact_id"]
            or frozen.get("template_artifact_id") != nominal["artifact_id"]
            or frozen.get("protocol_sha256") != protocol_sha256
            or plan.get("inputs", {}).get("prepared_artifact_id") != bindings["prepared_artifact_id"]
            or plan.get("inputs", {}).get("template_artifact_id") != nominal["artifact_id"]
            or plan.get("inputs", {}).get("freeze_artifact_id") != bindings["freeze_artifact_id"]):
        raise ResearchError("Stage B artifacts are not consistently bound")

    p0_source = prepared_root / "p0-validation.json"
    t1_source = run_root / "nominal" / "t1-validation.json"
    if evaluation_version == 'v2':
        from higgsml.inference import seed_workflow
        values = seed_workflow.load_frozen(run_root/'register',run_root/'nominal',run_root/'freeze',protocol)
        bound_prepared, source_nominal = values[2], values[4]
        if bound_prepared.path != prepared_root:
            raise ResearchError('v2 self-review prepared source mismatch')
        if seed_workflow.source_history(bound_prepared):
            raise ResearchError('historically opened population cannot receive new v2 self-review access')
        seed_workflow.validate_plan(plan,protocol)
        t1_source = source_nominal.file('t1-validation.json')
    if not p0_source.is_file() or not t1_source.is_file():
        raise ResearchError("bound automated P0/T1 material is missing")

    staging = run_root / f".access-review.{uuid.uuid4().hex}.staging"
    staging.mkdir()
    try:
        common = {"schema_version": EVIDENCE_SCHEMA, "review_mode": MODE,
                  "reviewer": reviewer, "independent": False, **bindings,
                  "limitations": ["single researcher self-review; not independently validated"]}
        p0 = {**common, "evidence_kind": "p0", "source": str(p0_source),
              "source_sha256": sha256_file(p0_source),
              "reviewed_definitions": ["processes", "units", "four_vectors", "pairing", "weights", "selection"]}
        t1 = {**common, "evidence_kind": "signed_mc_t1", "source": str(t1_source),
              "source_sha256": sha256_file(t1_source),
              "reviewed_scope": ["software_contract", "covariance_contract", "low_count_contract"]}
        p0_path = staging / "self-reviewed-p0-applicability.json"
        t1_path = staging / "self-reviewed-signed-mc-t1.json"
        _write(p0_path, p0)
        _write(t1_path, t1)
        review = {"schema_version": "h4l-off-assessment-access-v1", "status": STATUS,
                  "review_mode": MODE, "independent": False, "reviewer": reviewer, **bindings,
                  "history_review": "self_reviewed_unused_assessment_population",
                  "role_isolation": "self_reviewed_physical_groups_disjoint",
                  "allowed_conclusions": CONCLUSIONS,
                  "p0_reference": _receipt(p0_path), "t1_reference": _receipt(t1_path)}
        access = staging / "validated-off-assessment-access.json"
        _write(access, review)
        validate_self_review_access(review, staging)
        staging.rename(output)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    source_access = output / 'validated-off-assessment-access.json'
    if evaluation_version == 'v2':
        seed_workflow.access_adapter(run_root/'register',run_root/'nominal',run_root/'freeze',protocol,
            run_root/'access-review',run_root.parent,evaluation_plan_path=run_root/'evaluation-plan'/'evaluation-plan.json',
            result_path=run_root/'asimov',access_review=source_access)
        return run_root/'access-review'/'validated-off-assessment-access.json'
    return source_access


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
