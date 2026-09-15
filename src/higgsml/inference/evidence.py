"""Strict, read-only ingestion of independently produced evidence packages."""
from __future__ import annotations

import platform
from pathlib import Path

from higgsml.artifacts import digest_json, sha256_file
from higgsml.errors import ResearchError


EVIDENCE_TYPES = {
    "signed_mc_t1",
    "physical_systematics",
    "mela",
    "arm64_authority",
    "frozen_assessment",
}
EVIDENCE_STATUSES = {"validated", "external_pending", "failed"}


def validate_off_p0(value, *, expected, package_root):
    """Validate numerical applicability before any assessment claim or decoding."""
    import math
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
    from higgsml.artifacts import read_json
    schema = read_json(Path(__file__).resolve().parents[3]/'config/schemas/h4l_off_p0_applicability.schema.json')
    try:
        Draft202012Validator(schema).validate(value)
    except ValidationError as error:
        raise ResearchError('invalid P0 applicability schema: '+error.message) from error
    if (value['package_id'] != digest_json({k:v for k,v in value.items() if k!='package_id'})
            or any(value.get(k)!=v for k,v in expected.items())):
        raise ResearchError('P0 applicability identity/scope mismatch')
    _validated_reference(value['reference'], 'p0', package_root)
    if 'automat' in str(value['reference']).lower():
        raise ResearchError('automatic reference cannot qualify independent P0')
    receipts = {r['path'] for r in value['reference']['files']}
    definitions = value['physical_definitions']
    if any(not set(v['reference_files']) <= receipts for v in definitions.values()):
        raise ResearchError('P0 physical definition lacks bound reference files')
    comparisons = value['numerical_comparisons']
    if {r['definition'] for r in comparisons} != set(definitions):
        raise ResearchError('P0 comparisons do not cover every physical definition')
    for row in comparisons:
        if (any(type(row[k]) not in (int,float) or not math.isfinite(row[k]) for k in ('expected','actual','atol','rtol'))
                or row['reference_path'] not in definitions[row['definition']]['reference_files']
                or abs(row['actual']-row['expected']) > row['atol']+row['rtol']*abs(row['expected'])):
            raise ResearchError('P0 numerical comparison invalid or outside declared tolerance')
    return value


