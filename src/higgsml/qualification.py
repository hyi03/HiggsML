"""Conservative interpretation of P0/T1 contracts, never scientific approval.

Legacy v1 ``validated`` is accepted for software replay only. Independent
packages and assessment history retain their separate downstream gates.
"""
from pathlib import Path

from jsonschema import Draft202012Validator

from higgsml.artifacts import read_json
from higgsml.errors import ResearchError


def contract_qualification(checked=False):
    return {
        "schema_version": "h4l-evidence-qualification-v2",
        "contract_checked": bool(checked),
        "source_audited": False,
        "independent_numerical_validation": False,
        "physical_applicability": False,
        "confirmatory_eligibility": False,
    }


def contract_checked(evidence, kind):
    if not isinstance(evidence, dict) or not evidence.get("evidence_id"):
        return False
    version = evidence.get("schema_version")
    if version == f"h4l-{kind}-validation-v2":
        schema = Path(__file__).resolve().parents[2] / "config/schemas" / f"{kind}_validation_v2.schema.json"
        try:
            Draft202012Validator(read_json(schema)).validate(evidence)
        except Exception as exc:
            raise ResearchError(f"Invalid {kind.upper()} v2 contract evidence") from exc
        return evidence["status"] == "contract_checked"
    if version not in (None, f"h4l-{kind}-validation-v1"):
        return False
    # Historical callers also supplied unversioned synthetic fixtures. This
    # compatibility path confers no source, numerical or scientific approval.
    return evidence.get("status") == "validated"
