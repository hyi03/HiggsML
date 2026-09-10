#!/usr/bin/env python3
"""Build reviewed H4l inputs, then prepare the controlled feature batch."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from tqdm.auto import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT.parent
RUNS_ROOT = (PROJECT_ROOT / "runs").resolve()
PROTOCOL = (PROJECT_ROOT / "config" / "research_protocol_v1.json").resolve()
PROFILE = (PROJECT_ROOT / "config" / "profiles" / "open_data_2020.yaml").resolve()
RUN_SCRIPT = (PROJECT_ROOT / "scripts" / "h4l_run.py").resolve()
VALIDATION_ROOT = (PROJECT_ROOT / "config" / "validation").resolve()
DEFAULT_RECEIPT = (
    REPOSITORY_ROOT / "data" / "raw" / "atlas2020_4lep" / "dataset_receipt.json"
).resolve()
DATASET = "atlas2020_4lep"
MANIFEST_NAME = "h4l-root-input-v1-manifest.json"
P0_VALIDATION_NAME = "p0-validation.json"
T1_VALIDATION_NAME = "t1-validation.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dataset_binding import dataset_context  # noqa: E402
from src.research.artifacts import digest_json  # noqa: E402
from src.research.protocol import load_protocol  # noqa: E402


class WorkflowError(Exception):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate bound H4l inputs and run audit, prepare, and G1.",
    )
    parser.add_argument("--dataset-receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Validate inputs and print commands without creating runs.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the prerequisite-stage progress bar.",
    )
    return parser


def _resolve(value: Path) -> Path:
    candidate = value.expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowError(f"Invalid JSON artifact: {path}: {error}", 3) from error
    if not isinstance(value, dict):
        raise WorkflowError(f"JSON artifact must be an object: {path}", 3)
    return value


def _validate_schema(value: dict, schema_name: str, label: str) -> None:
    schema = _load_json(VALIDATION_ROOT / schema_name)
    try:
        Draft202012Validator(schema).validate(value)
    except ValidationError as error:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise WorkflowError(
            f"{label} does not satisfy {schema_name} at {location}: {error.message}", 3
        ) from error


def _write_json_new(path: Path, value: dict) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    except OSError as error:
        raise WorkflowError(f"Cannot write JSON artifact {path}: {error}", 4) from error


def _manifest_from_receipt(receipt_path: Path) -> dict:
    receipt = _load_json(receipt_path)
    if (
        receipt.get("schema_version") != "higgsml.download-receipt.v1"
        or receipt.get("status") != "complete"
        or receipt.get("dataset_name") != DATASET
        or receipt.get("mc_only") is not True
    ):
        raise WorkflowError(
            "Dataset receipt must be a complete atlas2020_4lep MC-only download receipt.", 3
        )
    members = receipt.get("members")
    if not isinstance(members, list) or len(members) != 2:
        raise WorkflowError("Dataset receipt must contain exactly the higgs and zz members.", 3)
    by_role = {
        member.get("role"): member for member in members if isinstance(member, dict)
    }
    if set(by_role) != {"higgs", "zz"}:
        raise WorkflowError("Dataset receipt roles must be exactly higgs and zz.", 3)

    receipt_root = receipt_path.parent.resolve()
    files = {}
    for role in ("higgs", "zz"):
        member = by_role[role]
        filename = member.get("filename")
        digest = member.get("actual_sha256")
        actual_size = member.get("actual_size_bytes")
        if (
            not isinstance(filename, str)
            or not filename
            or member.get("sha256") != digest
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or member.get("size_bytes") != actual_size
            or not isinstance(actual_size, int)
            or actual_size < 1
        ):
            raise WorkflowError(f"Dataset receipt member {role} has inconsistent size/hash evidence.", 3)
        source = (receipt_root / filename).resolve()
        if source.parent != receipt_root or not source.is_file():
            raise WorkflowError(f"Dataset receipt member is missing or leaves its directory: {source}", 3)
        stat = source.stat()
        if stat.st_size != actual_size:
            raise WorkflowError(f"Dataset receipt size no longer matches local file: {source}", 3)
        files[role] = {
            "path": str(source),
            "sha256": digest,
            "verified_size_bytes": stat.st_size,
            "verified_mtime_ns": stat.st_mtime_ns,
        }
    manifest = {
        "schema_version": "h4l-root-input-v1",
        "dataset": DATASET,
        "mc_only": True,
        "files": files,
    }
    _validate_schema(manifest, "h4l_root_input_v1.schema.json", "ROOT manifest")
    return manifest


def _binding_digests(manifest: dict) -> tuple[str, str]:
    protocol = load_protocol(PROTOCOL, dataset=DATASET).to_dict()
    protocol_sha256 = digest_json(protocol)
    source_evidence_sha256 = digest_json(
        {
            "dataset_snapshot": dataset_context(DATASET).snapshot(),
            "manifest": manifest,
            "payload_access": "development_entries_only",
            "acquisition_hash_reverified": False,
        }
    )
    return protocol_sha256, source_evidence_sha256


def _automated_validations(manifest: dict) -> tuple[dict, dict]:
    protocol_sha256, source_evidence_sha256 = _binding_digests(manifest)
    contract_reference = f"automated-not-independent:{protocol_sha256}"
    p0 = {
        "schema_version": "h4l-p0-validation-v1",
        "status": "validated",
        "dataset": DATASET,
        "protocol_sha256": protocol_sha256,
        "source_evidence_sha256": source_evidence_sha256,
        "evidence_id": f"automated-p0-{source_evidence_sha256[:16]}",
        "independent_reference": contract_reference,
        "physical_definitions": {
            "processes": {"status": "validated", "reference": "dataset-receipt:higgs,zz"},
            "units": {"status": "validated", "reference": "open_data_2020.yaml:momentum_unit"},
            "four_vectors": {"status": "validated", "reference": "src/domain/four_vectors.py"},
            "pairing": {"status": "validated", "reference": "src/domain/reconstruction.py:pair_four_leptons"},
            "weights": {"status": "validated", "reference": "src/domain/weights.py:physical_event_weight"},
            "selection": {"status": "validated", "reference": "src/domain/selection.py"},
        },
    }
    t1_contract = {
        "correlation": "independent_process_bins",
        "auxiliary": "poisson_tau_gamma",
        "modifier": "shapesys",
        "pyhf_version": "0.7.6",
    }
    t1 = {
        "schema_version": "h4l-t1-validation-v1",
        "status": "validated",
        "dataset": DATASET,
        "protocol_sha256": protocol_sha256,
        "evidence_id": f"automated-t1-{digest_json(t1_contract)[:16]}",
        "independent_reference": contract_reference,
        **t1_contract,
        "validation_summary": {
            "reviewed_by": "scripts/h4l_prepare.py",
            "reviewed_at": "generated-from-bound-repository-contract",
            "numerical_tests": ["schema and frozen T1 contract validation"],
        },
    }
    _validate_schema(p0, "p0_validation_v1.schema.json", "Automated P0 validation")
    _validate_schema(t1, "t1_validation_v1.schema.json", "Automated T1 validation")
    return p0, t1


def _validate_bound_evidence(p0: dict, t1: dict, manifest: dict) -> None:
    _validate_schema(p0, "p0_validation_v1.schema.json", "P0 validation")
    _validate_schema(t1, "t1_validation_v1.schema.json", "T1 validation")
    protocol_sha256, source_evidence_sha256 = _binding_digests(manifest)
    if p0.get("status") != "validated" or t1.get("status") != "validated":
        pending = [name for name, value in (("P0", p0), ("T1", t1)) if value.get("status") == "pending"]
        detail = "/".join(pending) if pending else "P0/T1"
        raise WorkflowError(
            f"{detail} evidence is pending; controlled MC requires independent review before validation.", 3
        )
    if (
        p0.get("dataset") != DATASET
        or p0.get("protocol_sha256") != protocol_sha256
        or p0.get("source_evidence_sha256") != source_evidence_sha256
        or t1.get("dataset") != DATASET
        or t1.get("protocol_sha256") != protocol_sha256
    ):
        raise WorkflowError("P0/T1 evidence does not match the current dataset, protocol, and ROOT source.", 3)
    expected_t1 = {
        "correlation": "independent_process_bins",
        "auxiliary": "poisson_tau_gamma",
        "modifier": "shapesys",
        "pyhf_version": "0.7.6",
    }
    if any(t1.get(key) != value for key, value in expected_t1.items()):
        raise WorkflowError("T1 evidence does not match the frozen statistical model.", 3)


def _display(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _invoke(arguments: list[str], *, plan_only: bool) -> None:
    command = [sys.executable, "-m", "src.cli.research", *arguments]
    print(_display(command), flush=True)
    if plan_only:
        return
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode != 0:
        raise WorkflowError(
            f"higgsml-research failed with exit code {completed.returncode}",
            completed.returncode,
        )


def _validate_run_root(run_root: Path) -> None:
    try:
        relative = run_root.relative_to(RUNS_ROOT)
    except ValueError as error:
        raise WorkflowError(
            f"RunRoot must be a child of the neural/runs directory: {run_root}", 4
        ) from error
    if not relative.parts:
        raise WorkflowError("RunRoot cannot be the neural/runs directory itself", 4)
    if run_root.exists():
        raise WorkflowError(f"RunRoot already exists and cannot be reused: {run_root}", 4)


def _run_workflow(args: argparse.Namespace, receipt: Path) -> None:
    run_root = _resolve(args.run_root)
    _validate_run_root(run_root)
    for required in (PROTOCOL, PROFILE, RUN_SCRIPT):
        if not required.is_file():
            raise WorkflowError(f"Required project file does not exist: {required}", 3)

    manifest = _manifest_from_receipt(receipt)
    p0, t1 = _automated_validations(manifest)
    _validate_bound_evidence(p0, t1, manifest)

    inputs_root = run_root / "inputs"
    root_manifest = inputs_root / MANIFEST_NAME
    p0_validation = inputs_root / P0_VALIDATION_NAME
    t1_validation = inputs_root / T1_VALIDATION_NAME
    if not args.plan_only:
        inputs_root.mkdir(parents=True)
        _write_json_new(root_manifest, manifest)
        _write_json_new(p0_validation, p0)
        _write_json_new(t1_validation, t1)
        print(f"Wrote automatically bound inputs: {inputs_root}")

    audit_run = run_root / "audit"
    prepared_run = run_root / "prepare"
    train_root = run_root / "g1" / "train"
    calibration_root = run_root / "g1" / "calibrate"
    model_runs = {name: train_root / name.lower() for name in ("M0c", "M2", "M3")}
    calibration_runs = {
        "m0c_raw": calibration_root / "m0c-raw",
        "m2_raw": calibration_root / "m2-raw",
        "m4": calibration_root / "m4-physical",
        "m3_raw": calibration_root / "m3-raw",
        "m5": calibration_root / "m5-physical",
    }
    gate_run = run_root / "g1" / "templates"
    batch_root = run_root / "batch" / "seed42"
    common = ["--dataset", DATASET, "--protocol", str(PROTOCOL)]

    steps = [
        (
            "audit",
            ["audit", *common, "--input-manifest", str(root_manifest), "--run-dir", str(audit_run)],
        ),
        (
            "prepare",
            [
                "prepare", *common,
                "--input-manifest", str(root_manifest),
                "--profile", str(PROFILE),
                "--p0-validation", str(p0_validation),
                "--run-dir", str(prepared_run),
            ],
        ),
    ]
    for candidate in ("M0c", "M2", "M3"):
        steps.append(
            (
                f"train {candidate}",
                [
                    "train", *common,
                    "--input-run", str(prepared_run),
                    "--candidate", candidate,
                    "--seed", "42",
                    "--run-dir", str(model_runs[candidate]),
                ],
            )
        )

    calibration_specs = (
        ("M0c", "raw", calibration_runs["m0c_raw"]),
        ("M2", "raw", calibration_runs["m2_raw"]),
        ("M2", "physical", calibration_runs["m4"]),
        ("M3", "raw", calibration_runs["m3_raw"]),
        ("M3", "physical", calibration_runs["m5"]),
    )
    for candidate, transform, output in calibration_specs:
        steps.append(
            (
                f"calibrate {candidate} {transform}",
                [
                    "calibrate", *common,
                    "--input-run", str(prepared_run),
                    "--model-run", str(model_runs[candidate]),
                    "--transform", transform,
                    "--run-dir", str(output),
                ],
            )
        )

    template_arguments = ["templates", *common, "--input-run", str(prepared_run)]
    for calibration_run in calibration_runs.values():
        template_arguments.extend(["--calibration-run", str(calibration_run)])
    template_arguments.extend(
        ["--t1-validation", str(t1_validation), "--run-dir", str(gate_run)]
    )
    steps.append(("templates", template_arguments))

    with tqdm(
        steps,
        desc="H4l prerequisites",
        unit="stage",
        disable=args.plan_only or args.no_progress,
    ) as progress:
        for label, arguments in progress:
            progress.set_postfix_str(label, refresh=True)
            _invoke(arguments, plan_only=args.plan_only)

    if not args.plan_only:
        g1_path = gate_run / "g1.json"
        status = _load_json(g1_path).get("status")
        print(f"G1 status: {status}")
        if status != "passed":
            raise WorkflowError(
                "G1 did not pass; do not start the feature-combination batch.", 5
            )

    next_command = [
        sys.executable, str(RUN_SCRIPT),
        "--seed", "42",
        "--prepared-run", str(prepared_run),
        "--gate-run", str(gate_run),
        "--t1-validation", str(t1_validation),
        "--output-root", str(batch_root),
    ]
    print("Next batch command:")
    print(_display(next_command))
    if args.plan_only:
        print("Plan complete; no run was created.")
    else:
        print("Prerequisites complete; assessment remains unopened.")


def _run(args: argparse.Namespace) -> None:
    receipt = _resolve(args.dataset_receipt)
    _run_workflow(args, receipt)


def main() -> int:
    try:
        _run(_parser().parse_args())
    except WorkflowError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
