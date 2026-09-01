from __future__ import annotations

import json
import hashlib
import io
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Thread, current_thread

import pandas as pd
import pytest

from src import full_training_run
from src.full_training_run import (
    TrainingArtifactReceipt,
    TrainingInput,
    TrainingOutputLayout,
    assert_input_hashes_unchanged,
    claim_training_output,
    load_training_mc_frame,
    publish_training_manifest,
    record_training_failure,
    resolve_training_input,
    resolve_training_output,
    snapshot_input_hashes,
    write_training_artifacts,
)
from src.provenance import sha256_file


def _json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")


def _synthetic_task4a_run(tmp_path: Path) -> Path:
    run = tmp_path / "task4a"
    (run / "processed").mkdir(parents=True)
    (run / "artifacts").mkdir()
    config = run / "config.yaml"
    config.write_bytes(b"entry_stop: 5000\n")
    pd.DataFrame(
        {
            "eventNumber": [1, 2, 3],
            "channelNumber": [345060, 345060, 700600],
            "label": [1, 1, 0],
            "split": ["train", "validation", "test"],
            "physical_weight": [1.0, -0.25, 2.0],
            "feature": [0.1, 0.2, 0.3],
        }
    ).to_csv(run / "processed/mc_events.csv.gz", index=False)
    _json(
        run / "artifacts/data_summary.json",
        {
            "schema_version": "1.0",
            "data": {},
            "mc": {
                "higgs": {"label": 1, "selected_events": 2},
                "zz": {"label": 0, "selected_events": 1},
            },
        },
    )
    _json(
        run / "artifacts/run_manifest.json",
        {
            "schema_version": "1.1",
            "config": {
                "path": "config/demo.yaml",
                "snapshot_path": str(config),
                "sha256": sha256_file(config),
            },
            "processing": {
                "read_policy": {
                    "mode": "full",
                    "entry_stop": None,
                    "chunk_size_events": 50_000,
                }
            },
            "outputs": {
                "locations": {
                    "run_dir": str(run),
                    "processed_dir": str(run / "processed"),
                    "artifacts_dir": str(run / "artifacts"),
                }
            },
        },
    )
    return run


def test_resolve_training_input_validates_synthetic_full_mc_without_data_table(tmp_path):
    run = _synthetic_task4a_run(tmp_path)

    resolved = resolve_training_input(run)

    assert isinstance(resolved, TrainingInput)
    assert resolved.input_run == run
    assert resolved.expected_rows == 3
    assert resolved.hashes == snapshot_input_hashes(resolved)
    assert set(resolved.hashes) == {"config", "mc", "summary", "manifest"}
    assert not (run / "processed/data_events.csv.gz").exists()


def test_load_training_mc_frame_reads_one_hashed_snapshot_then_parses_bytes(
    tmp_path, monkeypatch
):
    resolved = resolve_training_input(_synthetic_task4a_run(tmp_path))
    original_read_bytes = Path.read_bytes
    original_read_csv = pd.read_csv
    filesystem_reads: list[Path] = []
    parse_sources: list[object] = []

    def recording_read_bytes(path):
        if path == resolved.mc_path:
            filesystem_reads.append(path)
        return original_read_bytes(path)

    def recording_read_csv(source, *args, **kwargs):
        parse_sources.append(source)
        return original_read_csv(source, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", recording_read_bytes)
    monkeypatch.setattr(pd, "read_csv", recording_read_csv)

    loaded = load_training_mc_frame(resolved)

    assert filesystem_reads == [resolved.mc_path]
    assert len(parse_sources) == 1
    assert isinstance(parse_sources[0], io.BytesIO)
    assert loaded["eventNumber"].tolist() == [1, 2, 3]


def test_load_training_mc_frame_rejects_swap_restored_bytes_before_parsing(
    tmp_path, monkeypatch
):
    resolved = resolve_training_input(_synthetic_task4a_run(tmp_path))
    original_bytes = resolved.mc_path.read_bytes()
    alternate = pd.read_csv(resolved.mc_path)
    alternate["feature"] += 100.0
    alternate_path = tmp_path / "alternate.csv.gz"
    alternate.to_csv(alternate_path, index=False)
    alternate_bytes = alternate_path.read_bytes()
    original_read_bytes = Path.read_bytes
    original_read_csv = pd.read_csv
    filesystem_reads: list[Path] = []
    parse_sources: list[object] = []

    def swap_restore_during_read(path):
        if path != resolved.mc_path:
            return original_read_bytes(path)
        filesystem_reads.append(path)
        path.write_bytes(alternate_bytes)
        try:
            return original_read_bytes(path)
        finally:
            path.write_bytes(original_bytes)

    def recording_read_csv(source, *args, **kwargs):
        parse_sources.append(source)
        return original_read_csv(source, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", swap_restore_during_read)
    monkeypatch.setattr(pd, "read_csv", recording_read_csv)

    with pytest.raises(RuntimeError, match="Task 4A input changed during training"):
        load_training_mc_frame(resolved)

    assert filesystem_reads == [resolved.mc_path]
    assert parse_sources == []
    assert original_read_bytes(resolved.mc_path) == original_bytes


@pytest.mark.parametrize(
    "relative_path",
    ["artifacts/run_manifest.json", "processed/mc_events.csv.gz"],
)
def test_resolve_training_input_rejects_missing_required_artifact(tmp_path, relative_path):
    run = _synthetic_task4a_run(tmp_path)
    (run / relative_path).unlink()

    with pytest.raises(FileNotFoundError, match="Task 4A input"):
        resolve_training_input(run)


def test_resolve_training_input_requires_manifest_schema_1_1(tmp_path):
    run = _synthetic_task4a_run(tmp_path)
    manifest = run / "artifacts/run_manifest.json"
    payload = json.loads(manifest.read_text())
    payload["schema_version"] = "1.0"
    _json(manifest, payload)

    with pytest.raises(ValueError, match="schema_version.*1.1"):
        resolve_training_input(run)


def test_resolve_training_input_accepts_explicit_complete_manifest_status(tmp_path):
    run = _synthetic_task4a_run(tmp_path)
    manifest = run / "artifacts/run_manifest.json"
    payload = json.loads(manifest.read_text())
    payload["status"] = "complete"
    _json(manifest, payload)

    assert resolve_training_input(run).expected_rows == 3


@pytest.mark.parametrize("status", ["failed", "incomplete", 1, None, True])
def test_resolve_training_input_rejects_explicit_noncomplete_manifest_status(
    tmp_path, status
):
    run = _synthetic_task4a_run(tmp_path)
    manifest = run / "artifacts/run_manifest.json"
    payload = json.loads(manifest.read_text())
    payload["status"] = status
    _json(manifest, payload)

    with pytest.raises(ValueError, match="status.*complete"):
        resolve_training_input(run)


@pytest.mark.parametrize(
    "policy",
    [
        {"mode": "head", "entry_stop": None, "chunk_size_events": 50_000},
        {"mode": "full", "entry_stop": 5_000, "chunk_size_events": 50_000},
    ],
)
def test_resolve_training_input_requires_unlimited_full_read_policy(tmp_path, policy):
    run = _synthetic_task4a_run(tmp_path)
    manifest = run / "artifacts/run_manifest.json"
    payload = json.loads(manifest.read_text())
    payload["processing"]["read_policy"] = policy
    _json(manifest, payload)

    with pytest.raises(ValueError, match="full.*entry_stop"):
        resolve_training_input(run)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("rows", "selected event count"),
        ("labels", "label count"),
    ],
)
def test_resolve_training_input_reconciles_summary_rows_and_labels(
    tmp_path, mutation, message
):
    run = _synthetic_task4a_run(tmp_path)
    summary = run / "artifacts/data_summary.json"
    payload = json.loads(summary.read_text())
    if mutation == "rows":
        payload["mc"]["higgs"]["selected_events"] = 3
    else:
        payload["mc"]["higgs"]["label"] = 0
    _json(summary, payload)

    with pytest.raises(ValueError, match=message):
        resolve_training_input(run)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_resolve_training_input_rejects_nonfinite_mc_values(tmp_path, bad):
    run = _synthetic_task4a_run(tmp_path)
    mc_path = run / "processed/mc_events.csv.gz"
    frame = pd.read_csv(mc_path)
    frame.loc[0, "feature"] = bad
    frame.to_csv(mc_path, index=False)

    with pytest.raises(ValueError, match="finite"):
        resolve_training_input(run)


