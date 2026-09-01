import hashlib
import json
import sys

import pandas as pd
import pytest
import yaml

from scripts import prepare_demo
from src import provenance
from src.pipeline import PreparedSample
from src.weights import MCNormalization


def selection_mapping():
    return {
        "require_exactly_four_leptons": True,
        "allowed_lepton_types": [11, 13],
        "lepton_pt_thresholds_gev": [20.0, 15.0, 10.0, 7.0],
        "electron_max_abs_eta": 2.47,
        "muon_max_abs_eta": 2.7,
        "require_zero_charge": True,
        "min_all_sfos_mass_gev": 5.0,
        "z1_mass_window_gev": [50.0, 106.0],
        "z2_mass": {
            "min_mode": "fixed",
            "fixed_min_gev": 12.0,
            "max_gev": 115.0,
            "sliding": {
                "low_m4l_gev": 140.0,
                "high_m4l_gev": 190.0,
                "low_min_gev": 12.0,
                "high_min_gev": 50.0,
            },
        },
        "m4l_window_gev": [105.0, 160.0],
    }


def enhanced_selection_mapping():
    mapping = selection_mapping()
    mapping["lepton_quality"] = {
        "enabled": True,
        "require_event_trigger": True,
        "require_trigger_match": True,
        "require_tight_id": True,
        "track_isolation_max": 0.3,
        "calo_isolation_max": 0.3,
        "electron_d0sig_max": 5.0,
        "muon_d0sig_max": 3.0,
        "z0_sintheta_max_mm": 0.5,
    }
    return mapping


def write_test_config_and_inputs(tmp_path):
    input_paths = {}
    for name, content in (
        ("higgs", b"synthetic-higgs-root"),
        ("zz", b"synthetic-zz-root"),
        ("data", b"synthetic-data-root"),
    ):
        path = tmp_path / f"{name}.root"
        path.write_bytes(content)
        input_paths[name] = path
    config = {
        "random_seed": 42,
        "luminosity_pb": 10000.0,
        "tree_name": "analysis",
        "momentum_unit": "GeV",
        "entry_stop": 5000,
        "chunk_size_events": 50000,
        "samples": {
            "higgs": {
                "path": str(input_paths["higgs"]),
                "channel_numbers": [345060],
                "label": 1,
            },
            "zz": {
                "path": str(input_paths["zz"]),
                "channel_numbers": [700600],
                "label": 0,
            },
            "data": {
                "path": str(input_paths["data"]),
                "period": "data16_periodA",
            },
        },
        "selection": selection_mapping(),
    }
    config_path = tmp_path / "demo.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return config_path, input_paths


