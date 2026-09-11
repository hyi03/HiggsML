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
G1_SCRIPT = PROJECT_ROOT / "scripts" / "h4l_g1.py"
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


def _load_g1_module():
    spec = importlib.util.spec_from_file_location("h4l_g1_test_module", G1_SCRIPT)
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
    assert "--run-name" in completed.stdout
    assert "--run-root" in completed.stdout
    assert "--no-progress" in completed.stdout
    assert "--protocol" in completed.stdout
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


def test_prepare_plan_stops_after_audit_and_prepare(
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
    for expected in ("src.cli.research audit", "src.cli.research prepare", "h4l_g1.py"):
        assert expected in output
    assert "src.cli.research train" not in output
    assert "src.cli.research calibrate" not in output
    assert "src.cli.research templates" not in output
    assert "h4l_run.py" not in output
    assert not run_root.exists()


def test_prepare_metrics_output_is_opt_in(tmp_path: Path) -> None:
    receipt, _ = _dataset_receipt(tmp_path)
    default_root = _new_run_root("pytest-prepare-metrics-default")
    verbose_root = _new_run_root("pytest-prepare-metrics-enabled")

    default = _run(
        PREPARE_SCRIPT,
        "--dataset-receipt", str(receipt),
        "--run-root", str(default_root),
        "--plan-only",
    )
    enabled = _run(
        PREPARE_SCRIPT,
        "--dataset-receipt", str(receipt),
        "--run-root", str(verbose_root),
        "--show-prepare-metrics",
        "--plan-only",
    )

    assert default.returncode == 0, default.stderr
    assert "--show-prepare-metrics" not in default.stdout
    assert enabled.returncode == 0, enabled.stderr
    assert enabled.stdout.count("--show-prepare-metrics") == 1
    assert not default_root.exists()
    assert not verbose_root.exists()


def test_shared_run_name_derives_prepare_g1_and_batch_paths(tmp_path: Path) -> None:
    receipt, _ = _dataset_receipt(tmp_path)
    run_name = f"pytest-shared-{uuid.uuid4().hex}"
    run_root = PROJECT_ROOT / "runs" / f"h4l-feature-combinations-prerequisites-{run_name}"

    prepare = _run(
        PREPARE_SCRIPT,
        "--dataset-receipt", str(receipt),
        "--run-name", run_name,
        "--plan-only",
    )
    assert prepare.returncode == 0, prepare.stderr
    assert str(run_root / "prepare") in prepare.stdout
    assert f"--run-name {run_name}" in prepare.stdout

    g1 = _run(G1_SCRIPT, "--run-name", run_name, "--plan-only")
    assert g1.returncode == 0, g1.stderr
    assert g1.stdout.count(f"--input-run {run_root / 'prepare'}") == 9
    assert str(run_root / "inputs" / "t1-validation.json") in g1.stdout
    assert str(run_root / "g1" / "templates") in g1.stdout
    assert f"--run-name {run_name}" in g1.stdout

    batch = _run(RUN_SCRIPT, "--run-name", run_name, "--plan-only")
    assert batch.returncode == 0, batch.stderr
    assert str(run_root / "prepare") in batch.stdout
    assert str(run_root / "g1" / "templates") in batch.stdout
    assert str(run_root / "inputs" / "t1-validation.json") in batch.stdout
    assert str(run_root / "batch" / "all-seeds" / "seed42") in batch.stdout
    assert str(run_root / "batch" / "all-seeds" / "seed46") in batch.stdout
    assert not run_root.exists()


@pytest.mark.parametrize("script", [PREPARE_SCRIPT, G1_SCRIPT, RUN_SCRIPT])
def test_shared_run_name_rejects_path_traversal(
    script: Path, tmp_path: Path,
) -> None:
    arguments = ["--run-name", "../escape", "--plan-only"]
    if script == PREPARE_SCRIPT:
        receipt, _ = _dataset_receipt(tmp_path)
        arguments[:0] = ["--dataset-receipt", str(receipt)]

    completed = _run(script, *arguments)

    assert completed.returncode == 2
    assert "run name must contain" in completed.stderr


@pytest.mark.parametrize(
    ("script", "explicit_option", "error_text"),
    [
        (PREPARE_SCRIPT, "--run-root", "not allowed with argument"),
        (G1_SCRIPT, "--output-root", "cannot be combined"),
        (RUN_SCRIPT, "--output-root", "cannot be combined"),
    ],
)
def test_run_name_refuses_ambiguous_explicit_paths(
    script: Path, explicit_option: str, error_text: str,
) -> None:
    completed = _run(
        script,
        "--run-name", "001",
        explicit_option, "runs/other",
        "--plan-only",
    )

    assert completed.returncode == 2
    assert error_text in completed.stderr


def test_prepare_fixed_workload_diagnosis_does_not_offer_g1(tmp_path: Path) -> None:
    receipt, _ = _dataset_receipt(tmp_path)
    run_root = _new_run_root("pytest-prepare-diagnostic-plan")

    completed = _run(
        PREPARE_SCRIPT,
        "--dataset-receipt", str(receipt),
        "--run-root", str(run_root),
        "--diagnostic-entries-per-file", "1000",
        "--plan-only",
    )

    assert completed.returncode == 0, completed.stderr
    assert "--diagnostic-entries-per-file 1000" in completed.stdout
    assert "Next G1 command:" not in completed.stdout
    assert "Fixed-workload diagnosis" in completed.stdout
    assert not run_root.exists()


def test_prepare_run_name_rejects_diagnostic_mode() -> None:
    completed = _run(
        PREPARE_SCRIPT,
        "--run-name", "001",
        "--diagnostic-entries-per-file", "1000",
        "--plan-only",
    )

    assert completed.returncode == 2
    assert "use --run-root for diagnostics" in completed.stderr


def test_prepare_writes_automatic_inputs_before_running_prerequisites(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prepare = _load_prepare_module()
    receipt, _ = _dataset_receipt(tmp_path)
    monkeypatch.setattr(prepare, "RUNS_ROOT", tmp_path.resolve())
    run_root = tmp_path / "run"

    invoked: list[list[str]] = []

    def fake_invoke(arguments: list[str], *, plan_only: bool) -> None:
        assert plan_only is False
        invoked.append(arguments)

    monkeypatch.setattr(prepare, "_invoke", fake_invoke)
    prepare._run(
        argparse.Namespace(
            dataset_receipt=receipt,
            run_root=run_root,
            protocol=None,
            plan_only=False,
            no_progress=False,
        )
    )

    inputs = run_root / "inputs"
    assert json.loads((inputs / "p0-validation.json").read_text(encoding="utf-8"))["status"] == "validated"
    assert json.loads((inputs / "t1-validation.json").read_text(encoding="utf-8"))["status"] == "validated"
    assert (inputs / "h4l-root-input-v1-manifest.json").is_file()
    assert [arguments[0] for arguments in invoked] == ["audit", "prepare"]
    assert "--show-prepare-progress" not in invoked[0]
    assert "--show-prepare-progress" in invoked[1]
    assert "H4l prepare" not in capsys.readouterr().err


def test_g1_plan_reuses_prepared_run_without_preparing_root_again() -> None:
    prepared = _new_run_root("pytest-g1-prepared")
    t1_validation = prepared.parent / f"{prepared.name}-t1.json"
    output_root = _new_run_root("pytest-g1-output")

    completed = _run(
        G1_SCRIPT,
        "--prepared-run", str(prepared),
        "--t1-validation", str(t1_validation),
        "--output-root", str(output_root),
        "--plan-only",
    )

    assert completed.returncode == 0, completed.stderr
    output = completed.stdout
    assert output.count("src.cli.research train") == 3
    assert output.count("src.cli.research calibrate") == 5
    assert output.count("src.cli.research templates") == 1
    assert "src.cli.research prepare" not in output
    assert output.count(f"--input-run {prepared}") == 9
    assert "h4l_run.py" in output
    assert not output_root.exists()


def test_exploratory_protocol_propagates_prepare_to_g1_to_batch(tmp_path: Path) -> None:
    receipt, _ = _dataset_receipt(tmp_path)
    protocol = PROJECT_ROOT / "config" / "research_protocol_exploratory_all_mc_v1.json"
    run_root = _new_run_root("pytest-exploratory-plan")
    prepare = _run(PREPARE_SCRIPT, "--dataset-receipt", str(receipt),
                   "--run-root", str(run_root), "--protocol", str(protocol), "--plan-only")
    assert prepare.returncode == 0, prepare.stderr
    assert prepare.stdout.count(f"--protocol {protocol}") == 3

    g1 = _run(G1_SCRIPT, "--prepared-run", str(run_root / "prepare"),
              "--t1-validation", str(run_root / "inputs" / "t1-validation.json"),
              "--output-root", str(run_root / "g1"), "--protocol", str(protocol), "--plan-only")
    assert g1.returncode == 0, g1.stderr
    assert g1.stdout.count(f"--protocol {protocol}") == 10

    batch = _run(RUN_SCRIPT, "--seed", "42", "--prepared-run", str(run_root / "prepare"),
                 "--gate-run", str(run_root / "g1" / "templates"),
                 "--t1-validation", str(run_root / "inputs" / "t1-validation.json"),
                 "--output-root", str(run_root / "batch" / "seed42"),
                 "--protocol", str(protocol), "--plan-only")
    assert batch.returncode == 0, batch.stderr
    assert batch.stdout.count(f"--protocol {protocol}") == 41


def test_run_plan_covers_all_combinations_without_creating_run() -> None:
    output_root = _new_run_root("pytest-run-plan")

    completed = _run(
        RUN_SCRIPT,
        "--output-root", str(output_root),
        "--plan-only",
    )

    assert completed.returncode == 0, completed.stderr
    output = completed.stdout
    assert output.count("src.cli.research train") == 90
    assert output.count("src.cli.research calibrate") == 100
    assert "--groups ABCD" in output
    assert output.count("src.cli.research templates") == 1
    assert output.count("src.cli.research infer") == 1
    assert output.count("src.cli.research report") == 1
    assert "seed42" in output and "seed46" in output
    assert not output_root.exists()


def test_run_explicit_seed_keeps_single_seed_diagnostic_plan() -> None:
    output_root = _new_run_root("pytest-run-single-plan")
    completed = _run(RUN_SCRIPT, "--seed", "42", "--output-root", str(output_root),
                     "--plan-only")
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.count("src.cli.research train") == 18
    assert completed.stdout.count("src.cli.research calibrate") == 20
    assert "seed43" not in completed.stdout
    assert not output_root.exists()


def test_run_refuses_existing_output_without_invoking_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _load_run_module()
    prepared = tmp_path / "prepared"; prepared.mkdir()
    gate = tmp_path / "gate"; gate.mkdir()
    t1_validation = tmp_path / "t1-validation.json"; t1_validation.write_text("{}")
    output_root = tmp_path / "existing"; output_root.mkdir()
    monkeypatch.setattr(run, "RUNS_ROOT", tmp_path.resolve())
    monkeypatch.setattr(run, "_validate_t1", lambda *_args: None)
    monkeypatch.setattr(run, "_invoke", lambda *_args, **_kwargs: pytest.fail("stage invoked"))
    with pytest.raises(run.WorkflowError, match="cannot be reused") as failure:
        run._run(argparse.Namespace(seed=None,config=run.DEFAULT_CONFIG,protocol=None,
            prepared_run=prepared,gate_run=gate,t1_validation=t1_validation,
            output_root=output_root,plan_only=False,no_progress=True))
    assert failure.value.exit_code == 4


def test_conclusion_output_contains_combination_shapley_and_primary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    run = _load_run_module()
    per_seed = [{"seed":seed,"width68":1.0,"relative_improvement_vs_empty":.1}
                for seed in range(42,47)]
    contributions = [{"seed":seed,"contribution":.01} for seed in range(42,47)]
    report = {
        "feature_combination_comparisons": [],
        "feature_combination_summary": {
            "status":"valid","seeds":list(range(42,47)),
            "combinations":[{"subset":"AB","per_seed":per_seed,"median_width68":1.0,
                             "median_relative_improvement_vs_empty":.1}],
            "best_combination":{"subset":"AB","median_width68":1.0,
                                "median_relative_improvement_vs_empty":.1},
            "shapley":{"groups":{group:{"per_seed":contributions,"median_contribution":.01,
                "min_contribution":.0,"max_contribution":.02} for group in "ABCD"},
                "interactions":[{"pair":"AB","conditioning_subset":"",
                    "median_second_difference":.03}]},
        },
        "primary_comparison":{"status":"valid","paired_seeds":[{"seed":42,
            "M4_width68":2.,"M5_width68":1.8,"relative_improvement":.1}],
            "median_relative_improvement":.1},
        "primary_comparison_cohort_id":"cohort",
    }
    run._print_conclusions(report,tmp_path/"report.md",complete=True)
    output=capsys.readouterr().out
    for expected in ("Best combination: AB","Group-level Shapley contributions",
                     "Strongest positive interaction","Primary M5/M4 comparison: valid",
                     "five-seed median improvement=10.0000%"):
        assert expected in output


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
    monkeypatch.setattr(run, "_print_conclusions", lambda *_args, **_kwargs: None)
    run._run(
        argparse.Namespace(
            seed=42,
            config=run.DEFAULT_CONFIG,
            protocol=None,
            prepared_run=prepared,
            gate_run=gate,
            t1_validation=t1_validation,
            output_root=output_root,
            plan_only=False,
            no_progress=False,
        )
    )

    progress_output = capsys.readouterr().err
    assert "H4l diagnostic seed 42" in progress_output
    assert "41/41" in progress_output


def test_run_cli_supports_disabling_progress() -> None:
    completed = _run(RUN_SCRIPT, "--help")

    assert completed.returncode == 0
    assert "--no-progress" in completed.stdout


@pytest.mark.parametrize("script", [PREPARE_SCRIPT, G1_SCRIPT, RUN_SCRIPT])
def test_h4l_scripts_expose_clean(script: Path) -> None:
    completed = _run(script, "--help")
    assert completed.returncode == 0
    assert "--clean" in completed.stdout


def test_prepare_clean_removes_only_prepare_owned_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_prepare_module()
    run_root = tmp_path / "workflow"
    for name in ("inputs", "audit", "prepare", "g1", "batch"):
        (run_root / name).mkdir(parents=True)
        (run_root / name / "owned.txt").write_text(name)
    monkeypatch.setattr(module, "RUNS_ROOT", tmp_path.resolve())
    module._run(argparse.Namespace(run_name=None,run_root=run_root,clean=True,
        plan_only=False,diagnostic_entries_per_file=None))
    assert all(not (run_root/name).exists() for name in ("inputs","audit","prepare"))
    assert (run_root/"g1"/"owned.txt").is_file()
    assert (run_root/"batch"/"owned.txt").is_file()


def test_g1_and_run_clean_remove_only_selected_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    g1 = _load_g1_module(); run = _load_run_module()
    workflow = tmp_path / "workflow"
    g1_root = workflow / "g1"; g1_root.mkdir(parents=True)
    batch_root = workflow / "batch" / "all-seeds"; batch_root.mkdir(parents=True)
    preserved = workflow / "prepare"; preserved.mkdir(parents=True)
    monkeypatch.setattr(g1, "RUNS_ROOT", tmp_path.resolve())
    g1._run(argparse.Namespace(run_name=None,prepared_run=None,t1_validation=None,
        output_root=g1_root,clean=True,plan_only=False))
    assert not g1_root.exists() and preserved.exists() and batch_root.exists()
    monkeypatch.setattr(run, "RUNS_ROOT", tmp_path.resolve())
    run._run(argparse.Namespace(seed=None,config=run.DEFAULT_CONFIG,protocol=None,
        run_name=None,prepared_run=None,gate_run=None,t1_validation=None,
        output_root=batch_root,clean=True,plan_only=False,no_progress=True))
    assert not batch_root.exists() and preserved.exists()


def test_run_name_clean_removes_the_default_complete_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_run_module()
    workflow = tmp_path / "h4l-feature-combinations-prerequisites-001"
    complete_batch = workflow / "batch" / "all-seeds"
    single_seed_batch = workflow / "batch" / "seed42"
    complete_batch.mkdir(parents=True)
    single_seed_batch.mkdir()
    (complete_batch / "result.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "RUNS_ROOT", tmp_path.resolve())

    module._run(argparse.Namespace(
        seed=None,
        run_name="001",
        output_root=None,
        prepared_run=None,
        gate_run=None,
        t1_validation=None,
        config=tmp_path / "does-not-exist.json",
        clean=True,
        plan_only=False,
    ))

    assert not complete_batch.exists()
    assert single_seed_batch.exists()


def test_clean_rejects_target_outside_runs_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_g1_module()
    runs_root = tmp_path / "runs"; runs_root.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    monkeypatch.setattr(module, "RUNS_ROOT", runs_root.resolve())
    with pytest.raises(module.WorkflowError, match="must be below") as failure:
        module._run(argparse.Namespace(run_name=None,prepared_run=None,t1_validation=None,
            output_root=outside,clean=True,plan_only=False))
    assert failure.value.exit_code == 4 and outside.exists()


def test_clean_rejects_a_symbolic_link_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_g1_module()
    runs_root = tmp_path / "runs"
    outside = tmp_path / "outside"
    runs_root.mkdir()
    outside.mkdir()
    link = runs_root / "linked-g1"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"Directory symlinks are unavailable: {error}")
    monkeypatch.setattr(module, "RUNS_ROOT", runs_root.resolve())

    with pytest.raises(module.WorkflowError, match="symbolic link") as failure:
        module._run(argparse.Namespace(
            run_name=None,
            prepared_run=None,
            t1_validation=None,
            output_root=link,
            clean=True,
            plan_only=False,
        ))

    assert failure.value.exit_code == 4
    assert link.is_symlink()
    assert outside.exists()


@pytest.mark.parametrize("load_module", [_load_g1_module, _load_run_module])
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


def test_prepare_invoke_has_no_dot_progress(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_prepare_module()

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

    assert capsys.readouterr().err == ""


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