@pytest.mark.parametrize(
    "relative_path",
    [
        "config.yaml",
        "processed/mc_events.csv.gz",
        "artifacts/data_summary.json",
        "artifacts/run_manifest.json",
    ],
)
def test_resolve_training_input_rejects_dangling_artifact_symlinks(
    tmp_path, relative_path
):
    run = _synthetic_task4a_run(tmp_path)
    path = run / relative_path
    path.unlink()
    path.symlink_to(path.with_name("missing-target"))

    with pytest.raises(FileNotFoundError, match="dangling symlink"):
        resolve_training_input(run)


def test_resolve_training_input_rejects_dangling_run_symlink(tmp_path):
    run = tmp_path / "task4a"
    run.symlink_to(tmp_path / "missing-run", target_is_directory=True)

    with pytest.raises(FileNotFoundError, match="dangling symlink"):
        resolve_training_input(run)


@pytest.mark.parametrize("name", ["config", "mc", "summary", "manifest"])
def test_final_hash_check_detects_each_changed_task4a_input(tmp_path, name):
    resolved = resolve_training_input(_synthetic_task4a_run(tmp_path))
    paths = {
        "config": resolved.config_path,
        "mc": resolved.mc_path,
        "summary": resolved.summary_path,
        "manifest": resolved.manifest_path,
    }
    with paths[name].open("ab") as handle:
        handle.write(b"changed")

    with pytest.raises(RuntimeError, match="Task 4A input changed during training"):
        assert_input_hashes_unchanged(resolved)


def test_resolve_training_input_rejects_mutation_after_validation(tmp_path, monkeypatch):
    run = _synthetic_task4a_run(tmp_path)

    def mutate_validated_summary():
        with (run / "artifacts/data_summary.json").open("ab") as handle:
            handle.write(b"changed-after-validation")

    monkeypatch.setattr(
        full_training_run,
        "_after_input_validation",
        mutate_validated_summary,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="Task 4A input changed during training"):
        resolve_training_input(run)


def test_resolve_training_input_parses_snapshotted_bytes_not_swap_restored_path(
    tmp_path, monkeypatch
):
    run = _synthetic_task4a_run(tmp_path)
    manifest = run / "artifacts/run_manifest.json"
    valid_bytes = manifest.read_bytes()
    invalid_bytes = b"not-json-but-stable-before-and-after"
    manifest.write_bytes(invalid_bytes)
    original_reader = full_training_run._read_json_object

    def swap_only_while_path_parser_reads(path, name):
        if path == manifest:
            manifest.write_bytes(valid_bytes)
            try:
                return original_reader(path, name)
            finally:
                manifest.write_bytes(invalid_bytes)
        return original_reader(path, name)

    monkeypatch.setattr(
        full_training_run, "_read_json_object", swap_only_while_path_parser_reads
    )

    with pytest.raises(ValueError, match="manifest is not valid JSON"):
        resolve_training_input(run)

    assert manifest.read_bytes() == invalid_bytes


def test_resolve_training_output_returns_fixed_fresh_layout(tmp_path):
    input_run = _synthetic_task4a_run(tmp_path)

    layout = resolve_training_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=input_run,
        run_dir="runs/training-1",
    )

    run_dir = tmp_path / "runs/training-1"
    assert layout == TrainingOutputLayout(
        run_dir=run_dir,
        config_snapshot=run_dir / "config.yaml",
        model_dir=run_dir / "model",
        artifacts_dir=run_dir / "artifacts",
        predictions_dir=run_dir / "predictions",
        plots_dir=run_dir / "plots",
    )
    assert not (tmp_path / "runs/training-1").exists()


