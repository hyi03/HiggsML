from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.features import FEATURES
from src import full_training_evaluation, full_training_model
from src.pipeline import PreparedSample
from src.weights import MCNormalization

from test_external_zz_run import EXTERNAL_OUTPUTS, synthetic_training_run


def _module():
    assert importlib.util.find_spec("scripts.validate_external_zz") is not None
    return importlib.import_module("scripts.validate_external_zz")


def _selection() -> dict[str, object]:
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
        "lepton_quality": {
            "enabled": True,
            "require_event_trigger": True,
            "require_trigger_match": True,
            "require_tight_id": True,
            "track_isolation_max": 0.3,
            "calo_isolation_max": 0.3,
            "electron_d0sig_max": 5.0,
            "muon_d0sig_max": 3.0,
            "z0_sintheta_max_mm": 0.5,
        },
    }


def write_config(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "external.root"
    root.write_bytes(b"fake-root-never-opened")
    config = {
        "schema_version": "1.0",
        "luminosity_pb": 10000.0,
        "tree_name": "analysis",
        "momentum_unit": "GeV",
        "input_profile": "release22",
        "entry_stop": None,
        "chunk_size_events": 50000,
        "samples": {
            "zz": {
                "path": str(root),
                "channel_numbers": [700600],
                "label": 0,
                "input_profile": "release22",
            }
        },
        "selection": _selection(),
    }
    path = tmp_path / "external.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path, root


def external_frame() -> pd.DataFrame:
    rows = []
    for index, score in enumerate((0.2, 0.5, 0.8)):
        rows.append(
            {
                **{
                    feature: score + 0.001 * feature_index
                    for feature_index, feature in enumerate(FEATURES)
                },
                "m4l": 110.0 + 15.0 * index,
                "eventNumber": 200 + index,
                "channelNumber": 700600,
                "split": ("train", "validation", "test")[index],
                "label": 0,
                "physical_weight": (-2.0 if index == 1 else 1.0),
            }
        )
    return pd.DataFrame(rows)


class _FrozenModel:
    def predict_proba(self, values: pd.DataFrame) -> np.ndarray:
        scores = np.asarray([0.2, 0.5, 0.8], dtype=float)
        return np.column_stack([1.0 - scores, scores])


def test_repository_external_config_is_exact_release22_enhanced_700600():
    """A smoke limit, legacy selection, or extra sample would invalidate real validation."""
    path = Path("config/external_zz_700600.yaml")
    assert path.exists()
    config = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert config == {
        "schema_version": "1.0",
        "luminosity_pb": 10000.0,
        "tree_name": "analysis",
        "momentum_unit": "GeV",
        "input_profile": "release22",
        "entry_stop": None,
        "chunk_size_events": 50000,
        "samples": {
            "zz": {
                "path": "data/raw/zz.root",
                "channel_numbers": [700600],
                "label": 0,
                "input_profile": "release22",
            }
        },
        "selection": _selection(),
    }


@pytest.mark.parametrize("kind", ["directory", "dangling_symlink"])
def test_cli_refuses_existing_output_before_any_input_read(
    tmp_path, monkeypatch, kind
):
    """Output ownership must be decided before config, ROOT, model, or table reads."""
    module = _module()
    output = tmp_path / "external-run"
    if kind == "directory":
        output.mkdir()
    else:
        output.symlink_to(tmp_path / "missing")
    calls = []
    monkeypatch.setattr(
        module,
        "resolve_external_zz_inputs",
        lambda **kwargs: calls.append("inputs")
        or (_ for _ in ()).throw(AssertionError("input resolution reached")),
    )
    monkeypatch.setattr(
        module,
        "prepare_sample",
        lambda *args, **kwargs: calls.append("root")
        or (_ for _ in ()).throw(AssertionError("ROOT reached")),
    )
    monkeypatch.setattr(
        module,
        "_load_frozen_model",
        lambda payload: calls.append("model")
        or (_ for _ in ()).throw(AssertionError("model reached")),
    )

    with pytest.raises(FileExistsError, match="already exists"):
        module.main(
            [
                "--training-run",
                str(tmp_path / "training"),
                "--config",
                str(tmp_path / "config.yaml"),
                "--run-dir",
                str(output),
            ]
        )

    assert calls == []


def test_zero_fit_cli_uses_only_frozen_model_and_publishes_exact_outputs(
    tmp_path, monkeypatch
):
    """Any fit, candidate comparison, or working-point rebuild is forbidden on 700600."""
    module = _module()
    training = synthetic_training_run(tmp_path)
    config, root = write_config(tmp_path)
    output = tmp_path / "external-run"
    calls = []

    def forbidden(*args, **kwargs):
        raise AssertionError("external validation attempted training")

    assert not hasattr(module, "cross_validate_candidates")
    assert not hasattr(module, "fit_final_model")
    assert not hasattr(module, "build_working_points")
    monkeypatch.setattr(full_training_model, "cross_validate_candidates", forbidden)
    monkeypatch.setattr(full_training_model, "fit_final_model", forbidden)
    monkeypatch.setattr(full_training_evaluation, "build_working_points", forbidden)

    def fake_prepare(path, **kwargs):
        calls.append(("prepare", Path(path), kwargs))
        assert Path(path) == root
        assert kwargs["sample_name"] == "external_zz_700600"
        assert kwargs["expected_channels"] == [700600]
        assert kwargs["label"] == 0
        assert kwargs["is_data"] is False
        assert kwargs["entry_stop"] is None
        assert kwargs["input_profile"] == "release22"
        return PreparedSample(
            frame=external_frame(),
            cutflow={"stages": {"read": {"count": 3}, "selected": {"count": 3}}},
            normalization=MCNormalization(1.0, 1.0, 1.0, 1.0),
        )

    def fake_plots(training_test, external, points, destination):
        calls.append(("plots", len(training_test), len(external)))
        destination = Path(destination)
        destination.mkdir(parents=True)
        for name in (
            "external_score_comparison.png",
            "external_kinematics_comparison.png",
            "external_mass_comparison.png",
        ):
            (destination / name).write_bytes(name.encode())

    monkeypatch.setattr(module, "prepare_sample", fake_prepare)
    monkeypatch.setattr(module, "_load_frozen_model", lambda payload: _FrozenModel())
    monkeypatch.setattr(module, "save_external_zz_plots", fake_plots)

    module.main(
        [
            "--training-run",
            str(training),
            "--config",
            str(config),
            "--run-dir",
            str(output),
        ]
    )

    files = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    assert files == EXTERNAL_OUTPUTS | {"manifest.json"}
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert len(pd.read_csv(output / "predictions/external_zz_scores.csv.gz")) == 3
    assert calls[0][0] == "prepare"
    assert calls[1][0] == "plots"
