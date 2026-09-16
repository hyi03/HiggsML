from pathlib import Path
import subprocess
import sys
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "h4l_off_run.py"


def invoke(*arguments):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments], cwd=PROJECT_ROOT,
        text=True, capture_output=True, check=False,
    )


def test_plan_prints_one_command_workflow_without_creating_output():
    name = f"pytest-{uuid.uuid4().hex}"
    output = PROJECT_ROOT / "runs" / f"h4l-off-{name}"
    completed = invoke("--source-run-name", "02", "--run-name", name, "--plan")
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.count("higgsml.cli attribution") == 5
    assert "h4l_evaluate.py" in completed.stdout
    assert "Execution requires --access-review" in completed.stdout
    assert not output.exists()


def test_stage_b_plan_does_not_require_access_review():
    completed = invoke(
        "--source-run-name", "T2", "--run-name", "paper-001",
        "--stage-b", "--plan",
    )
    assert completed.returncode == 0, completed.stderr
    assert "h4l_evaluate.py" not in completed.stdout
    assert "runs" in completed.stdout and "h4l-off-paper-001" in completed.stdout


def test_force_is_forwarded_to_each_debug_stage():
    completed = invoke(
        "--source-run-name", "T2", "--run-name", "debug-001",
        "--stage-b", "--force", "--plan",
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.count("--force") == 5


def test_full_execution_requires_access_review():
    completed = invoke("--source-run-name", "02", "--run-name", "paper-001")
    assert completed.returncode == 2
    assert "Full evaluation requires --access-review" in completed.stderr


def test_evaluation_plan_reuses_stage_b_paths():
    completed = invoke(
        "--source-run-name", "02", "--run-name", "paper-001",
        "--evaluation", "--plan",
    )
    assert completed.returncode == 0, completed.stderr
    assert "higgsml.cli attribution" not in completed.stdout
    assert completed.stdout.count("h4l_evaluate.py") == 1
    assert "report-B" in completed.stdout and "evaluation-plan.json" in completed.stdout
    assert "access-review" in completed.stdout
    assert "validated-off-assessment-access.json" in completed.stdout


def test_no_progress_is_supported_and_forwarded_to_evaluator():
    help_result = invoke("--help")
    assert help_result.returncode == 0
    assert "--no-progress" in help_result.stdout
    completed = invoke(
        "--source-run-name", "02", "--run-name", "paper-001",
        "--evaluation", "--no-progress", "--plan",
    )
    assert completed.returncode == 0, completed.stderr
    assert "h4l_evaluate.py" in completed.stdout
    assert "--no-progress" in completed.stdout


def test_workers_are_validated_and_forwarded_to_evaluator():
    completed = invoke(
        "--source-run-name", "02", "--run-name", "paper-001",
        "--evaluation", "--workers", "2", "--worker-threads", "1", "--plan",
    )
    assert completed.returncode == 0, completed.stderr
    evaluator = next(line for line in completed.stdout.splitlines() if "h4l_evaluate.py" in line)
    assert "--workers 2" in evaluator
    assert "--worker-threads 1" in evaluator

    invalid = invoke(
        "--source-run-name", "02", "--run-name", "paper-001",
        "--evaluation", "--workers", "0", "--plan",
    )
    assert invalid.returncode == 2
    assert "--workers must be positive" in invalid.stderr


def test_run_names_reject_path_traversal():
    completed = invoke(
        "--source-run-name", "../escape", "--run-name", "paper-001", "--plan",
    )
    assert completed.returncode == 2
    assert "run name must contain" in completed.stderr


def test_off_wrapper_exposes_resumable_execution():
    completed = invoke("--help")

    assert completed.returncode == 0
    assert "--continue" in completed.stdout


def test_off_wrapper_forwards_continue_to_evaluation():
    completed = invoke(
        "--source-run-name", "02", "--run-name", "paper-001",
        "--evaluation", "--continue", "--plan",
    )

    assert completed.returncode == 0, completed.stderr
    evaluator = next(line for line in completed.stdout.splitlines() if "h4l_evaluate.py" in line)
    assert "--continue" in evaluator