@pytest.mark.parametrize("entry_kind", ["directory", "file", "dangling_symlink"])
def test_resolve_training_output_never_accepts_an_existing_entry(tmp_path, entry_kind):
    input_run = _synthetic_task4a_run(tmp_path)
    target = tmp_path / "runs/training-1"
    target.parent.mkdir()
    if entry_kind == "directory":
        target.mkdir()
    elif entry_kind == "file":
        target.write_bytes(b"owned")
    else:
        target.symlink_to(tmp_path / "missing-run", target_is_directory=True)

    with pytest.raises(FileExistsError, match="training run directory already exists"):
        resolve_training_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            input_run=input_run,
            run_dir="runs/training-1",
        )


@pytest.mark.parametrize(
    "protected",
    [
        ".",
        "data/new-training",
        "outputs/new-training",
        "config/new-training",
        "docs/new-training",
        "src/new-training",
        "scripts/new-training",
        "tests/new-training",
    ],
)
def test_resolve_training_output_rejects_project_and_protected_paths(
    tmp_path, protected
):
    input_run = _synthetic_task4a_run(tmp_path)

    with pytest.raises(ValueError, match="protected"):
        resolve_training_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            input_run=input_run,
            run_dir=protected,
        )


@pytest.mark.parametrize("suffix", ["", "nested-training"])
def test_resolve_training_output_protects_task4a_input_run(tmp_path, suffix):
    input_run = _synthetic_task4a_run(tmp_path)
    target = input_run / suffix if suffix else input_run

    with pytest.raises(ValueError, match="Task 4A input run"):
        resolve_training_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            input_run=input_run,
            run_dir=target,
        )


def test_claim_training_output_atomically_creates_fixed_directories(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_run = _synthetic_task4a_run(tmp_path)
    layout = resolve_training_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=input_run,
        run_dir="runs/training-1",
    )

    claimed = claim_training_output(layout)

    assert claimed.run_dir == layout.run_dir
    assert claimed.directory_identities is not None
    assert claimed.run_dir.is_dir()
    assert claimed.model_dir.is_dir()
    assert claimed.artifacts_dir.is_dir()
    assert claimed.predictions_dir.is_dir()
    assert claimed.plots_dir.is_dir()
    assert not claimed.config_snapshot.exists()


def test_two_concurrent_training_claims_have_exactly_one_winner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_run = _synthetic_task4a_run(tmp_path)
    layout = resolve_training_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=input_run,
        run_dir="runs/training-1",
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(claim_training_output, layout) for _ in range(2)]

    outcomes = []
    for future in futures:
        try:
            outcomes.append(future.result())
        except Exception as error:
            outcomes.append(error)
    assert sum(isinstance(outcome, TrainingOutputLayout) for outcome in outcomes) == 1
    failures = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
    assert len(failures) == 1
    assert isinstance(failures[0], FileExistsError)


def test_claim_uses_checked_absolute_path_after_cwd_change(tmp_path, monkeypatch):
    input_run = _synthetic_task4a_run(tmp_path)
    layout = resolve_training_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=input_run,
        run_dir="runs/training-1",
    )
    other = tmp_path / "other-cwd"
    other.mkdir()
    monkeypatch.chdir(other)

    claimed = claim_training_output(layout)

    assert claimed.run_dir == tmp_path / "runs/training-1"
    assert claimed.run_dir.is_dir()
    assert not (other / "runs/training-1").exists()


def test_claim_rejects_parent_symlink_added_after_resolution(tmp_path):
    input_run = _synthetic_task4a_run(tmp_path)
    layout = resolve_training_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=input_run,
        run_dir="fresh-parent/training-1",
    )
    (tmp_path / "fresh-parent").symlink_to(input_run, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        claim_training_output(layout)

    assert not (input_run / "training-1").exists()


class _TinyModel:
    def __init__(self, payload: bytes = b"tiny-model") -> None:
        self.payload = payload

    def save_raw(self, *, raw_format: str) -> bytes:
        assert raw_format == "json"
        return self.payload


_JSON_ARTIFACT_NAMES = (
    "weight_summary.json",
    "metrics.json",
    "working_points.json",
)
_ARTIFACT_TABLE_NAMES = ("cv_results.csv",)
_PREDICTION_NAMES = (
    "oof_scores.csv.gz",
    "test_scores.csv.gz",
)
_PLOT_NAMES = (
    "roc_curve.png",
    "score_distributions.png",
    "cv_stability.png",
    "feature_importance.png",
    "mc_mass_sculpting.png",
    "mc_mass_signal_background.png",
    "mc_mass_working_points.png",
)


def test_frozen_artifact_allowlist_matches_approved_task4_layout_exactly():
    assert full_training_run.MODEL_NAME == "xgboost_model.json"
    assert full_training_run.JSON_ARTIFACT_NAMES == (
        "weight_summary.json",
        "metrics.json",
        "working_points.json",
    )
    assert full_training_run.ARTIFACT_TABLE_NAMES == ("cv_results.csv",)
    assert full_training_run.PREDICTION_NAMES == (
        "oof_scores.csv.gz",
        "test_scores.csv.gz",
    )
    assert full_training_run.PLOT_NAMES == (
        "roc_curve.png",
        "score_distributions.png",
        "cv_stability.png",
        "feature_importance.png",
        "mc_mass_sculpting.png",
        "mc_mass_signal_background.png",
        "mc_mass_working_points.png",
    )
    frozen = {
        full_training_run.MODEL_NAME,
        *full_training_run.JSON_ARTIFACT_NAMES,
        *full_training_run.ARTIFACT_TABLE_NAMES,
        *full_training_run.PREDICTION_NAMES,
        *full_training_run.PLOT_NAMES,
    }
    assert frozen.isdisjoint(
        {
            "model_selection.json",
            "overfitting_check.json",
            "warnings.json",
            "development_predictions.csv.gz",
            "candidate_cv_auc.png",
            "score_distribution.png",
            "train_test_score_comparison.png",
            "score_vs_m4l.png",
        }
    )


def _approved_artifact_inputs():
    json_artifacts = {
        name: {"name": name, "value": 0.9} for name in _JSON_ARTIFACT_NAMES
    }
    artifact_tables = {
        name: pd.DataFrame({"candidate": ["a", "b"], "weighted_auc": [0.8, 0.9]})
        for name in _ARTIFACT_TABLE_NAMES
    }
    prediction_frames = {
        name: pd.DataFrame({"eventNumber": [1, 2], "score": [0.2, 0.8]})
        for name in _PREDICTION_NAMES
    }
    plot_artifacts = {name: f"bytes:{name}".encode() for name in _PLOT_NAMES}
    return json_artifacts, artifact_tables, prediction_frames, plot_artifacts


def _claimed_training_layout(tmp_path: Path, monkeypatch) -> tuple[TrainingInput, TrainingOutputLayout]:
    monkeypatch.chdir(tmp_path)
    training_input = resolve_training_input(_synthetic_task4a_run(tmp_path))
    layout = resolve_training_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=training_input.input_run,
        run_dir="runs/training-1",
    )
    claimed = claim_training_output(layout)
    return training_input, claimed


