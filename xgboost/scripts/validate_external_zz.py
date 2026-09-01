from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import io
from pathlib import Path
import tempfile

import numpy as np
import yaml

from src.external_zz_run import (
    EXTERNAL_PLOT_NAMES,
    assert_external_input_hashes_unchanged,
    claim_external_zz_output,
    publish_external_zz_manifest,
    record_external_zz_failure,
    resolve_external_zz_inputs,
    resolve_external_zz_output,
    write_external_zz_artifacts,
)
from src.external_zz_validation import (
    evaluate_external_zz,
    save_external_zz_plots,
    score_external_zz,
)
from src.pipeline import prepare_sample
from src.provenance import software_versions
from src.selection import SelectionConfig


_ENHANCED_SELECTION = {
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
_TOP_LEVEL_KEYS = {
    "schema_version",
    "luminosity_pb",
    "tree_name",
    "momentum_unit",
    "input_profile",
    "entry_stop",
    "chunk_size_events",
    "samples",
    "selection",
}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Validate the frozen DSID 363490 model on external DSID 700600"
    )
    parser.add_argument("--training-run", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parents[1]
    working_directory = Path.cwd()
    # This pure path preflight intentionally precedes every config, ROOT,
    # training-manifest, table, and model read.
    preflight = resolve_external_zz_output(
        project_root=project_root,
        working_directory=working_directory,
        training_run=args.training_run,
        run_dir=args.run_dir,
    )

    config_path = Path(args.config)
    config_bytes = config_path.read_bytes()
    config, selection, sample = _validated_config(config_bytes)
    inputs = resolve_external_zz_inputs(
        training_run=args.training_run,
        config_path=config_path,
        external_root=sample["path"],
    )
    if inputs.snapshots["config"] != config_bytes:
        raise RuntimeError("external validation config changed during input resolution")

    layout = claim_external_zz_output(preflight)
    try:
        prepared = prepare_sample(
            sample["path"],
            sample_name="external_zz_700600",
            selection=selection,
            tree_name=config["tree_name"],
            momentum_unit=config["momentum_unit"],
            is_data=False,
            label=sample["label"],
            expected_channels=sample["channel_numbers"],
            luminosity_pb=float(config["luminosity_pb"]),
            entry_stop=config["entry_stop"],
            chunk_size_events=config["chunk_size_events"],
            input_profile=sample["input_profile"],
            normalization_override=None,
        )
        model = _load_frozen_model(inputs.snapshots["model"])
        scored = score_external_zz(model, prepared.frame)
        metrics = evaluate_external_zz(
            inputs.training_test, scored, inputs.working_points
        )
        metrics["external_selection"] = {
            "read_rows": int(prepared.cutflow["stages"]["read"]["count"]),
            "selected_rows": int(
                prepared.cutflow["stages"]["selected"]["count"]
            ),
        }
        plots = _plot_bytes(
            inputs.training_test, scored, inputs.working_points
        )
        assert_external_input_hashes_unchanged(inputs)
        receipt = write_external_zz_artifacts(
            layout,
            config_source=config_path,
            config_bytes=config_bytes,
            metrics=metrics,
            scores=scored,
            plots=plots,
        )
        publish_external_zz_manifest(
            layout,
            inputs,
            receipt=receipt,
            software=software_versions(),
        )
    except Exception as error:
        record_external_zz_failure(layout, error)
        raise


def _validated_config(
    payload: bytes,
) -> tuple[dict[str, object], SelectionConfig, dict[str, object]]:
    try:
        raw = yaml.safe_load(payload)
    except yaml.YAMLError as error:
        raise ValueError("external validation config is not valid YAML") from error
    if not isinstance(raw, dict) or set(raw) != _TOP_LEVEL_KEYS:
        raise ValueError("external validation config keys do not match the frozen contract")
    if raw.get("schema_version") != "1.0":
        raise ValueError("external validation schema_version must be 1.0")
    if raw.get("tree_name") != "analysis":
        raise ValueError("external validation tree_name must be analysis")
    if raw.get("momentum_unit") != "GeV":
        raise ValueError("external validation momentum_unit must be GeV")
    if raw.get("input_profile") != "release22":
        raise ValueError("external validation input_profile must be release22")
    if raw.get("entry_stop") is not None:
        raise ValueError("external validation must read the full 700600 ROOT")
    if raw.get("chunk_size_events") != 50_000:
        raise ValueError("external validation chunk_size_events must be 50000")
    luminosity = raw.get("luminosity_pb")
    if isinstance(luminosity, bool) or luminosity != 10_000.0:
        raise ValueError("external validation luminosity_pb must be 10000.0")
    if raw.get("selection") != _ENHANCED_SELECTION:
        raise ValueError("external validation must use the exact enhanced selection")
    samples = raw.get("samples")
    if not isinstance(samples, dict) or set(samples) != {"zz"}:
        raise ValueError("external validation config must contain only the ZZ sample")
    sample = samples["zz"]
    required_sample_keys = {
        "path",
        "channel_numbers",
        "label",
        "input_profile",
    }
    if not isinstance(sample, dict) or set(sample) != required_sample_keys:
        raise ValueError("external ZZ sample keys do not match the frozen contract")
    if (
        not isinstance(sample["path"], str)
        or not sample["path"]
        or sample["channel_numbers"] != [700600]
        or sample["label"] != 0
        or sample["input_profile"] != "release22"
    ):
        raise ValueError("external ZZ sample must be Release-22 DSID 700600 label 0")
    selection = SelectionConfig.from_mapping(raw["selection"])
    return raw, selection, sample


class _FrozenBoosterModel:
    def __init__(self, booster, xgboost_module) -> None:
        self._booster = booster
        self._xgboost = xgboost_module

    def predict_proba(self, values) -> np.ndarray:
        matrix = self._xgboost.DMatrix(values, feature_names=list(values.columns))
        scores = np.asarray(self._booster.predict(matrix), dtype=float)
        return np.column_stack([1.0 - scores, scores])


def _load_frozen_model(payload: bytes):
    """Load XGBoost JSON bytes without exposing or invoking a fit method."""
    import xgboost

    booster = xgboost.Booster()
    booster.load_model(bytearray(payload))
    return _FrozenBoosterModel(booster, xgboost)


def _plot_bytes(training_test, external, points) -> dict[str, bytes]:
    with tempfile.TemporaryDirectory(prefix="task5-external-zz-plots-") as temporary:
        destination = Path(temporary) / "plots"
        save_external_zz_plots(
            training_test, external, points, destination
        )
        actual = {path.name for path in destination.iterdir() if path.is_file()}
        if actual != set(EXTERNAL_PLOT_NAMES):
            raise ValueError("external plots do not match the approved contract")
        return {
            name: (destination / name).read_bytes()
            for name in EXTERNAL_PLOT_NAMES
        }


if __name__ == "__main__":
    main()
