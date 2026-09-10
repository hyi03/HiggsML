from __future__ import annotations

from pathlib import Path
import hashlib
import json
import subprocess
import sys
import uuid

import pytest
from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREPARE_SCRIPT = PROJECT_ROOT / "scripts" / "h4l_prepare.py"
RUN_SCRIPT = PROJECT_ROOT / "scripts" / "h4l_run.py"
VALIDATION_ROOT = PROJECT_ROOT / "config" / "validation"


def _dataset_receipt(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    dataset_root = tmp_path / "atlas2020_4lep"
    dataset_root.mkdir()
    files = {
        "higgs": dataset_root / "mc_345060.ggH125_ZZ4lep.4lep.root",
        "zz": dataset_root / "mc_363490.llll.4lep.root",
    }
    members = []
    for role, path in files.items():
        payload = f"controlled-{role}-fixture".encode()
        path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        members.append({
            "role": role,
            "filename": path.name,
            "sha256": digest,
            "actual_sha256": digest,
            "size_bytes": len(payload),
            "actual_size_bytes": len(payload),
        })
    receipt = {
        "schema_version": "higgsml.download-receipt.v1",
        "status": "complete",
        "dataset_name": "atlas2020_4lep",
        "mc_only": True,
        "validation_scope": "file_bytes_only",
        "members": members,
    }
    receipt_path = dataset_root / "dataset_receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return receipt_path, files


def _write_input_package(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    receipt, _ = _dataset_receipt(tmp_path)
    package = tmp_path / "evidence-package"
    completed = _run(
        PREPARE_SCRIPT,
        "--dataset-receipt", str(receipt),
        "--write-input-package", str(package),
    )
    assert completed.returncode == 0, completed.stderr
    return (
        receipt,
        package / "h4l-root-input-v1-manifest.json",
        package / "p0-validation.pending.json",
        package / "t1-validation.pending.json",
    )


def _complete_pending_evidence(
    p0_path: Path, t1_path: Path, *, status: str = "validated"
) -> None:
    p0 = json.loads(p0_path.read_text(encoding="utf-8"))
    p0.update(
        status=status,
        evidence_id="independent-p0-review-001",
        independent_reference="external-review-record:p0-001",
    )
    for name, definition in p0["physical_definitions"].items():
        definition.update(status="validated", reference=f"external-review-record:{name}")
    p0_path.write_text(json.dumps(p0), encoding="utf-8")

    t1 = json.loads(t1_path.read_text(encoding="utf-8"))
    t1.update(
        status=status,
        evidence_id="independent-t1-review-001",
        independent_reference="external-review-record:t1-001",
        validation_summary={
            "reviewed_by": "independent-reviewer",
            "reviewed_at": "2026-09-10T00:00:00Z",
            "numerical_tests": ["independent shapesys reference comparison"],
        },
    )
    t1_path.write_text(json.dumps(t1), encoding="utf-8")


def _new_run_root(prefix: str) -> Path:
    return PROJECT_ROOT / "runs" / f"{prefix}-{uuid.uuid4().hex}"


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_write_input_package_generates_manifest_and_pending_valid_templates(
    tmp_path: Path,
) -> None:
    receipt, manifest_path, p0_path, t1_path = _write_input_package(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt_value = json.loads(receipt.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "h4l-root-input-v1"
    assert manifest["mc_only"] is True
    for member in receipt_value["members"]:
        item = manifest["files"][member["role"]]
        source = receipt.parent / member["filename"]
        assert item == {
            "path": str(source.resolve()),
            "sha256": member["actual_sha256"],
            "verified_size_bytes": source.stat().st_size,
            "verified_mtime_ns": source.stat().st_mtime_ns,
        }

    for schema_name, instance_path in (
        ("h4l_root_input_v1.schema.json", manifest_path),
        ("p0_validation_v1.schema.json", p0_path),
        ("t1_validation_v1.schema.json", t1_path),
    ):
        schema = json.loads((VALIDATION_ROOT / schema_name).read_text(encoding="utf-8"))
        instance = json.loads(instance_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(instance)
    assert json.loads(p0_path.read_text(encoding="utf-8"))["status"] == "pending"
    assert json.loads(t1_path.read_text(encoding="utf-8"))["status"] == "pending"


def test_prepare_plan_accepts_reviewed_bound_evidence_without_creating_run(
    tmp_path: Path,
) -> None:
    receipt, _, p0_validation, t1_validation = _write_input_package(tmp_path)
    _complete_pending_evidence(p0_validation, t1_validation)
    run_root = _new_run_root("pytest-prepare-plan")

    completed = _run(
        PREPARE_SCRIPT,
        "--dataset-receipt", str(receipt),
        "--p0-validation", str(p0_validation),
        "--t1-validation", str(t1_validation),
        "--run-root", str(run_root),
        "--plan-only",
    )

    assert completed.returncode == 0, completed.stderr
    output = completed.stdout
    for expected in (
        "src.cli.research audit",
        "src.cli.research prepare",
        "--candidate M0c",
        "--candidate M2",
        "--candidate M3",
        "--transform physical",
        "src.cli.research templates",
        "h4l_run.py",
    ):
        assert expected in output
    assert not run_root.exists()


def test_validate_promotes_both_complete_evidence_after_full_validation(
    tmp_path: Path,
) -> None:
    receipt, _, p0_validation, t1_validation = _write_input_package(tmp_path)
    _complete_pending_evidence(p0_validation, t1_validation, status="pending")

    completed = _run(
        PREPARE_SCRIPT,
        "--dataset-receipt", str(receipt),
        "--p0-validation", str(p0_validation),
        "--t1-validation", str(t1_validation),
        "--validate",
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(p0_validation.read_text(encoding="utf-8"))["status"] == "validated"
    assert json.loads(t1_validation.read_text(encoding="utf-8"))["status"] == "validated"


def test_validate_refuses_blank_pending_templates_without_changing_status(
    tmp_path: Path,
) -> None:
    receipt, _, p0_validation, t1_validation = _write_input_package(tmp_path)

    completed = _run(
        PREPARE_SCRIPT,
        "--dataset-receipt", str(receipt),
        "--p0-validation", str(p0_validation),
        "--t1-validation", str(t1_validation),
        "--validate",
    )

    assert completed.returncode == 3
    assert "independent review" in (completed.stdout + completed.stderr).lower()
    assert json.loads(p0_validation.read_text(encoding="utf-8"))["status"] == "pending"
    assert json.loads(t1_validation.read_text(encoding="utf-8"))["status"] == "pending"


def test_prepare_plan_rejects_pending_evidence(tmp_path: Path) -> None:
    receipt, _, p0_validation, t1_validation = _write_input_package(tmp_path)
    run_root = _new_run_root("pytest-prepare-pending")

    completed = _run(
        PREPARE_SCRIPT,
        "--dataset-receipt", str(receipt),
        "--p0-validation", str(p0_validation),
        "--t1-validation", str(t1_validation),
        "--run-root", str(run_root),
        "--plan-only",
    )

    assert completed.returncode != 0
    assert "pending" in (completed.stdout + completed.stderr).lower()
    assert not run_root.exists()


def test_run_plan_covers_all_combinations_without_creating_run() -> None:
    output_root = _new_run_root("pytest-run-plan")

    completed = _run(
        RUN_SCRIPT,
        "--seed", "42",
        "--output-root", str(output_root),
        "--plan-only",
    )

    assert completed.returncode == 0, completed.stderr
    output = completed.stdout
    assert output.count("src.cli.research train") == 16
    assert output.count("src.cli.research calibrate") == 16
    assert "--groups ABCD" in output
    assert "src.cli.research templates" in output
    assert "src.cli.research infer" in output
    assert "src.cli.research report" in output
    assert not output_root.exists()


def test_run_refuses_pending_t1_before_starting_batch(tmp_path: Path) -> None:
    _, _, _, t1_validation = _write_input_package(tmp_path)
    prepared = tmp_path / "prepared"
    gate = tmp_path / "gate"
    prepared.mkdir()
    gate.mkdir()
    output_root = _new_run_root("pytest-run-pending")

    completed = _run(
        RUN_SCRIPT,
        "--prepared-run", str(prepared),
        "--gate-run", str(gate),
        "--t1-validation", str(t1_validation),
        "--output-root", str(output_root),
    )

    assert completed.returncode == 3
    assert "pending" in (completed.stdout + completed.stderr).lower()
    assert "src.cli.research train" not in completed.stdout
    assert not output_root.exists()


@pytest.mark.parametrize("seed", [41, 47])
def test_run_rejects_seed_outside_registered_range(seed: int) -> None:
    completed = _run(RUN_SCRIPT, "--seed", str(seed), "--plan-only")

    assert completed.returncode == 2
    assert "invalid choice" in completed.stderr.lower()
