from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import importlib.util
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


def _load_prepare_module():
    spec = importlib.util.spec_from_file_location("h4l_prepare_test_module", PREPARE_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_run_module():
    spec = importlib.util.spec_from_file_location("h4l_run_test_module", RUN_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_prepare_cli_has_no_manual_review_arguments() -> None:
    completed = _run(PREPARE_SCRIPT, "--help")

    assert completed.returncode == 0
    assert "--run-root" in completed.stdout
    assert "--no-progress" in completed.stdout
    for removed in ("--write-input-package", "--p0-validation", "--t1-validation", "--validate"):
        assert removed not in completed.stdout


def test_automatic_validation_is_bound_and_schema_valid(
    tmp_path: Path,
) -> None:
    prepare = _load_prepare_module()
    receipt, _ = _dataset_receipt(tmp_path)
    manifest = prepare._manifest_from_receipt(receipt)
    p0, t1 = prepare._automated_validations(manifest)
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

    for schema_name, instance in (
        ("h4l_root_input_v1.schema.json", manifest),
        ("p0_validation_v1.schema.json", p0),
        ("t1_validation_v1.schema.json", t1),
    ):
        schema = json.loads((VALIDATION_ROOT / schema_name).read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(instance)
    assert p0["status"] == "validated"
    assert t1["status"] == "validated"
    assert p0["evidence_id"].startswith("automated-p0-")
    assert t1["evidence_id"].startswith("automated-t1-")


def test_prepare_plan_uses_one_command_without_creating_run(
    tmp_path: Path,
) -> None:
    receipt, _ = _dataset_receipt(tmp_path)
    run_root = _new_run_root("pytest-prepare-plan")

    completed = _run(
        PREPARE_SCRIPT,
        "--dataset-receipt", str(receipt),
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


def test_prepare_writes_automatic_inputs_before_running_prerequisites(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prepare = _load_prepare_module()
    receipt, _ = _dataset_receipt(tmp_path)
    monkeypatch.setattr(prepare, "RUNS_ROOT", tmp_path.resolve())
    run_root = tmp_path / "run"

    def fake_invoke(arguments: list[str], *, plan_only: bool) -> None:
        assert plan_only is False
        if arguments[0] == "templates":
            gate = Path(arguments[arguments.index("--run-dir") + 1])
            gate.mkdir(parents=True)
            (gate / "g1.json").write_text('{"status":"passed"}', encoding="utf-8")

    monkeypatch.setattr(prepare, "_invoke", fake_invoke)
    prepare._run(
        argparse.Namespace(
            dataset_receipt=receipt,
            run_root=run_root,
            plan_only=False,
            no_progress=False,
        )
    )

    inputs = run_root / "inputs"
    assert json.loads((inputs / "p0-validation.json").read_text(encoding="utf-8"))["status"] == "validated"
    assert json.loads((inputs / "t1-validation.json").read_text(encoding="utf-8"))["status"] == "validated"
    assert (inputs / "h4l-root-input-v1-manifest.json").is_file()
    progress_output = capsys.readouterr().err
    assert "H4l prerequisites" in progress_output
    assert "11/11" in progress_output


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


def test_run_shows_progress_for_all_batch_stages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run = _load_run_module()
    prepared = tmp_path / "prepared"
    gate = tmp_path / "gate"
    t1_validation = tmp_path / "t1-validation.json"
    output_root = tmp_path / "batch"
    prepared.mkdir()
    gate.mkdir()
    t1_validation.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(run, "RUNS_ROOT", tmp_path.resolve())
    monkeypatch.setattr(run, "_validate_t1", lambda *_args: None)

    def fake_invoke(arguments: list[str], *, plan_only: bool) -> None:
        assert plan_only is False
        if arguments[0] == "report":
            report_run = Path(arguments[arguments.index("--run-dir") + 1])
            report_run.mkdir(parents=True)
            (report_run / "report.json").write_text(
                json.dumps({
                    "feature_combination_comparisons": [
                        {"status": "valid", "seed": 42}
                    ]
                }),
                encoding="utf-8",
            )

    monkeypatch.setattr(run, "_invoke", fake_invoke)
    run._run(
        argparse.Namespace(
            seed=42,
            config=run.DEFAULT_CONFIG,
            prepared_run=prepared,
            gate_run=gate,
            t1_validation=t1_validation,
            output_root=output_root,
            plan_only=False,
            no_progress=False,
        )
    )

    progress_output = capsys.readouterr().err
    assert "H4l batch seed 42" in progress_output
    assert "35/35" in progress_output


def test_run_cli_supports_disabling_progress() -> None:
    completed = _run(RUN_SCRIPT, "--help")

    assert completed.returncode == 0
    assert "--no-progress" in completed.stdout


@pytest.mark.parametrize("load_module", [_load_prepare_module, _load_run_module])
def test_invoke_uses_single_line_dot_progress(
    load_module,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = load_module()

    class FakeProcess:
        waits = 0

        def wait(self, *, timeout: int) -> int:
            assert timeout == 1
            self.waits += 1
            if self.waits <= 2:
                raise subprocess.TimeoutExpired(cmd="research", timeout=timeout)
            return 0

    monkeypatch.setattr(module.subprocess, "Popen", lambda *_args, **_kwargs: FakeProcess())

    module._invoke(["prepare"], plan_only=False)

    assert capsys.readouterr().err == "[h4l] stage 'prepare' running ..\n"


def test_run_refuses_pending_t1_before_starting_batch(tmp_path: Path) -> None:
    t1_validation = VALIDATION_ROOT / "t1_validation.pending.json"
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
