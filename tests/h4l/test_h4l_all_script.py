from __future__ import annotations

import importlib.util
from pathlib import Path
import json
import sys
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "h4l_all.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("h4l_all_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _isolated_command_contract(workflow, monkeypatch):
    # These tests exercise child argument routing. Real metadata and completion
    # validation have separate disk-backed tests in test_h4l_readiness.py.
    monkeypatch.setattr(workflow, 'preflight', lambda *args: {
        'access_blockers': [], 'prepared_artifact_id': 'fixture',
    })
    monkeypatch.setattr(workflow, 'verify_completion', lambda *args: {'execution_status': 'complete'})


@pytest.mark.parametrize(('flags', 'method'), [
    ([], 'joint-support-v1'),
    (['--threshold-method', 'joint-support-v1'], 'joint-support-v1'),
    (['--threshold-method', 'median-v1'], 'median-v1'),
])
def test_threshold_method_reaches_stage_b_and_evaluation(
    tmp_path: Path, monkeypatch, flags, method,
) -> None:
    workflow = _load_module()
    _isolated_command_contract(workflow, monkeypatch)
    monkeypatch.setattr(workflow, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(workflow, "_physical_memory_bytes", lambda: 16 * 1024**3)
    plan = tmp_path / "h4l-off-default" / "evaluation-plan" / "evaluation-plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text("{}", encoding="utf-8")
    commands: list[list[str]] = []
    def invoke(command):
        commands.append(command)
        if command[1:5] == ["-m", "higgsml.cli", "attribution", "access-review"]:
            access = (
                tmp_path / "h4l-off-default" / "access-review"
                / "validated-off-assessment-access.json"
            )
            access.parent.mkdir(parents=True)
            access.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(workflow, "_invoke", invoke)

    workflow._run(workflow._parser().parse_args(flags))

    assert [Path(command[1]).name for command in commands] == [
        "h4l_prepare.py",
        "h4l_check.py",
        "h4l_run.py",
        "h4l_off_run.py",
        "h4l_off_self_review.py",
        "-m",
        "h4l_off_run.py",
    ]
    assert commands[0][2:] == ["--run-name", "default"]
    assert commands[1][2:] == ["--run-name", "default"]
    assert commands[2][2:] == ["--run-name", "default"]
    assert commands[3][2:] == [
        "--source-run-name", "default", "--run-name", "default",
        "--stage-b", "--threshold-method", method,
        "--continue", "--workers", "2", "--worker-threads", "1",
    ]
    assert commands[4][2:] == ["--run-name", "default"]
    assert commands[5][1:4] == ["-m", "higgsml.cli", "attribution"]
    assert commands[5][4] == "access-review"
    assert commands[6][2:] == [
        "--source-run-name", "default", "--run-name", "default",
        "--threshold-method", method, "--evaluation", "--access-review",
        str(tmp_path / "h4l-off-default" / "access-review" / "validated-off-assessment-access.json"),
        "--workers", "2", "--worker-threads", "1",
    ]


def test_explicit_run_name_reuses_an_existing_access_review(
    tmp_path: Path, monkeypatch,
) -> None:
    workflow = _load_module()
    _isolated_command_contract(workflow, monkeypatch)
    monkeypatch.setattr(workflow, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(workflow, "_physical_memory_bytes", lambda: 48 * 1024**3)
    review = (
        tmp_path / "h4l-off-study-001" / "access-review"
        / "validated-off-assessment-access.json"
    )
    review.parent.mkdir(parents=True)
    review.write_text(json.dumps({
        "schema_version": "h4l-off-assessment-access-v3",
    }), encoding="utf-8")
    plan = tmp_path / "h4l-off-study-001" / "evaluation-plan" / "evaluation-plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text("{}", encoding="utf-8")
    commands: list[list[str]] = []
    monkeypatch.setattr(workflow, "_invoke", lambda command: commands.append(command))

    workflow._run(workflow._parser().parse_args([
        "--run-name", "study-001", "--access-review", str(review),
    ]))

    assert len(commands) == 5
    assert commands[-1][2:] == [
        "--source-run-name", "study-001", "--run-name", "study-001",
        "--threshold-method", "joint-support-v1", "--evaluation", "--access-review", str(review),
        "--workers", "4", "--worker-threads", "1",
    ]


def test_explicit_source_review_is_adapted_before_evaluation(
    tmp_path: Path, monkeypatch,
) -> None:
    workflow = _load_module()
    _isolated_command_contract(workflow, monkeypatch)
    monkeypatch.setattr(workflow, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(workflow, "_physical_memory_bytes", lambda: 16 * 1024**3)
    source_review = tmp_path / "independent-review.json"
    source_review.write_text(json.dumps({
        "schema_version": "h4l-off-assessment-access-v1",
    }), encoding="utf-8")
    plan = tmp_path / "h4l-off-study-002" / "evaluation-plan" / "evaluation-plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text("{}", encoding="utf-8")
    commands: list[list[str]] = []
    def invoke(command):
        commands.append(command)
        if command[1:5] == ["-m", "higgsml.cli", "attribution", "access-review"]:
            access = (
                tmp_path / "h4l-off-study-002" / "access-review"
                / "validated-off-assessment-access.json"
            )
            access.parent.mkdir(parents=True)
            access.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(workflow, "_invoke", invoke)

    workflow._run(workflow._parser().parse_args([
        "--run-name", "study-002", "--access-review", str(source_review),
    ]))

    adapter = commands[-2]
    assert adapter[1:5] == ["-m", "higgsml.cli", "attribution", "access-review"]
    assert adapter[adapter.index("--access-review") + 1] == str(source_review.resolve())
    expected = (
        tmp_path / "h4l-off-study-002" / "access-review"
        / "validated-off-assessment-access.json"
    )
    assert commands[-1][commands[-1].index("--access-review") + 1] == str(expected)


def test_missing_explicit_access_review_fails_before_work_starts(
    tmp_path: Path, monkeypatch,
) -> None:
    workflow = _load_module()
    monkeypatch.setattr(workflow, "RUNS_ROOT", tmp_path)
    commands: list[list[str]] = []
    monkeypatch.setattr(workflow, "_invoke", lambda command: commands.append(command))

    with pytest.raises(workflow.WorkflowError, match="Access review not found"):
        workflow._run(workflow._parser().parse_args([
            "--run-name", "study-003",
            "--access-review", str(tmp_path / "missing.json"),
        ]))

    assert commands == []


def test_blocked_access_adapter_does_not_start_evaluation(
    tmp_path: Path, monkeypatch, capsys,
) -> None:
    workflow = _load_module()
    _isolated_command_contract(workflow, monkeypatch)
    monkeypatch.setattr(workflow, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(workflow, "_physical_memory_bytes", lambda: 16 * 1024**3)
    plan = tmp_path / "h4l-off-blocked" / "evaluation-plan" / "evaluation-plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text("{}", encoding="utf-8")
    source = (
        tmp_path / "h4l-off-blocked" / "source-access-review"
        / "validated-off-assessment-access.json"
    )
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({
        "schema_version": "h4l-off-assessment-access-v1",
    }), encoding="utf-8")
    commands: list[list[str]] = []
    monkeypatch.setattr(workflow, "_invoke", lambda command: commands.append(command))

    with pytest.raises(workflow.WorkflowError, match='Assessment access remains blocked') as error:
        workflow._run(workflow._parser().parse_args(["--run-name", "blocked"]))
    assert error.value.exit_code == 5

    assert commands[-1][1:5] == ["-m", "higgsml.cli", "attribution", "access-review"]
    assert not any(Path(command[1]).name == "h4l_off_run.py" and "--evaluation" in command
                   for command in commands)


def test_version_selector_is_removed() -> None:
    workflow = _load_module()
    with pytest.raises(SystemExit):
        workflow._parser().parse_args(["--evaluation-version", "v3"])


def test_worker_count_is_bounded_by_physical_memory(monkeypatch) -> None:
    workflow = _load_module()
    for available, expected in (
        (None, 1),
        (-1, 1),
        (0, 1),
        (7 * 1024**3 - 1, 1),
        (7 * 1024**3, 1),
        (12 * 1024**3 - 1, 1),
        (12 * 1024**3, 2),
        (16 * 1024**3, 2),
        (17 * 1024**3, 3),
        (22 * 1024**3, 4),
        (96 * 1024**3, 4),
    ):
        monkeypatch.setattr(workflow, "_physical_memory_bytes", lambda value=available: value)
        assert workflow._off_workers() == expected