def write_per_sample_config_and_inputs(tmp_path):
    config_path, input_paths = write_test_config_and_inputs(tmp_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["input_profile"] = "release22"
    config["samples"]["higgs"]["input_profile"] = "release22"
    config["samples"]["zz"].update(
        {
            "channel_numbers": [363490],
            "input_profile": "open_data_2020",
            "normalization": {
                "source": "official_metadata",
                "xsec_pb": 1.2564,
                "k_factor": 1.0,
                "filter_efficiency": 1.0,
                "sum_of_weights": 7538705.808,
            },
        }
    )
    config["samples"]["data"]["input_profile"] = "release22"
    config["selection"] = enhanced_selection_mapping()
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return config_path, input_paths, config


def install_fake_prepare_sample(monkeypatch):
    calls = []

    def fake_prepare_sample(path, **kwargs):
        calls.append(kwargs)
        is_data = kwargs["is_data"]
        if is_data:
            frame = pd.DataFrame(
                [
                    {
                        "runNumber": 10,
                        "eventNumber": 20,
                        "label": -1,
                        "physical_weight": 1.0,
                        "train_weight": 1.0,
                        "split": "data",
                    }
                ]
            )
            normalization = None
        else:
            label = int(kwargs["label"])
            frame = pd.DataFrame(
                [
                    {
                        "eventNumber": 20,
                        "channelNumber": kwargs["expected_channels"][0],
                        "label": label,
                        "physical_weight": -0.5 if label == 1 else 2.0,
                        "train_weight": 1.0,
                        "split": "train",
                    }
                ]
            )
            normalization = MCNormalization(2.0, 1.0, 1.0, 100.0)
        return PreparedSample(
            frame=frame,
            cutflow={
                "sample_name": kwargs["sample_name"],
                "kind": "data" if is_data else "mc",
                "stages": {
                    "read": {"count": 2},
                    "selected": {"count": 1},
                },
            },
            normalization=normalization,
        )

    monkeypatch.setattr(prepare_demo, "prepare_sample", fake_prepare_sample)
    return calls


def test_prepare_script_wires_selection_and_writes_sample_cutflows(
    tmp_path, monkeypatch
):
    config_path, input_paths = write_test_config_and_inputs(tmp_path)
    calls = install_fake_prepare_sample(monkeypatch)
    monkeypatch.setattr(
        provenance, "discover_git_commit", lambda cwd: "unavailable"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_demo",
            "--config",
            str(config_path),
            "--output-dir",
            "artifacts",
        ],
    )

    prepare_demo.main()

    assert [call["sample_name"] for call in calls] == [
        "higgs_345060",
        "zz_700600",
        "data16_periodA",
    ]
    assert all(call["selection"].z2_min_mode == "fixed" for call in calls)
    assert [call["entry_stop"] for call in calls] == [5000, 5000, 5000]
    assert [call["chunk_size_events"] for call in calls] == [50_000] * 3
    assert (tmp_path / "data/processed/mc_events.csv.gz").exists()
    assert (tmp_path / "data/processed/data_events.csv.gz").exists()
    cutflow_payload = json.loads((tmp_path / "artifacts/cutflow.json").read_text())
    assert list(cutflow_payload["samples"]) == [
        "data16_periodA",
        "higgs_345060",
        "zz_700600",
    ]
    summary_payload = json.loads(
        (tmp_path / "artifacts/data_summary.json").read_text()
    )
    assert list(summary_payload["data"]) == ["data16_periodA"]
    assert list(summary_payload["mc"]) == ["higgs_345060", "zz_700600"]
    assert summary_payload["mc"]["higgs_345060"]["negative_weight_events"] == 1

    manifest_payload = json.loads(
        (tmp_path / "artifacts/run_manifest.json").read_text()
    )
    assert manifest_payload["config"]["sha256"] == hashlib.sha256(
        config_path.read_bytes()
    ).hexdigest()
    assert manifest_payload["config"]["snapshot_path"] is None
    assert list(manifest_payload["inputs"]) == [
        "data16_periodA",
        "higgs_345060",
        "zz_700600",
    ]
    expected_inputs = {
        "data16_periodA": input_paths["data"],
        "higgs_345060": input_paths["higgs"],
        "zz_700600": input_paths["zz"],
    }
    for name, path in expected_inputs.items():
        assert manifest_payload["inputs"][name]["sha256"] == hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    assert manifest_payload["processing"] == {
        "read_policy": {
            "mode": "head",
            "entry_stop": 5000,
            "chunk_size_events": 50_000,
        },
        "random_seed": 42,
        "tree_name": "analysis",
        "momentum_unit": "GeV",
        "selection": {"z2_min_mode": "fixed"},
    }
    assert manifest_payload["git"]["commit"] == "unavailable"
    assert not (tmp_path / "outputs").exists()


def test_prepare_script_resolves_profile_unit_and_normalization_per_sample(
    tmp_path, monkeypatch
):
    config_path, _, config = write_per_sample_config_and_inputs(tmp_path)
    calls = install_fake_prepare_sample(monkeypatch)
    monkeypatch.setattr(provenance, "discover_git_commit", lambda cwd: "unavailable")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prepare_demo", "--config", str(config_path), "--output-dir", "artifacts"],
    )

    prepare_demo.main()

    higgs, zz, data = calls
    assert (higgs["input_profile"], higgs["tree_name"], higgs["momentum_unit"]) == (
        "release22",
        "analysis",
        "GeV",
    )
    assert higgs["normalization_override"] is None
    assert (zz["input_profile"], zz["tree_name"], zz["momentum_unit"]) == (
        "open_data_2020",
        "mini",
        "MeV",
    )
    assert zz["normalization_override"] == MCNormalization(
        1.2564, 1.0, 1.0, 7538705.808
    )
    assert (data["input_profile"], data["tree_name"], data["momentum_unit"]) == (
        "release22",
        "analysis",
        "GeV",
    )
    assert data["normalization_override"] is None

    manifest = json.loads((tmp_path / "artifacts/run_manifest.json").read_text())
    assert manifest["processing"]["selection"] == config["selection"]
    assert manifest["processing"]["samples"] == {
        "higgs_345060": {
            "input_profile": "release22",
            "tree_name": "analysis",
            "momentum_unit": "GeV",
            "normalization_source": "root",
        },
        "zz_363490": {
            "input_profile": "open_data_2020",
            "tree_name": "mini",
            "momentum_unit": "MeV",
            "normalization_source": "official_metadata",
        },
        "data16_periodA": {
            "input_profile": "release22",
            "tree_name": "analysis",
            "momentum_unit": "GeV",
            "normalization_source": None,
        },
    }
    assert "1.3" not in json.dumps(manifest, sort_keys=True)


