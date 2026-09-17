"""Schema checks for synthetic examples and produced workflow artifacts."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from higgsml.errors import ResearchError
from higgsml.inference.seed_schema import validate_workflow_document
from higgsml.inference import seed_workflow as workflow


ROOT = Path(__file__).parents[2]
EXAMPLES = {
    "h4l_mass_off_registration_v2.json",
    "h4l_mass_off_compatibility_audit_v1.json",
    "h4l_joint_support_workflow_v1.json",
    "h4l_mass_off_evaluation_spec_v2.json",
    "h4l_mass_off_freeze_v2.json",
    "h4l_mass_off_evaluation_plan_v2.json",
    "h4l_off_assessment_access_v2.json",
}


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_synthetic_examples_are_schema_valid(name):
    value = json.loads((ROOT / "config" / "examples" / name).read_text(encoding="utf-8"))
    assert validate_workflow_document(value) is value


def test_schema_rejects_bad_identity_shape_and_unknown_version():
    registration = json.loads((ROOT / "config" / "examples" / "h4l_mass_off_registration_v2.json").read_text())
    bad = deepcopy(registration)
    bad["candidate_keys"] = bad["candidate_keys"][:-1]
    with pytest.raises(ResearchError, match="too short"):
        validate_workflow_document(bad)
    bad = deepcopy(registration)
    bad["schema_version"] = "h4l-mass-off-registration-v2-typo"
    with pytest.raises(ResearchError, match="unsupported"):
        validate_workflow_document(bad)


def test_schema_rejects_circular_specification_fields_and_changed_budget():
    spec = json.loads((ROOT / "config" / "examples" / "h4l_mass_off_evaluation_spec_v2.json").read_text())
    spec["freeze_artifact_id"] = "f" * 64
    with pytest.raises(ResearchError, match="Additional properties"):
        validate_workflow_document(spec)
    spec.pop("freeze_artifact_id")
    spec["budgets"]["toys"]["count"] = 499
    with pytest.raises(ResearchError, match="was expected"):
        validate_workflow_document(spec)


def test_actual_support_spec_freeze_and_plan_artifacts_validate(tmp_path, monkeypatch):
    from test_seed_workflow import _fixture, _planned

    root, protocol, _ = _fixture(tmp_path, monkeypatch)
    plan_path = _planned(root, protocol, monkeypatch)
    paths = [
        root / "support-j0" / "joint-support-summary.json",
        root / "support-j1" / "joint-support-summary.json",
        root / "evaluation-spec" / "evaluation-spec.json",
        root / "freeze" / "freeze.json",
        plan_path,
    ]
    for path in paths:
        validate_workflow_document(workflow.read_json(path))
