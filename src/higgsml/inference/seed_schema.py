"""JSON Schema validation for the owned within-seed workflow documents."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from higgsml.errors import ResearchError


_SCHEMAS = {
    "h4l-mass-off-registration-v3": "h4l_mass_off_registration.schema.json",
    "h4l-mass-off-compatibility-audit-v3": "h4l_mass_off_compatibility_audit.schema.json",
    "h4l-mass-off-evaluation-spec-v3": "h4l_mass_off_evaluation_spec.schema.json",
    "h4l-mass-off-freeze-v3": "h4l_mass_off_freeze.schema.json",
    "h4l-mass-off-evaluation-plan-v3": "h4l_mass_off_evaluation_plan.schema.json",
    "h4l-off-assessment-access-v3": "h4l_off_assessment_access.schema.json",
    "h4l-marginal-support-workflow-v1": "h4l_marginal_support_workflow.schema.json",
}


def validate_workflow_document(value):
    """Validate one owned workflow document and return it unchanged."""
    if not isinstance(value, dict):
        raise ResearchError("workflow document must be an object")
    version = value.get("schema_version")
    name = _SCHEMAS.get(version)
    if name is None:
        raise ResearchError(f"unsupported workflow schema_version: {version!r}")
    if version == "h4l-mass-off-evaluation-plan-v3":
        validate_workflow_document(value.get("specification"))
    path = Path(__file__).parents[3] / "config" / "schemas" / name
    try:
        Draft202012Validator(json.loads(path.read_text(encoding="utf-8"))).validate(value)
    except ValidationError as error:
        location = ".".join(map(str, error.absolute_path)) or "<root>"
        raise ResearchError(f"invalid {version} document at {location}: {error.message}") from error
    return value