def _validated_reference(reference, evidence_type, package_root):
    for field in ("producer", "reference_id", "independence_basis"):
        if not isinstance(reference.get(field), str) or not reference[field].strip():
            raise ResearchError(f"validated evidence requires reference.{field}")
    files = reference.get("files")
    if not isinstance(files, list) or not files:
        raise ResearchError("validated evidence requires at least one referenced file receipt")
    if package_root is None:
        raise ResearchError("validated evidence files require a package root")
    root = Path(package_root).resolve()
    seen = set()
    for receipt in files:
        if not isinstance(receipt, dict) or set(receipt) != {"path", "sha256", "size_bytes"}:
            raise ResearchError("invalid evidence file receipt")
        if not isinstance(receipt["path"], str) or not receipt["path"]:
            raise ResearchError("invalid evidence file receipt path")
        relative = Path(receipt["path"])
        if relative.is_absolute() or not relative.parts or relative in seen:
            raise ResearchError("evidence file paths must be unique and relative")
        seen.add(relative)
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as error:
            raise ResearchError("evidence file escapes its package directory") from error
        if path.is_symlink() or not path.is_file():
            raise ResearchError("evidence reference file is missing or unsafe")
        if (not isinstance(receipt["sha256"], str) or len(receipt["sha256"]) != 64
                or any(character not in "0123456789abcdef" for character in receipt["sha256"])
                or type(receipt["size_bytes"]) is not int or receipt["size_bytes"] < 0
                or path.stat().st_size != receipt["size_bytes"]
                or sha256_file(path) != receipt["sha256"]):
            raise ResearchError("evidence reference file receipt mismatch")
    if evidence_type == "arm64_authority":
        machine = str(reference.get("machine", "")).lower()
        if (machine not in {"arm64", "aarch64"} or reference.get("native") is not True
                or reference.get("exit_code") != 0 or not reference.get("command")
                or not isinstance(reference.get("environment_lock_sha256"), str)
                or len(reference["environment_lock_sha256"]) != 64
                or not isinstance(reference.get("comparison"), dict)):
            raise ResearchError("ARM64 authority evidence lacks a native successful reproducibility receipt")
    elif evidence_type == "physical_systematics":
        if (not reference.get("source") or not isinstance(reference.get("variations"), list)
                or not reference["variations"] or not isinstance(reference.get("nuisance_definitions"), list)
                or not reference["nuisance_definitions"]):
            raise ResearchError("physical-systematic evidence requires sourced variations and nuisances")
        for variation in reference["variations"]:
            if (not isinstance(variation, dict) or variation.get("type") not in {"normsys", "histosys"}
                    or not variation.get("name") or "up" not in variation or "down" not in variation
                    or not isinstance(variation.get("processes"), list) or not variation["processes"]):
                raise ResearchError("physical-systematic variation uses an unsupported or incomplete template type")
    elif evidence_type == "mela":
        if (not reference.get("backend") or not reference.get("configuration_id")
                or type(reference.get("compared_rows")) is not int or reference["compared_rows"] < 1
                or not isinstance(reference.get("max_relative_error"), (int, float))
                or reference["max_relative_error"] < 0):
            raise ResearchError("MELA evidence lacks a backend/configuration comparison summary")
    elif evidence_type == "signed_mc_t1":
        if (type(reference.get("closure_cases")) is not int or reference["closure_cases"] < 1
                or type(reference.get("coverage_cases")) is not int or reference["coverage_cases"] < 1
                or reference.get("covariance_validated") is not True
                or not reference.get("low_count_scope")):
            raise ResearchError("signed-MC/T1 evidence lacks closure, coverage, covariance, or low-count scope")
    elif evidence_type == "frozen_assessment":
        if (not reference.get("freeze_id") or not reference.get("claim_id")
                or not reference.get("evaluation_plan_id")
                or not isinstance(reference.get("published_result_artifact_ids"), list)
                or not reference["published_result_artifact_ids"]):
            raise ResearchError("frozen-assessment evidence lacks freeze, claim, plan, or published results")


def validate_evidence_package(value, *, dataset, protocol_sha256, package_root=None):
    required = {
        "schema_version", "evidence_type", "status", "dataset", "protocol_sha256",
        "prepared_artifact_id", "scope", "independent", "reference", "findings",
        "limitations",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ResearchError("independent evidence package has missing or unknown fields")
    if value["schema_version"] != "h4l-independent-evidence-v1":
        raise ResearchError("unsupported independent evidence schema")
    if value["evidence_type"] not in EVIDENCE_TYPES or value["status"] not in EVIDENCE_STATUSES:
        raise ResearchError("unsupported independent evidence type or status")
    if value["dataset"] != dataset or value["protocol_sha256"] != protocol_sha256:
        raise ResearchError("independent evidence dataset/protocol mismatch")
    if not isinstance(value["scope"], str) or not value["scope"].strip():
        raise ResearchError("independent evidence scope is required")
    if value["prepared_artifact_id"] is not None and not isinstance(value["prepared_artifact_id"], str):
        raise ResearchError("invalid evidence population binding")
    if type(value["independent"]) is not bool or not isinstance(value["reference"], dict):
        raise ResearchError("invalid evidence independence/reference declaration")
    if (not isinstance(value["findings"], list) or not isinstance(value["limitations"], list)
            or any(not isinstance(item, str) for item in value["limitations"])):
        raise ResearchError("evidence findings and limitations must be lists")
    if value["status"] == "validated":
        if not value["independent"] or not value["reference"]:
            raise ResearchError("validated evidence requires an independent nonempty reference")
        _validated_reference(value["reference"], value["evidence_type"], package_root)
    result = dict(value)
    result["ingested_on_machine"] = platform.machine()
    result["evidence_id"] = digest_json(value)
    return result
