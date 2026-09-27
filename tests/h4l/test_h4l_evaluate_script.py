import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import uuid

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "h4l_evaluate.py"


def invoke(plan):
    output = PROJECT_ROOT / "runs" / f"pytest-evaluate-plan-{uuid.uuid4().hex}"
    return subprocess.run([sys.executable, str(SCRIPT), "--plan", str(plan),
        "--prepared-run", "runs/missing-prepare", "--template-run", "runs/missing-template",
        "--freeze-run", "runs/missing-freeze", "--output-root", str(output), "--plan-only"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)


def test_malformed_missing_and_nonobject_plans_have_controlled_errors(tmp_path):
    path=tmp_path/'invalid.json'
    for content in (None,'{','[]'):
        if content is not None: path.write_text(content,encoding='utf-8')
        result=invoke(path)
        assert result.returncode==3 and 'Invalid evaluation plan' in result.stderr
        assert 'Traceback' not in result.stderr


def test_evaluator_supports_disabling_progress():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], cwd=PROJECT_ROOT,
        text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0
    assert "--no-progress" in completed.stdout
    assert "--evaluation-unit" in completed.stdout
    assert "--retry-failed" in completed.stdout


def test_attribution_cli_supports_disabling_internal_progress():
    completed = subprocess.run(
        [sys.executable, "-m", "higgsml.cli", "attribution", "--help"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0
    assert "--no-progress" in completed.stdout


def test_evaluator_and_attribution_cli_expose_process_workers():
    evaluator = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], cwd=PROJECT_ROOT,
        text=True, capture_output=True, check=False,
    )
    attribution = subprocess.run(
        [sys.executable, "-m", "higgsml.cli", "attribution", "--help"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert evaluator.returncode == attribution.returncode == 0
    assert "--workers" in evaluator.stdout and "--worker-threads" in evaluator.stdout
    assert "--workers" in attribution.stdout and "--worker-threads" in attribution.stdout


def test_version_selector_is_removed():
    for command in (
        [sys.executable, str(SCRIPT), "--help"],
        [sys.executable, "-m", "higgsml.cli", "attribution", "--help"],
    ):
        completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
        assert completed.returncode == 0
        assert "--evaluation-version" not in completed.stdout


def test_long_off_stage_refreshes_progress_while_child_is_running(monkeypatch):
    spec = importlib.util.spec_from_file_location("h4l_evaluate_progress_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    class Process:
        waits = 0
        def wait(self, timeout):
            self.waits += 1
            if self.waits < 3:
                raise subprocess.TimeoutExpired(cmd="stage", timeout=timeout)
            return 0

    class Progress:
        def __init__(self):
            self.label = None
            self.refreshes = 0
        def set_postfix_str(self, label, refresh):
            self.label = label
            self.refreshes += int(refresh)
        def refresh(self):
            self.refreshes += 1

    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_k: Process())
    progress = Progress()
    module._invoke_with_progress(["research"], label="assessment mu=1", progress=progress)
    assert progress.label == "assessment mu=1"
    assert progress.refreshes == 3


def test_assessment_access_is_validated_before_output_or_units(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("h4l_evaluate_preflight_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    from higgsml.errors import ResearchError
    from higgsml.inference import marginal_workflow

    monkeypatch.setattr(module, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(marginal_workflow, "validate_plan", lambda *_a: None)
    monkeypatch.setattr(marginal_workflow, "matrix", lambda: [
        {"stage": "assessment", "mu": 0, "training_seed": 42},
    ])
    monkeypatch.setattr(
        marginal_workflow, "validate_access",
        lambda *_a, **_k: (_ for _ in ()).throw(ResearchError("missing receipt")),
    )
    output = tmp_path / "evaluation"
    args = SimpleNamespace(
        force=False, reuse_stage=[], evaluation_unit=[], retry_failed=False,
        output_root=output, plan_only=False, registration_run=tmp_path / "register",
        result_run=tmp_path / "result", template_run=tmp_path / "nominal",
        freeze_run=tmp_path / "freeze", plan=tmp_path / "plan.json",
        access_review=tmp_path / "missing.json", workers=1, worker_threads=1,
        show_command=False, no_progress=True, continue_run=False,
    )

    with pytest.raises(module.EvaluationError, match="Invalid assessment access review: missing receipt"):
        module._run_default(args, {}, {})

    assert not output.exists()
