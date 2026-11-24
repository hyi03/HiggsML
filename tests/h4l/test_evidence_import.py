import hashlib

import pytest

from higgsml.errors import ResearchError
from higgsml.inference.evidence import validate_evidence_package


PROTOCOL = "a" * 64


def package(evidence_type="signed_mc_t1", status="external_pending"):
    return {"schema_version": "h4l-independent-evidence-v1", "evidence_type": evidence_type,
            "status": status, "dataset": "atlas2020_4lep", "protocol_sha256": PROTOCOL,
            "prepared_artifact_id": None, "scope": "test scope", "independent": False,
            "reference": {}, "findings": [], "limitations": ["external evidence absent"]}


def receipt(tmp_path):
    path = tmp_path / "reference.json"
    path.write_bytes(b"independent reference")
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size}


def test_pending_evidence_is_importable_without_becoming_validated():
    result = validate_evidence_package(package(), dataset="atlas2020_4lep", protocol_sha256=PROTOCOL)
    assert result["status"] == "external_pending" and result["evidence_id"]


def test_validated_label_cannot_be_asserted_by_boolean_alone(tmp_path):
    value = package(status="validated")
    value.update(independent=True, reference={})
    with pytest.raises(ResearchError, match="independent nonempty reference"):
        validate_evidence_package(value, dataset="atlas2020_4lep", protocol_sha256=PROTOCOL,
                                  package_root=tmp_path)


def test_validated_evidence_verifies_file_receipt(tmp_path):
    value = package(evidence_type="signed_mc_t1", status="validated")
    value.update(independent=True, reference={
        "producer": "external-lab", "reference_id": "t1-run-1",
        "independence_basis": "independent numerical implementation", "files": [receipt(tmp_path)],
        "closure_cases": 2, "coverage_cases": 2, "covariance_validated": True,
        "low_count_scope": "registered low-count cases"})
    result = validate_evidence_package(value, dataset="atlas2020_4lep", protocol_sha256=PROTOCOL,
                                       package_root=tmp_path)
    assert result["status"] == "validated"
    value["reference"]["files"][0]["sha256"] = "0" * 64
    with pytest.raises(ResearchError, match="receipt mismatch"):
        validate_evidence_package(value, dataset="atlas2020_4lep", protocol_sha256=PROTOCOL,
                                  package_root=tmp_path)


def test_evidence_population_and_protocol_mismatches_are_rejected():
    value = package()
    with pytest.raises(ResearchError, match="dataset/protocol mismatch"):
        validate_evidence_package(value, dataset="atlas2020_4lep", protocol_sha256="b" * 64)


def test_physical_evidence_rejects_unsupported_template_variations(tmp_path):
    value = package(evidence_type="physical_systematics", status="validated")
    value.update(independent=True, reference={
        "producer": "external-lab", "reference_id": "syst-1", "independence_basis": "external samples",
        "files": [receipt(tmp_path)], "source": "generator campaign receipt",
        "variations": [{"name": "bad", "type": "arbitrary", "up": [1], "down": [1], "processes": ["zz"]}],
        "nuisance_definitions": [{"name": "bad"}]})
    with pytest.raises(ResearchError, match="unsupported"):
        validate_evidence_package(value, dataset="atlas2020_4lep", protocol_sha256=PROTOCOL,
                                  package_root=tmp_path)