@pytest.mark.parametrize(
    ("sample_name", "normalization", "message"),
    [
        (
            "data",
            {
                "source": "official_metadata",
                "xsec_pb": 1.2564,
                "k_factor": 1.0,
                "filter_efficiency": 1.0,
                "sum_of_weights": 7538705.808,
            },
            "data samples may not specify external normalization",
        ),
        (
            "zz",
            {"source": "official_metadata", "xsec_pb": 1.2564},
            "normalization keys must be exactly",
        ),
        (
            "zz",
            {
                "source": "official_metadata",
                "xsec_pb": 1.2564,
                "k_factor": 1.0,
                "filter_efficiency": 1.0,
                "sum_of_weights": 7538705.808,
                "correction": 1.3,
            },
            "normalization keys must be exactly",
        ),
        ("zz", {"source": "made_up"}, "unknown normalization source"),
        ("higgs", {"source": "official_metadata", "xsec_pb": 1.0, "k_factor": 1.0, "filter_efficiency": 1.0, "sum_of_weights": 1.0}, "event normalization conflicts with override"),
    ],
)
def test_prepare_script_rejects_invalid_per_sample_normalization_before_root_io(
    tmp_path, monkeypatch, sample_name, normalization, message
):
    config_path, _, config = write_per_sample_config_and_inputs(tmp_path)
    config["samples"][sample_name]["normalization"] = normalization
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        prepare_demo,
        "prepare_sample",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["prepare_demo", "--config", str(config_path)])

    with pytest.raises(ValueError, match=message):
        prepare_demo.main()

    assert calls == []


def test_prepare_script_full_mode_writes_only_fresh_run_directory(
    tmp_path, monkeypatch
):
    config_path, input_paths = write_test_config_and_inputs(tmp_path)
    calls = install_fake_prepare_sample(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_demo",
            "--config",
            str(config_path),
            "--full",
            "--run-dir",
            "runs/full-baseline-2026-08-10",
        ],
    )

    prepare_demo.main()

    run_dir = tmp_path / "runs/full-baseline-2026-08-10"
    assert [call["entry_stop"] for call in calls] == [None, None, None]
    assert [call["chunk_size_events"] for call in calls] == [50_000] * 3
    assert (run_dir / "config.yaml").read_bytes() == config_path.read_bytes()
    assert (run_dir / "processed/mc_events.csv.gz").exists()
    assert (run_dir / "processed/data_events.csv.gz").exists()
    assert (run_dir / "artifacts/cutflow.json").exists()
    assert (run_dir / "artifacts/data_summary.json").exists()
    manifest = json.loads((run_dir / "artifacts/run_manifest.json").read_text())
    assert manifest["schema_version"] == "1.1"
    assert manifest["processing"]["read_policy"] == {
        "mode": "full",
        "entry_stop": None,
        "chunk_size_events": 50_000,
    }
    assert set(manifest["mc_normalization"]) == {
        "higgs_345060",
        "zz_700600",
    }
    assert manifest["config"]["snapshot_path"] == (
        "runs/full-baseline-2026-08-10/config.yaml"
    )
    assert manifest["outputs"]["locations"] == {
        "run_dir": "runs/full-baseline-2026-08-10",
        "processed_dir": "runs/full-baseline-2026-08-10/processed",
        "artifacts_dir": "runs/full-baseline-2026-08-10/artifacts",
    }
    assert {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file()
    } == {
        "config.yaml",
        "processed/mc_events.csv.gz",
        "processed/data_events.csv.gz",
        "artifacts/cutflow.json",
        "artifacts/data_summary.json",
        "artifacts/run_manifest.json",
    }
    assert not (tmp_path / "data/processed").exists()
    assert not (tmp_path / "outputs").exists()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--full"],
        ["--full", "--run-dir", "runs/full", "--output-dir", "artifacts"],
    ],
)
def test_prepare_script_preflight_errors_before_root_io(
    tmp_path, monkeypatch, arguments
):
    config_path, _ = write_test_config_and_inputs(tmp_path)
    calls = []
    monkeypatch.setattr(
        prepare_demo,
        "prepare_sample",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prepare_demo", "--config", str(config_path), *arguments],
    )

    with pytest.raises(ValueError):
        prepare_demo.main()

    assert calls == []
    assert not (tmp_path / "runs/full").exists()


def test_prepare_script_rejects_dangling_run_symlink_before_root_io(
    tmp_path, monkeypatch
):
    config_path, _ = write_test_config_and_inputs(tmp_path)
    calls = []
    monkeypatch.setattr(
        prepare_demo,
        "prepare_sample",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.chdir(tmp_path)
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs/full").symlink_to(
        tmp_path / "missing-target", target_is_directory=True
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_demo",
            "--config",
            str(config_path),
            "--full",
            "--run-dir",
            "runs/full",
        ],
    )

    with pytest.raises(FileExistsError, match="run directory already exists"):
        prepare_demo.main()

    assert calls == []