def _write_tiny_artifacts(
    tmp_path: Path, monkeypatch
) -> tuple[TrainingInput, TrainingOutputLayout, TrainingArtifactReceipt]:
    training_input, layout = _claimed_training_layout(tmp_path, monkeypatch)
    config_source = tmp_path / "full_training.yaml"
    config_bytes = b"schema_version: '1.0'\n"
    config_source.write_bytes(config_bytes)
    json_artifacts, artifact_tables, prediction_frames, plot_artifacts = (
        _approved_artifact_inputs()
    )
    receipt = write_training_artifacts(
        layout,
        config_source=config_source,
        config_bytes=config_bytes,
        model=_TinyModel(),
        json_artifacts=json_artifacts,
        artifact_tables=artifact_tables,
        prediction_frames=prediction_frames,
        plot_artifacts=plot_artifacts,
    )
    return training_input, layout, receipt


def test_write_training_artifacts_returns_opaque_receipt_for_exact_contract(
    tmp_path, monkeypatch
):
    _, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)

    assert isinstance(receipt, TrainingArtifactReceipt)
    assert layout.config_snapshot.read_bytes() == b"schema_version: '1.0'\n"
    assert (layout.model_dir / "xgboost_model.json").read_bytes() == b"tiny-model"
    assert set(path.name for path in layout.artifacts_dir.iterdir()) == set(
        _JSON_ARTIFACT_NAMES + _ARTIFACT_TABLE_NAMES
    )
    assert set(path.name for path in layout.predictions_dir.iterdir()) == set(
        _PREDICTION_NAMES
    )
    assert set(path.name for path in layout.plots_dir.iterdir()) == set(_PLOT_NAMES)
    assert not [path for path in layout.run_dir.rglob("*") if ".tmp" in path.name]
    assert not (layout.artifacts_dir / "training_manifest.json").exists()

    with pytest.raises(TypeError):
        TrainingArtifactReceipt()


@pytest.mark.parametrize("category", ["json", "tables", "predictions", "plots"])
def test_writer_rejects_missing_or_extra_approved_artifact_names(
    tmp_path, monkeypatch, category
):
    _, layout = _claimed_training_layout(tmp_path, monkeypatch)
    source = tmp_path / "full_training.yaml"
    source.write_bytes(b"config")
    json_artifacts, artifact_tables, prediction_frames, plot_artifacts = (
        _approved_artifact_inputs()
    )
    selected = {
        "json": json_artifacts,
        "tables": artifact_tables,
        "predictions": prediction_frames,
        "plots": plot_artifacts,
    }[category]
    selected.pop(next(iter(selected)))
    selected["unexpected.file"] = {} if category == "json" else (
        pd.DataFrame({"x": [1]})
        if category in {"tables", "predictions"}
        else b"extra"
    )

    with pytest.raises(ValueError, match="approved artifact contract"):
        write_training_artifacts(
            layout,
            config_source=source,
            config_bytes=b"config",
            model=_TinyModel(),
            json_artifacts=json_artifacts,
            artifact_tables=artifact_tables,
            prediction_frames=prediction_frames,
            plot_artifacts=plot_artifacts,
        )

    assert (layout.run_dir / ".terminal.failed").is_dir()


def test_writer_rechecks_training_config_immediately_before_snapshot(tmp_path, monkeypatch):
    _, layout = _claimed_training_layout(tmp_path, monkeypatch)
    source = tmp_path / "full_training.yaml"
    source.write_bytes(b"changed")
    json_artifacts, artifact_tables, prediction_frames, plot_artifacts = (
        _approved_artifact_inputs()
    )

    with pytest.raises(RuntimeError, match="training config changed"):
        write_training_artifacts(
            layout,
            config_source=source,
            config_bytes=b"original",
            model=_TinyModel(),
            json_artifacts=json_artifacts,
            artifact_tables=artifact_tables,
            prediction_frames=prediction_frames,
            plot_artifacts=plot_artifacts,
        )

    assert not layout.config_snapshot.exists()
    assert not (layout.artifacts_dir / "training_manifest.json").exists()
    assert (layout.run_dir / "failure.json").exists()


def test_writer_rejects_non_json_numbers_and_never_publishes_manifest(
    tmp_path, monkeypatch
):
    _, layout = _claimed_training_layout(tmp_path, monkeypatch)
    source = tmp_path / "full_training.yaml"
    source.write_bytes(b"config")
    json_artifacts, artifact_tables, prediction_frames, plot_artifacts = (
        _approved_artifact_inputs()
    )
    json_artifacts["metrics.json"] = {"bad": float("nan")}

    with pytest.raises(ValueError, match="Out of range float values"):
        write_training_artifacts(
            layout,
            config_source=source,
            config_bytes=b"config",
            model=_TinyModel(),
            json_artifacts=json_artifacts,
            artifact_tables=artifact_tables,
            prediction_frames=prediction_frames,
            plot_artifacts=plot_artifacts,
        )

    assert not (layout.artifacts_dir / "metrics.json").exists()
    assert not (layout.artifacts_dir / "training_manifest.json").exists()
    assert json.loads((layout.run_dir / "failure.json").read_text())["status"] == "failed"


