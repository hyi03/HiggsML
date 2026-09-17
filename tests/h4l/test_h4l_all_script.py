from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "h4l_all.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("h4l_all_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_default_run_name_executes_the_complete_resumable_h4l_workflow(
    tmp_path: Path, monkeypatch,
) -> None:
    workflow = _load_module()
    monkeypatch.setattr(workflow, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(workflow, "_available_memory_bytes", lambda: 12 * 1024**3)
    monkeypatch.setattr(workflow, "_reviewer_name", lambda: "Test Researcher")
    commands: list[list[str]] = []
    monkeypatch.setattr(workflow, "_invoke", lambda command: commands.append(command))

    workflow._run(workflow._parser().parse_args([]))

    assert [Path(command[1]).name for command in commands] == [
        "h4l_prepare.py",
        "h4l_check.py",
        "h4l_run.py",
        "h4l_off_run.py",
        "h4l_off_self_review.py",
        "h4l_off_run.py",
    ]
    assert commands[0][2:] == []
    assert commands[1][2:] == ["--run-name", "default"]
    assert commands[2][2:] == ["--run-name", "default"]
    assert commands[3][2:] == [
        "--source-run-name", "default", "--run-name", "default",
        "--stage-b", "--workers", "2", "--worker-threads", "1",
    ]
    assert commands[4][2:] == [
        "--run-name", "default", "--reviewer", "Test Researcher",
    ]
    assert commands[5][2:] == [
        "--source-run-name", "default", "--run-name", "default",
        "--evaluation", "--workers", "2", "--worker-threads", "1",
    ]


def test_explicit_run_name_reuses_an_existing_access_review(
    tmp_path: Path, monkeypatch,
) -> None:
    workflow = _load_module()
    monkeypatch.setattr(workflow, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(workflow, "_available_memory_bytes", lambda: 48 * 1024**3)
    review = (
        tmp_path / "h4l-off-study-001" / "access-review"
        / "validated-off-assessment-access.json"
    )
    review.parent.mkdir(parents=True)
    review.write_text("{}", encoding="utf-8")
    commands: list[list[str]] = []
    monkeypatch.setattr(workflow, "_invoke", lambda command: commands.append(command))

    workflow._run(workflow._parser().parse_args(["--run-name", "study-001"]))

    assert len(commands) == 5
    assert all(Path(command[1]).name != "h4l_off_self_review.py" for command in commands)
    assert commands[-1][2:] == [
        "--source-run-name", "study-001", "--run-name", "study-001",
        "--evaluation", "--workers", "4", "--worker-threads", "1",
    ]


def test_worker_count_is_bounded_by_available_memory(monkeypatch) -> None:
    workflow = _load_module()
    for available, expected in (
        (None, 1),
        (4 * 1024**3, 1),
        (12 * 1024**3, 2),
        (24 * 1024**3, 4),
        (96 * 1024**3, 4),
    ):
        monkeypatch.setattr(workflow, "_available_memory_bytes", lambda value=available: value)
        assert workflow._off_workers() == expected
