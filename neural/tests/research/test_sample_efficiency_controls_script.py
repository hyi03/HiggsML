from __future__ import annotations

import json

import pytest

from src.cli.sample_efficiency_controls import _config, build_parser
from src.research.errors import ResearchError


def test_cli_modes_are_required_and_mutually_exclusive():
    parser = build_parser()
    with pytest.raises(SystemExit) as missing:
        parser.parse_args(["--dataset", "atlas2020_4lep", "--config", "x.json"])
    assert missing.value.code == 2
    with pytest.raises(SystemExit) as both:
        parser.parse_args(["--dataset", "atlas2020_4lep", "--config", "x.json",
                           "--controls-only", "--confirm"])
    assert both.value.code == 2


def test_exact_controls_config_forbids_confirmation_access(tmp_path):
    value = {"schema_version": "h4l-sample-efficiency-controls-config-v1",
        "mode": "controls-only", "dataset": "atlas2020_4lep", "protocol": "p",
        "sample_efficiency_protocol": "o", "prepared_run": "prepared",
        "compact_freeze_run": "freeze", "training_subsets_run": "subsets",
        "gate_run": "gate", "t1_validation": "t1", "batch_run": "batch",
        "report_run": "report", "exclusion_identity_sets": [], "confirmation_input": None,
        "output_root": "runs", "output_name": "controls", "repeat": False}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    assert _config(path)["mode"] == "controls-only"
    value["confirmation_input"] = "poison.pkg"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ResearchError, match="cannot access confirmation"):
        _config(path)