def test_writer_failure_leaves_no_complete_manifest_and_records_failure(
    tmp_path, monkeypatch
):
    class BrokenModel:
        def save_raw(self, *, raw_format):
            raise OSError("model write interrupted")

    _, layout = _claimed_training_layout(tmp_path, monkeypatch)
    source = tmp_path / "full_training.yaml"
    source.write_bytes(b"config")
    json_artifacts, artifact_tables, prediction_frames, plot_artifacts = (
        _approved_artifact_inputs()
    )

    with pytest.raises(OSError, match="model write interrupted"):
        write_training_artifacts(
            layout,
            config_source=source,
            config_bytes=b"config",
            model=BrokenModel(),
            json_artifacts=json_artifacts,
            artifact_tables=artifact_tables,
            prediction_frames=prediction_frames,
            plot_artifacts=plot_artifacts,
        )

    assert not (layout.artifacts_dir / "training_manifest.json").exists()
    failure = json.loads((layout.run_dir / "failure.json").read_text())
    assert failure == {
        "status": "failed",
        "error_type": "OSError",
        "message": "model write interrupted",
    }

    with pytest.raises((TypeError, RuntimeError)):
        publish_training_manifest(
            layout,
            resolve_training_input(tmp_path / "task4a"),
            receipt={"config.yaml": None},
            software={},
            effective_parameters={},
            features=[],
            sampling_fractions={"higgs": 1.0, "zz": 1.0},
            weight_policy={},
            fold_policy={},
            selected_model={},
            working_points={},
            warnings={},
        )
    assert not (layout.artifacts_dir / "training_manifest.json").exists()


def test_record_training_failure_public_boundary_is_terminal_and_no_clobber(
    tmp_path, monkeypatch
):
    _, layout = _claimed_training_layout(tmp_path, monkeypatch)

    record_training_failure(layout, RuntimeError("public failure"))
    record_training_failure(layout, OSError("later failure"))

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert not (layout.run_dir / ".terminal.lock").exists()
    assert not (layout.artifacts_dir / "training_manifest.json").exists()
    assert json.loads((layout.run_dir / "failure.json").read_text()) == {
        "status": "failed",
        "error_type": "RuntimeError",
        "message": "public failure",
    }


def test_writer_never_overwrites_an_existing_output_entry(tmp_path, monkeypatch):
    _, layout = _claimed_training_layout(tmp_path, monkeypatch)
    source = tmp_path / "full_training.yaml"
    source.write_bytes(b"config")
    json_artifacts, artifact_tables, prediction_frames, plot_artifacts = (
        _approved_artifact_inputs()
    )
    existing = layout.artifacts_dir / "metrics.json"
    existing.write_bytes(b"owned")

    with pytest.raises(FileExistsError, match="output entry already exists"):
        write_training_artifacts(
            layout,
            config_source=source,
            config_bytes=b"config",
            model=_TinyModel(),
            json_artifacts=json_artifacts,
            artifact_tables=artifact_tables,
            prediction_frames=prediction_frames,
            plot_artifacts=plot_artifacts,
        )

    assert existing.read_bytes() == b"owned"
    assert not (layout.artifacts_dir / "training_manifest.json").exists()


def _publish_tiny_manifest(
    layout: TrainingOutputLayout,
    training_input: TrainingInput,
    receipt: TrainingArtifactReceipt,
):
    return publish_training_manifest(
        layout,
        training_input,
        receipt=receipt,
        software={"python": "3.12-test"},
        effective_parameters={"max_depth": 2, "min_child_weight": 20},
        features=["feature_a", "feature_b"],
        sampling_fractions={"higgs": 1.0, "zz": 1.0},
        weight_policy={"fit": "class_balanced_abs_physical_weight"},
        fold_policy={"folds": 5, "assignment": "event_hash"},
        selected_model={"candidate": "depth2_child20", "trees": 12},
        working_points={"medium": {"threshold": 0.7}},
        warnings={"warning": False, "warning_reasons": []},
    )


def test_publisher_recounts_final_cv_results_artifact_table(tmp_path, monkeypatch):
    training_input, layout = _claimed_training_layout(tmp_path, monkeypatch)
    source = tmp_path / "full_training.yaml"
    source.write_bytes(b"config")
    receipt = write_training_artifacts(
        layout,
        config_source=source,
        config_bytes=b"config",
        model=_TinyModel(),
        json_artifacts={
            "weight_summary.json": {"rows": 3},
            "metrics.json": {"auc": 0.9},
            "working_points.json": {"medium": 0.7},
        },
        artifact_tables={
            "cv_results.csv": pd.DataFrame(
                {"candidate": ["a", "b"], "weighted_auc": [0.8, 0.9]}
            )
        },
        prediction_frames={
            "oof_scores.csv.gz": pd.DataFrame({"score": [0.2, 0.8]}),
            "test_scores.csv.gz": pd.DataFrame({"score": [0.3, 0.7]}),
        },
        plot_artifacts={
            "roc_curve.png": b"roc",
            "score_distributions.png": b"scores",
            "cv_stability.png": b"cv",
            "feature_importance.png": b"features",
            "mc_mass_sculpting.png": b"mass",
            "mc_mass_signal_background.png": b"signal-background-mass",
            "mc_mass_working_points.png": b"working-point-mass",
        },
    )
    cv_results = layout.artifacts_dir / "cv_results.csv"
    pd.DataFrame(
        {
            "candidate": ["replacement-a", "replacement-b", "replacement-c"],
            "weighted_auc": [0.81, 0.82, 0.83],
        }
    ).to_csv(cv_results, index=False)

    manifest = _publish_tiny_manifest(layout, training_input, receipt)

    assert manifest["outputs"]["artifacts/cv_results.csv"]["row_count"] == 3


