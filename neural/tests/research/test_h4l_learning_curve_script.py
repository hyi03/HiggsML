import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.cli.sample_efficiency import build_parser, clean_unstarted_batch
from src.research.artifacts import read_json
from src.research.errors import ResearchError


def test_parser_exposes_only_registered_batch_surface():
    parser = build_parser()
    names = {action.dest for action in parser._actions}
    assert names == {"help", "dataset", "config", "protocol", "sample_efficiency_protocol",
                     "prepared_run", "compact_freeze_run", "training_subsets_run", "gate_run",
                     "t1_validation", "output_root", "resources", "plan_only", "clean",
                     "no_progress"}


def test_clean_only_removes_owned_unstarted_placeholder(tmp_path):
    root = tmp_path / "runs"
    target = root / "batch"
    staging = target / "staging"
    staging.mkdir(parents=True)
    marker = {"schema_version": "h4l-sample-efficiency-owner-v1",
              "execution_plan_id": "a" * 64, "target": str(target.resolve())}
    (target / ".sample-efficiency-owner.json").write_text(json.dumps(marker), encoding="utf-8")
    clean_unstarted_batch(target, allowed_root=root, execution_plan_id="a" * 64)
    assert not target.exists()

    occupied = root / "occupied"
    occupied.mkdir()
    (occupied / ".sample-efficiency-owner.json").write_text(json.dumps({**marker,
        "target": str(occupied.resolve())}), encoding="utf-8")
    (occupied / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ResearchError):
        clean_unstarted_batch(occupied, allowed_root=root, execution_plan_id="a" * 64)

    nested = root / "parent" / "child"
    nested.mkdir(parents=True)
    (nested / ".sample-efficiency-owner.json").write_text(json.dumps({**marker,
        "target": str(nested.resolve())}), encoding="utf-8")
    with pytest.raises(ResearchError):
        clean_unstarted_batch(nested, allowed_root=root, execution_plan_id="a" * 64)


def test_script_help_is_available_without_running_workflow():
    script = Path(__file__).resolve().parents[2] / "scripts" / "h4l_learning_curve.py"
    completed = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)
    assert completed.returncode == 0
    assert "--training-subsets-run" in completed.stdout and "--plan-only" in completed.stdout


def test_artifact_json_rejects_nested_duplicate_keys(tmp_path):
    payload = tmp_path / "duplicate.json"
    payload.write_text('{"outer":{"key":1,"key":2}}', encoding="utf-8")
    with pytest.raises(ResearchError):
        read_json(payload)
