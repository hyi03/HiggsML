import subprocess
import sys
from pathlib import Path

import pytest

from src.cli.sample_efficiency_report import build_parser
from src.research.errors import ResearchError
from src.research.sample_efficiency import publish_sample_efficiency_report


def test_report_parser_has_no_scientific_overrides():
    names = {action.dest for action in build_parser()._actions}
    assert names == {"help", "dataset", "config", "protocol", "sample_efficiency_protocol",
        "prepared_run", "compact_freeze_run", "training_subsets_run", "gate_run",
        "t1_validation", "batch_run", "output_root", "output_name"}
    assert not names & {"seed", "replicates", "quality_target", "filter"}


def test_report_script_help():
    script = Path(__file__).resolve().parents[2] / "scripts" / "h4l_sample_efficiency_report.py"
    completed = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)
    assert completed.returncode == 0
    assert "--batch-run" in completed.stdout and "--output-name" in completed.stdout


def test_report_publisher_rejects_existing_target_before_upstream_reads(tmp_path):
    root = tmp_path / "runs"; root.mkdir()
    target = root / "report"; target.mkdir()
    with pytest.raises(ResearchError) as error:
        publish_sample_efficiency_report(target, allowed_root=root, batch_path="unreadable",
            prepared=None, freeze_run=None, subset_run=None, gate_run=None,
            t1_validation=None, base=None, overlay=None)
    assert error.value.status == "training_subset_binding_mismatch"