def test_publish_training_manifest_hashes_every_output_and_is_last(tmp_path, monkeypatch):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)

    manifest = _publish_tiny_manifest(layout, training_input, receipt)

    manifest_path = layout.artifacts_dir / "training_manifest.json"
    assert json.loads(manifest_path.read_text()) == manifest
    assert manifest["schema_version"] == "1.0"
    assert manifest["status"] == "complete"
    assert manifest["sampling_fractions"] == {"higgs": 1.0, "zz": 1.0}
    assert manifest["features"] == ["feature_a", "feature_b"]
    assert manifest["selected_model"]["effective_parameters"]["max_depth"] == 2
    assert manifest["input_task4a"] == {
        "run_dir": str(training_input.input_run),
        "config_path": str(training_input.config_path),
        "mc_path": str(training_input.mc_path),
        "summary_path": str(training_input.summary_path),
        "manifest_path": str(training_input.manifest_path),
        "expected_rows": 3,
        "hashes": dict(training_input.hashes),
    }
    expected_relatives = [
        "config.yaml",
        "model/xgboost_model.json",
        *(f"artifacts/{name}" for name in _JSON_ARTIFACT_NAMES),
        *(f"artifacts/{name}" for name in _ARTIFACT_TABLE_NAMES),
        *(f"predictions/{name}" for name in _PREDICTION_NAMES),
        *(f"plots/{name}" for name in _PLOT_NAMES),
    ]
    assert set(manifest["outputs"]) == set(expected_relatives)
    for relative in expected_relatives:
        path = layout.run_dir / relative
        record = manifest["outputs"][relative]
        assert record["path"] == str(path)
        assert record["size_bytes"] == path.stat().st_size
        assert record["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        if relative.startswith("predictions/") or relative == "artifacts/cv_results.csv":
            assert record["row_count"] == len(pd.read_csv(path))
        else:
            assert "row_count" not in record


def test_publisher_rechecks_task4a_hashes_before_manifest(tmp_path, monkeypatch):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    with training_input.summary_path.open("ab") as handle:
        handle.write(b"changed")

    with pytest.raises(RuntimeError, match="Task 4A input changed during training"):
        _publish_tiny_manifest(layout, training_input, receipt)

    assert not (layout.artifacts_dir / "training_manifest.json").exists()
    assert (layout.run_dir / "failure.json").exists()


def test_publisher_requires_every_approved_output_before_manifest(tmp_path, monkeypatch):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    (layout.plots_dir / _PLOT_NAMES[0]).unlink()

    with pytest.raises(FileNotFoundError, match="required training output"):
        _publish_tiny_manifest(layout, training_input, receipt)

    assert not (layout.artifacts_dir / "training_manifest.json").exists()
    assert (layout.run_dir / "failure.json").exists()


def test_publisher_rejects_extra_on_disk_entry(tmp_path, monkeypatch):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    (layout.plots_dir / "extra.png").write_bytes(b"extra")

    with pytest.raises(ValueError, match="unexpected training output"):
        _publish_tiny_manifest(layout, training_input, receipt)

    assert not (layout.artifacts_dir / "training_manifest.json").exists()


def test_publisher_recomputes_final_csv_row_counts(tmp_path, monkeypatch):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    prediction = layout.predictions_dir / _PREDICTION_NAMES[0]
    pd.DataFrame({"eventNumber": [10, 11, 12], "score": [0.1, 0.2, 0.3]}).to_csv(
        prediction, index=False
    )

    manifest = _publish_tiny_manifest(layout, training_input, receipt)

    assert manifest["outputs"][f"predictions/{_PREDICTION_NAMES[0]}"][
        "row_count"
    ] == 3


def test_publisher_rejects_required_name_fifo_promptly_without_blocking(
    tmp_path, monkeypatch
):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    target = layout.predictions_dir / _PREDICTION_NAMES[0]
    target.unlink()
    os.mkfifo(target)
    outcomes = []

    def attempt_publish():
        try:
            _publish_tiny_manifest(layout, training_input, receipt)
        except Exception as error:
            outcomes.append(error)

    worker = Thread(target=attempt_publish, daemon=True)
    worker.start()
    worker.join(timeout=1)

    assert not worker.is_alive(), "FIFO audit blocked instead of failing promptly"
    assert len(outcomes) == 1
    assert isinstance(outcomes[0], ValueError)
    assert "regular file" in str(outcomes[0])
    assert not (layout.artifacts_dir / "training_manifest.json").exists()
    assert (layout.run_dir / ".terminal.failed").is_dir()


def test_publisher_rejects_required_name_directory_as_nonregular(
    tmp_path, monkeypatch
):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    target = layout.plots_dir / _PLOT_NAMES[0]
    target.unlink()
    target.mkdir()

    with pytest.raises(ValueError, match="regular file"):
        _publish_tiny_manifest(layout, training_input, receipt)

    assert not (layout.artifacts_dir / "training_manifest.json").exists()
    assert (layout.run_dir / ".terminal.failed").is_dir()


def test_writer_rejects_child_symlink_swap_before_any_write(tmp_path, monkeypatch):
    _, layout = _claimed_training_layout(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    layout.plots_dir.rmdir()
    layout.plots_dir.symlink_to(outside, target_is_directory=True)
    source = tmp_path / "full_training.yaml"
    source.write_bytes(b"config")
    json_artifacts, artifact_tables, prediction_frames, plot_artifacts = (
        _approved_artifact_inputs()
    )

    with pytest.raises(ValueError, match="ownership|symlink"):
        write_training_artifacts(
            layout,
            config_source=source,
            config_bytes=b"config",
            model=_TinyModel(),
            json_artifacts=json_artifacts,
            artifact_tables=artifact_tables,
            prediction_frames=prediction_frames,
            plot_artifacts=plot_artifacts,
        )

    assert list(outside.iterdir()) == []


def test_publisher_never_overwrites_existing_manifest(tmp_path, monkeypatch):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    manifest_path = layout.artifacts_dir / "training_manifest.json"
    manifest_path.write_bytes(b"owned")

    with pytest.raises(FileExistsError, match="output entry already exists"):
        _publish_tiny_manifest(layout, training_input, receipt)

    assert manifest_path.read_bytes() == b"owned"


@pytest.mark.parametrize("kind", ["bytes", "model", "csv"])
def test_writer_no_clobber_promotion_preserves_competing_destination(
    tmp_path, monkeypatch, kind
):
    _, layout = _claimed_training_layout(tmp_path, monkeypatch)
    source = tmp_path / "full_training.yaml"
    source.write_bytes(b"config")
    json_artifacts, artifact_tables, prediction_frames, plot_artifacts = (
        _approved_artifact_inputs()
    )
    target = {
        "bytes": layout.config_snapshot,
        "model": layout.model_dir / "xgboost_model.json",
        "csv": layout.predictions_dir / _PREDICTION_NAMES[0],
    }[kind]
    ready = Event()
    installed = Event()

    def competing_creator():
        assert ready.wait(timeout=5)
        target.write_bytes(b"competing-owner")
        installed.set()

    competitor = Thread(target=competing_creator)
    competitor.start()

    def pause_for_competitor(destination):
        if destination == target:
            ready.set()
            assert installed.wait(timeout=5)

    monkeypatch.setattr(
        full_training_run, "_before_no_clobber_promote", pause_for_competitor
    )
    with pytest.raises(FileExistsError, match="output entry already exists"):
        write_training_artifacts(
            layout,
            config_source=source,
            config_bytes=b"config",
            model=_TinyModel(),
            json_artifacts=json_artifacts,
            artifact_tables=artifact_tables,
            prediction_frames=prediction_frames,
            plot_artifacts=plot_artifacts,
        )
    competitor.join(timeout=5)

    assert target.read_bytes() == b"competing-owner"
    assert not [path for path in layout.run_dir.rglob("*") if ".tmp" in path.name]
    assert not (layout.artifacts_dir / "training_manifest.json").exists()


def test_manifest_no_clobber_promotion_preserves_competing_destination(
    tmp_path, monkeypatch
):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    target = layout.artifacts_dir / "training_manifest.json"
    ready = Event()
    installed = Event()

    def competing_creator():
        assert ready.wait(timeout=5)
        target.write_bytes(b"competing-manifest")
        installed.set()

    competitor = Thread(target=competing_creator)
    competitor.start()

    def pause_for_competitor(destination):
        if destination == target:
            ready.set()
            assert installed.wait(timeout=5)

    monkeypatch.setattr(
        full_training_run, "_before_no_clobber_promote", pause_for_competitor
    )
    with pytest.raises(FileExistsError, match="output entry already exists"):
        _publish_tiny_manifest(layout, training_input, receipt)
    competitor.join(timeout=5)

    assert target.read_bytes() == b"competing-manifest"
    assert not [path for path in layout.run_dir.rglob("*") if ".tmp" in path.name]


def test_unique_temp_collision_is_fail_safe_and_never_overwrites_stale_temp(
    tmp_path, monkeypatch
):
    _, layout = _claimed_training_layout(tmp_path, monkeypatch)
    source = tmp_path / "full_training.yaml"
    source.write_bytes(b"config")
    json_artifacts, artifact_tables, prediction_frames, plot_artifacts = (
        _approved_artifact_inputs()
    )
    stale = layout.run_dir / ".config.yaml.collision.tmp"
    calls = 0

    def collide_once(_length):
        nonlocal calls
        calls += 1
        if calls == 1:
            stale.write_bytes(b"stale-owner")
            return "collision"
        return f"unique-{calls}"

    monkeypatch.setattr(full_training_run.secrets, "token_hex", collide_once)
    with pytest.raises(ValueError, match="unexpected training output"):
        write_training_artifacts(
            layout,
            config_source=source,
            config_bytes=b"config",
            model=_TinyModel(),
            json_artifacts=json_artifacts,
            artifact_tables=artifact_tables,
            prediction_frames=prediction_frames,
            plot_artifacts=plot_artifacts,
        )

    assert stale.read_bytes() == b"stale-owner"
    assert not [
        path
        for path in layout.run_dir.rglob("*")
        if ".tmp" in path.name and path != stale
    ]
    assert not (layout.artifacts_dir / "training_manifest.json").exists()


def test_interrupted_temp_write_cleans_every_owned_unique_temp(tmp_path, monkeypatch):
    _, layout = _claimed_training_layout(tmp_path, monkeypatch)
    source = tmp_path / "full_training.yaml"
    source.write_bytes(b"config")
    json_artifacts, artifact_tables, prediction_frames, plot_artifacts = (
        _approved_artifact_inputs()
    )

    def interrupt_write(descriptor, payload):
        raise OSError("staged write interrupted")

    monkeypatch.setattr(full_training_run, "_write_all", interrupt_write)
    with pytest.raises(OSError, match="staged write interrupted"):
        write_training_artifacts(
            layout,
            config_source=source,
            config_bytes=b"config",
            model=_TinyModel(),
            json_artifacts=json_artifacts,
            artifact_tables=artifact_tables,
            prediction_frames=prediction_frames,
            plot_artifacts=plot_artifacts,
        )

    assert not [path for path in layout.run_dir.rglob("*") if ".tmp" in path.name]
    assert (layout.run_dir / ".terminal.failed").is_dir()


def test_publisher_rechecks_inputs_after_manifest_staging(tmp_path, monkeypatch):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    observed_staged = []

    def mutate_after_staging():
        observed_staged.extend(
            path
            for path in layout.artifacts_dir.iterdir()
            if path.name.startswith(".training_manifest.json.")
            and path.name.endswith(".tmp")
        )
        with training_input.manifest_path.open("ab") as handle:
            handle.write(b"changed-after-output-hashing")

    monkeypatch.setattr(
        full_training_run, "_before_final_input_recheck", mutate_after_staging
    )
    with pytest.raises(RuntimeError, match="Task 4A input changed during training"):
        _publish_tiny_manifest(layout, training_input, receipt)

    assert observed_staged
    assert not (layout.artifacts_dir / "training_manifest.json").exists()
    assert not [path for path in layout.run_dir.rglob("*") if ".tmp" in path.name]
    assert (layout.run_dir / ".terminal.failed").is_dir()


def test_manifest_link_rechecks_input_after_pre_promotion_hook(tmp_path, monkeypatch):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    target = layout.artifacts_dir / "training_manifest.json"

    def mutate_at_last_promotion_boundary(destination):
        if destination == target:
            with training_input.config_path.open("ab") as handle:
                handle.write(b"changed-at-last-boundary")

    monkeypatch.setattr(
        full_training_run,
        "_before_no_clobber_promote",
        mutate_at_last_promotion_boundary,
    )
    with pytest.raises(RuntimeError, match="Task 4A input changed during training"):
        _publish_tiny_manifest(layout, training_input, receipt)

    assert not target.exists()
    assert (layout.run_dir / ".terminal.failed").is_dir()


def test_partial_child_creation_failure_permanently_marks_claimed_root(
    tmp_path, monkeypatch
):
    input_run = _synthetic_task4a_run(tmp_path)
    layout = resolve_training_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=input_run,
        run_dir="runs/training-1",
    )
    original_mkdir = full_training_run.os.mkdir

    def fail_predictions(path, *args, **kwargs):
        if path == "predictions":
            raise OSError("child creation interrupted")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(full_training_run.os, "mkdir", fail_predictions)
    with pytest.raises(OSError, match="child creation interrupted"):
        claim_training_output(layout)

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert json.loads((layout.run_dir / "failure.json").read_text())["status"] == "failed"


def test_failed_failure_json_write_still_blocks_completion(tmp_path, monkeypatch):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    original_publish = full_training_run._atomic_publish_bytes

    def fail_failure_json(descriptor, parent, final_name, payload):
        if final_name == "failure.json":
            raise OSError("failure marker disk error")
        return original_publish(descriptor, parent, final_name, payload)

    monkeypatch.setattr(
        full_training_run, "_atomic_publish_bytes", fail_failure_json
    )
    full_training_run._best_effort_failure(layout, OSError("training failed"))

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert not (layout.run_dir / "failure.json").exists()
    assert not (layout.run_dir / ".terminal.lock").exists()
    with pytest.raises(RuntimeError, match="failed training run"):
        _publish_tiny_manifest(layout, training_input, receipt)
    assert not (layout.artifacts_dir / "training_manifest.json").exists()


def test_publish_wins_concurrent_failure_without_contradictory_terminal_state(
    tmp_path, monkeypatch
):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    publisher_staged = Event()
    release_publisher = Event()
    failure_attempted_lock = Event()
    original_acquire = full_training_run._terminal_lock_acquire

    def pause_publisher_after_staging():
        publisher_staged.set()
        assert release_publisher.wait(timeout=5)

    def observe_failure_lock(root, **kwargs):
        if current_thread().name == "failure-thread":
            failure_attempted_lock.set()
        return original_acquire(root, **kwargs)

    monkeypatch.setattr(
        full_training_run, "_before_final_input_recheck", pause_publisher_after_staging
    )
    monkeypatch.setattr(
        full_training_run, "_terminal_lock_acquire", observe_failure_lock
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        publishing = executor.submit(
            _publish_tiny_manifest, layout, training_input, receipt
        )
        assert publisher_staged.wait(timeout=5)
        failure = Thread(
            target=full_training_run._best_effort_failure,
            args=(layout, OSError("concurrent failure")),
            name="failure-thread",
        )
        failure.start()
        assert failure_attempted_lock.wait(timeout=5)
        release_publisher.set()
        manifest = publishing.result(timeout=5)
    failure.join(timeout=5)

    assert manifest["status"] == "complete"
    assert (layout.artifacts_dir / "training_manifest.json").exists()
    assert not (layout.run_dir / "failure.json").exists()
    assert not (layout.run_dir / ".terminal.failed").exists()
    assert not (layout.run_dir / ".terminal.lock").exists()


def test_failure_wins_concurrent_publish_without_complete_manifest(
    tmp_path, monkeypatch
):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    failure_has_lock = Event()
    release_failure = Event()
    original_install = full_training_run._install_failure_locked

    def pause_failure_with_lock(root, run_dir, error):
        if current_thread().name == "failure-thread":
            failure_has_lock.set()
            assert release_failure.wait(timeout=5)
        return original_install(root, run_dir, error)

    monkeypatch.setattr(
        full_training_run, "_install_failure_locked", pause_failure_with_lock
    )
    failure = Thread(
        target=full_training_run._best_effort_failure,
        args=(layout, OSError("concurrent failure")),
        name="failure-thread",
    )
    failure.start()
    assert failure_has_lock.wait(timeout=5)
    with ThreadPoolExecutor(max_workers=1) as executor:
        publishing = executor.submit(
            _publish_tiny_manifest, layout, training_input, receipt
        )
        release_failure.set()
        with pytest.raises(RuntimeError, match="failed training run"):
            publishing.result(timeout=5)
    failure.join(timeout=5)

    assert not (layout.artifacts_dir / "training_manifest.json").exists()
    assert (layout.run_dir / "failure.json").exists()
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert not (layout.run_dir / ".terminal.lock").exists()


@pytest.mark.parametrize("phase", ["after_open", "pre_completion"])
@pytest.mark.parametrize("component", ["parent", "root", "child"])
def test_late_named_path_swap_fails_closed_without_manifest_or_residue(
    tmp_path, monkeypatch, phase, component
):
    training_input, layout, receipt = _write_tiny_artifacts(tmp_path, monkeypatch)
    swapped = False

    def swap_named_component():
        nonlocal swapped
        if swapped:
            return
        swapped = True
        if component == "parent":
            parent = layout.run_dir.parent
            moved_parent = parent.with_name(f"{parent.name}-moved")
            parent.rename(moved_parent)
            redirect_parent = tmp_path / "redirect-parent"
            redirect_parent.mkdir()
            parent.symlink_to(redirect_parent, target_is_directory=True)
        elif component == "root":
            moved_root = layout.run_dir.with_name("training-1-moved")
            layout.run_dir.rename(moved_root)
            layout.run_dir.mkdir()
        else:
            moved_child = layout.artifacts_dir.with_name("artifacts-moved")
            layout.artifacts_dir.rename(moved_child)
            layout.artifacts_dir.mkdir()

    if phase == "after_open":
        monkeypatch.setattr(
            full_training_run,
            "_after_output_directories_open",
            lambda _layout: swap_named_component(),
            raising=False,
        )
    else:
        monkeypatch.setattr(
            full_training_run,
            "_before_named_layout_revalidation",
            swap_named_component,
            raising=False,
        )

    with pytest.raises(ValueError, match="ownership|symlink|component|unexpected"):
        _publish_tiny_manifest(layout, training_input, receipt)

    assert swapped
    assert list(tmp_path.rglob("training_manifest.json")) == []
    assert not [path for path in tmp_path.rglob("*") if ".tmp" in path.name]
    assert not list(tmp_path.rglob(".terminal.lock"))
