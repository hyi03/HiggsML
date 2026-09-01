from __future__ import annotations

import builtins
import io
import json
from pathlib import Path
import sys
import tempfile
from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest

from scripts import train_full_mc
from src.features import FEATURES
from src.full_training_evaluation import build_working_points, evaluate_full_training
from src.full_training_model import (
    CandidateResult,
    FoldMetric,
    ModelSelectionResult,
    cross_validate_candidates,
    effective_parameters,
    final_tree_count,
    fit_final_model,
)
from src.full_training_plots import PLOT_NAMES, save_full_training_plots
from src.full_training_policy import (
    CandidateSpec,
    TrainingPolicy,
    assign_development_folds,
    development_fold,
    validate_mc_frame,
)
from src.full_training_run import (
    claim_training_output,
    load_training_mc_frame,
    publish_training_manifest,
    resolve_training_input,
    resolve_training_output,
    write_training_artifacts,
)
from src.provenance import sha256_file, software_versions


def _json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")


def _synthetic_task4a_run(tmp_path: Path) -> Path:
    run = tmp_path / "task4a"
    (run / "processed").mkdir(parents=True)
    (run / "artifacts").mkdir()
    config = run / "config.yaml"
    config.write_bytes(b"task: 4a\n")
    pd.DataFrame(
        {
            "eventNumber": [1, 2, 3],
            "channelNumber": [345060, 700600, 700600],
            "label": [1, 0, 0],
            "split": ["train", "validation", "test"],
            "physical_weight": [1.0, 2.0, 3.0],
        }
    ).to_csv(run / "processed/mc_events.csv.gz", index=False)
    _json(
        run / "artifacts/data_summary.json",
        {
            "schema_version": "1.0",
            "data": {},
            "mc": {
                "higgs": {"label": 1, "selected_events": 1},
                "zz": {"label": 0, "selected_events": 2},
            },
        },
    )
    _json(
        run / "artifacts/run_manifest.json",
        {
            "schema_version": "1.1",
            "status": "complete",
            "config": {"sha256": sha256_file(config)},
            "processing": {
                "read_policy": {"mode": "full", "entry_stop": None}
            },
        },
    )
    return run


def _training_frame() -> pd.DataFrame:
    rows = []
    event_number = 100
    for split, events_per_class in (("train", 8), ("validation", 4), ("test", 5)):
        for label in (0, 1):
            for offset in range(events_per_class):
                score_feature = 0.12 + 0.68 * label + 0.01 * offset
                rows.append(
                    {
                        **{feature: score_feature for feature in FEATURES},
                        "m4l": 106.0 + (event_number % 53),
                        "eventNumber": event_number,
                        "channelNumber": 345060 if label else 700600,
                        "split": split,
                        "label": label,
                        "physical_weight": (
                            -0.25 if offset == 0 else 1.0 + 0.1 * offset
                        ),
                    }
                )
                event_number += 1
    return pd.DataFrame(rows)


def test_prediction_audit_keeps_mass_comparison_columns_without_m4l_feature_leakage():
    """Dropping comparison kinematics or training on m4l would invalidate later MC checks."""
    audit = train_full_mc._audit_frame(_training_frame())

    assert list(audit.columns) == [
        "channelNumber",
        "eventNumber",
        "split",
        "label",
        "physical_weight",
        "m4l",
        "mZ1",
        "mZ2",
        "pt4l",
    ]
    assert "m4l" not in FEATURES


def test_scored_frame_routes_default_features_through_model_scorer(monkeypatch):
    """Bypassing score_model would let future CLI scoring drift from the default contract."""
    frame = _training_frame().iloc[:3].copy()
    calls: list[tuple[object, pd.DataFrame, object]] = []

    def fake_score(model, received, *, features=FEATURES):
        calls.append((model, received, features))
        return np.full(len(received), 0.25)

    monkeypatch.setattr(train_full_mc, "score_model", fake_score, raising=False)
    model = object()

    scored = train_full_mc._scored_frame(model, frame)

    assert len(calls) == 1
    assert calls[0][0] is model
    assert calls[0][1] is frame
    assert calls[0][2] is FEATURES
    assert scored["score"].to_numpy() == pytest.approx([0.25, 0.25, 0.25])


def _tiny_xgboost_frame() -> pd.DataFrame:
    rows = []
    next_event = 10_000
    for label in (0, 1):
        per_fold = {fold: 0 for fold in range(5)}
        while min(per_fold.values()) < 10:
            channel = 345060 if label else 700600
            fold = development_fold(channel, next_event)
            if per_fold[fold] < 10:
                replicate = per_fold[fold]
                value = 0.15 + 0.65 * label + 0.005 * replicate
                rows.append(
                    {
                        **{
                            feature: value + 0.0001 * feature_index
                            for feature_index, feature in enumerate(FEATURES)
                        },
                        "m4l": 106.0 + ((fold * 10 + replicate) % 53),
                        "eventNumber": next_event,
                        "channelNumber": channel,
                        "split": "train" if replicate % 2 == 0 else "validation",
                        "label": label,
                        "physical_weight": -0.2 if replicate == 0 else 1.0,
                    }
                )
                per_fold[fold] += 1
            next_event += 1
    for label in (0, 1):
        for replicate in range(10):
            value = 0.15 + 0.65 * label + 0.005 * replicate
            if label == 0 and replicate == 9:
                # Keep one deliberately signal-like test ZZ event so every
                # frozen OOF working point has a non-empty diagnostic subset.
                value = 0.90
            rows.append(
                {
                    **{
                        feature: value + 0.0001 * feature_index
                        for feature_index, feature in enumerate(FEATURES)
                    },
                    "m4l": 106.0 + replicate * 5,
                    "eventNumber": next_event,
                    "channelNumber": 345060 if label else 700600,
                    "split": "test",
                    "label": label,
                    "physical_weight": -0.2 if replicate == 0 else 1.0,
                }
            )
            next_event += 1
    return pd.DataFrame(rows)


def _tiny_test_policy() -> TrainingPolicy:
    return TrainingPolicy(
        folds=5,
        random_seed=7,
        n_jobs=1,
        common_parameters=MappingProxyType(
            {
                "n_estimators": 12,
                "learning_rate": 0.2,
                "subsample": 1.0,
                "colsample_bytree": 1.0,
                "reg_alpha": 0.0,
                "reg_lambda": 1.0,
                "objective": "binary:logistic",
                "eval_metric": "auc",
                "early_stopping_rounds": 3,
                "tree_method": "hist",
            }
        ),
        candidates=tuple(
            CandidateSpec(f"depth{depth}_child{child}", depth, float(child))
            for depth in (2, 3, 4)
            for child in (20, 5)
        ),
        working_points=MappingProxyType(
            {"loose": 0.50, "medium": 0.20, "tight": 0.10}
        ),
        auc_gap_limit=0.05,
        ks_distance_limit=0.10,
        mass_bins_gev=tuple(float(value) for value in range(105, 165, 5)),
    )


def _assert_finite_json(value: object) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _assert_finite_json(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_finite_json(nested)
    elif isinstance(value, float):
        assert np.isfinite(value)
    else:
        assert value is not None


def _training_task4a_run(tmp_path: Path, frame: pd.DataFrame) -> Path:
    run = tmp_path / "training-task4a"
    (run / "processed").mkdir(parents=True)
    (run / "artifacts").mkdir()
    config = run / "config.yaml"
    config.write_bytes(b"task: 4a-full\n")
    frame.to_csv(run / "processed/mc_events.csv.gz", index=False)
    _json(
        run / "artifacts/data_summary.json",
        {
            "schema_version": "1.0",
            "data": {},
            "mc": {
                "higgs": {
                    "label": 1,
                    "selected_events": int((frame["label"] == 1).sum()),
                },
                "zz": {
                    "label": 0,
                    "selected_events": int((frame["label"] == 0).sum()),
                },
            },
        },
    )
    _json(
        run / "artifacts/run_manifest.json",
        {
            "schema_version": "1.1",
            "status": "complete",
            "config": {"sha256": sha256_file(config)},
            "processing": {
                "read_policy": {"mode": "full", "entry_stop": None}
            },
        },
    )
    return run


def _fake_selection(frame: pd.DataFrame, policy) -> ModelSelectionResult:
    candidates = tuple(
        CandidateResult(
            candidate=candidate,
            folds=tuple(
                FoldMetric(
                    fold=fold,
                    weighted_auc=0.80 + 0.001 * fold,
                    unweighted_auc=0.81 + 0.001 * fold,
                    best_iteration=2 + fold,
                )
                for fold in range(policy.folds)
            ),
            mean_weighted_auc=0.802,
            standard_error_weighted_auc=0.001,
        )
        for candidate in policy.candidates
    )
    development = frame.index[frame["split"] != "test"]
    scores = frame.loc[development, FEATURES[0]].astype(float).rename("oof_score")
    folds = pd.Series(
        np.arange(len(development)) % policy.folds,
        index=development,
        name="development_fold",
    )
    return ModelSelectionResult(candidates[0], candidates, scores, folds)


def test_weight_summary_reports_no_identifier_collisions():
    frame = _training_frame()

    summary = train_full_mc._weight_summary(frame)

    assert summary["identity_collisions"] == {
        "unique_pairs": len(frame),
        "duplicate_pair_groups": 0,
        "rows_in_duplicate_pair_groups": 0,
        "cross_label_groups": 0,
        "cross_split_groups": 0,
    }


def test_weight_summary_reports_safe_identifier_collision_exactly():
    frame = _training_frame()
    duplicate = frame.iloc[[0]].copy()
    duplicate.index = [int(frame.index.max()) + 1]
    collided = pd.concat([frame, duplicate])

    summary = train_full_mc._weight_summary(collided)

    assert summary["identity_collisions"] == {
        "unique_pairs": len(frame),
        "duplicate_pair_groups": 1,
        "rows_in_duplicate_pair_groups": 2,
        "cross_label_groups": 0,
        "cross_split_groups": 0,
    }


class _FakeModel:
    def __init__(self, frame: pd.DataFrame, stages: list[str]) -> None:
        self._splits = frame["split"].to_dict()
        self._stages = stages
        self.feature_importances_ = np.full(len(FEATURES), 1.0 / len(FEATURES))

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        splits = {self._splits[index] for index in features.index}
        stage = "test" if splits == {"test"} else "final_development"
        self._stages.append(f"score:{stage}")
        scores = np.clip(features[FEATURES[0]].to_numpy(dtype=float), 0.01, 0.99)
        return np.column_stack([1.0 - scores, scores])

    def save_raw(self, *, raw_format: str) -> bytes:
        assert raw_format == "json"
        return b'{"model":"synthetic-fake"}'


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--input-run", "input", "--config", "config"],
        ["--input-run", "input", "--run-dir", "output"],
        ["--config", "config", "--run-dir", "output"],
    ],
)
def test_cli_requires_all_isolated_training_arguments(argv):
    with pytest.raises(SystemExit) as raised:
        train_full_mc.main(argv)

    assert raised.value.code == 2


def test_main_rejects_alternate_policy_factory_keyword():
    with pytest.raises(TypeError, match="_policy_factory"):
        train_full_mc.main([], _policy_factory=lambda path: _tiny_test_policy())


def test_invalid_frozen_config_fails_before_input_resolution_fit_or_claim(
    tmp_path, monkeypatch
):
    invalid_config = tmp_path / "invalid.yaml"
    invalid_config.write_text("schema_version: '1.0'\n", encoding="utf-8")
    output = tmp_path / "task4b"
    calls: list[str] = []
    monkeypatch.setattr(
        train_full_mc,
        "resolve_training_input",
        lambda path: calls.append("input") or (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(
        train_full_mc,
        "cross_validate_candidates",
        lambda *args, **kwargs: calls.append("fit") or (_ for _ in ()).throw(AssertionError()),
    )

    with pytest.raises(ValueError):
        train_full_mc.main(
            [
                "--input-run",
                str(tmp_path / "unused"),
                "--config",
                str(invalid_config),
                "--run-dir",
                str(output),
            ]
        )

    assert calls == []
    assert not output.exists()


def test_invalid_task4a_input_fails_before_fit_or_claim(tmp_path, monkeypatch):
    input_run = _synthetic_task4a_run(tmp_path)
    (input_run / "artifacts/run_manifest.json").unlink()
    output = tmp_path / "task4b"
    fits: list[str] = []
    monkeypatch.setattr(
        train_full_mc,
        "cross_validate_candidates",
        lambda *args, **kwargs: fits.append("fit") or (_ for _ in ()).throw(AssertionError()),
    )

    with pytest.raises(FileNotFoundError, match="Task 4A input"):
        train_full_mc.main(
            [
                "--input-run",
                str(input_run),
                "--config",
                "config/full_training.yaml",
                "--run-dir",
                str(output),
            ]
        )

    assert fits == []
    assert not output.exists()


@pytest.mark.parametrize("output_kind", ["directory", "dangling_symlink"])
def test_existing_or_dangling_output_fails_before_input_resolution_or_fit(
    tmp_path, monkeypatch, output_kind
):
    input_run = _synthetic_task4a_run(tmp_path)
    output = tmp_path / "task4b"
    if output_kind == "directory":
        output.mkdir()
        (output / "owned.txt").write_bytes(b"preserve-existing-output")
    else:
        output.symlink_to(tmp_path / "missing-target")
    before = (
        output.lstat().st_mode,
        output.lstat().st_size,
        output.lstat().st_mtime_ns,
        output.readlink() if output.is_symlink() else None,
        sorted(path.name for path in output.iterdir()) if output.is_dir() else None,
        (output / "owned.txt").read_bytes() if output.is_dir() else None,
    )
    calls: list[str] = []
    monkeypatch.setattr(
        train_full_mc,
        "resolve_training_input",
        lambda path: calls.append("resolve_input")
        or (_ for _ in ()).throw(
            AssertionError("resolve_training_input must not be called")
        ),
    )
    monkeypatch.setattr(
        train_full_mc,
        "load_training_mc_frame",
        lambda *args, **kwargs: calls.append("read")
        or (_ for _ in ()).throw(AssertionError("MC table must not be read")),
    )
    monkeypatch.setattr(
        train_full_mc,
        "cross_validate_candidates",
        lambda *args, **kwargs: calls.append("fit")
        or (_ for _ in ()).throw(AssertionError("fitting must not start")),
    )

    with pytest.raises(FileExistsError, match="already exists"):
        train_full_mc.main(
            [
                "--input-run",
                str(input_run),
                "--config",
                "config/full_training.yaml",
                "--run-dir",
                str(output),
            ]
        )

    after = (
        output.lstat().st_mode,
        output.lstat().st_size,
        output.lstat().st_mtime_ns,
        output.readlink() if output.is_symlink() else None,
        sorted(path.name for path in output.iterdir()) if output.is_dir() else None,
        (output / "owned.txt").read_bytes() if output.is_dir() else None,
    )
    assert calls == []
    assert after == before


def test_cli_reads_only_mc_once_and_preserves_sealed_stage_order(
    tmp_path, monkeypatch, capsys
):
    frame = _training_frame()
    input_run = _training_task4a_run(tmp_path, frame)
    output = tmp_path / "task4b"
    opened_paths: list[Path] = []
    filesystem_mc_reads: list[Path] = []
    stages: list[str] = []
    scratch_directories: list[Path] = []
    original_read_csv = pd.read_csv
    original_read_bytes = Path.read_bytes
    original_resolve_input = train_full_mc.resolve_training_input
    original_build_working_points = build_working_points
    original_evaluate = evaluate_full_training
    original_final_tree_count = train_full_mc.final_tree_count
    original_effective_parameters = train_full_mc.effective_parameters
    original_input_recheck = train_full_mc.assert_input_hashes_unchanged
    original_summary_text = train_full_mc._summary_text
    original_display_summary = train_full_mc._display_summary
    loader_armed = False

    def resolving_then_arm(path):
        nonlocal loader_armed
        resolved = original_resolve_input(path)
        loader_armed = True
        return resolved

    def recording_read_bytes(path):
        if loader_armed and path == input_run / "processed/mc_events.csv.gz":
            filesystem_mc_reads.append(path)
        return original_read_bytes(path)

    def recording_read_csv(source, *args, **kwargs):
        if isinstance(source, (str, Path)):
            opened_paths.append(Path(source))
        return original_read_csv(source, *args, **kwargs)

    def fake_cross_validate(received: pd.DataFrame, policy):
        stages.append("cross_validate")
        assert -1 not in set(received["label"])
        assert policy.folds == 5
        assert policy.random_seed == 42
        assert policy.n_jobs == 4
        assert policy.common_parameters["n_estimators"] == 1000
        assert [candidate.name for candidate in policy.candidates] == [
            "depth2_child20",
            "depth2_child5",
            "depth3_child20",
            "depth3_child5",
            "depth4_child20",
            "depth4_child5",
        ]
        return _fake_selection(received, policy)

    def recording_working_points(oof: pd.DataFrame, targets):
        stages.append("working_points")
        assert -1 not in set(oof["label"])
        return original_build_working_points(oof, targets)

    def recording_tree_count(selected):
        stages.append("final_tree_count")
        return original_final_tree_count(selected)

    def recording_effective_parameters(selection, policy, **kwargs):
        stages.append("effective_parameters")
        return original_effective_parameters(selection, policy, **kwargs)

    def fake_final_fit(received: pd.DataFrame, selection, policy):
        stages.append("final_fit")
        assert -1 not in set(received["label"])
        assert "test" in set(received["split"])
        return _FakeModel(received, stages)

    def recording_evaluate(oof, final_development, test, points, policy, **kwargs):
        stages.append("evaluate")
        for received in (oof, final_development, test):
            assert -1 not in set(received["label"])
        assert kwargs["selection"]["candidate"].startswith("depth")
        assert kwargs["selection"]["final_tree_count"] == 5
        return original_evaluate(
            oof,
            final_development,
            test,
            points,
            policy,
            **kwargs,
        )

    def fake_plots(oof, test, cv_results, model, points, policy, output_dir):
        stages.append("plots")
        assert -1 not in set(oof["label"])
        assert -1 not in set(test["label"])
        scratch = Path(output_dir)
        scratch_directories.append(scratch)
        scratch.mkdir(parents=True, exist_ok=True)
        for name in PLOT_NAMES:
            (scratch / name).write_bytes(f"synthetic-{name}".encode())

    original_write = train_full_mc.write_training_artifacts
    original_publish = train_full_mc.publish_training_manifest

    def recording_write(*args, **kwargs):
        stages.append("write_artifacts")
        return original_write(*args, **kwargs)

    def recording_publish(*args, **kwargs):
        stages.append("publish_manifest")
        return original_publish(*args, **kwargs)

    def recording_input_recheck(training_input):
        stages.append("input_recheck")
        return original_input_recheck(training_input)

    def recording_summary_text(**kwargs):
        stages.append("format_summary")
        return original_summary_text(**kwargs)

    def recording_display_summary(summary):
        stages.append("display_summary")
        return original_display_summary(summary)

    monkeypatch.setattr(pd, "read_csv", recording_read_csv)
    monkeypatch.setattr(Path, "read_bytes", recording_read_bytes)
    monkeypatch.setattr(
        train_full_mc, "resolve_training_input", resolving_then_arm
    )
    monkeypatch.setattr(train_full_mc, "cross_validate_candidates", fake_cross_validate)
    monkeypatch.setattr(train_full_mc, "final_tree_count", recording_tree_count)
    monkeypatch.setattr(train_full_mc, "build_working_points", recording_working_points)
    monkeypatch.setattr(
        train_full_mc, "effective_parameters", recording_effective_parameters
    )
    monkeypatch.setattr(train_full_mc, "fit_final_model", fake_final_fit)
    monkeypatch.setattr(train_full_mc, "evaluate_full_training", recording_evaluate)
    monkeypatch.setattr(train_full_mc, "save_full_training_plots", fake_plots)
    monkeypatch.setattr(train_full_mc, "write_training_artifacts", recording_write)
    monkeypatch.setattr(
        train_full_mc, "assert_input_hashes_unchanged", recording_input_recheck
    )
    monkeypatch.setattr(train_full_mc, "_summary_text", recording_summary_text)
    monkeypatch.setattr(
        train_full_mc, "_display_summary", recording_display_summary
    )
    monkeypatch.setattr(train_full_mc, "publish_training_manifest", recording_publish)

    train_full_mc.main(
        [
            "--input-run",
            str(input_run),
            "--config",
            "config/full_training.yaml",
            "--run-dir",
            str(output),
        ]
    )

    assert filesystem_mc_reads == [input_run / "processed/mc_events.csv.gz"]
    assert opened_paths == []
    assert not any("data_events" in str(path) for path in opened_paths)
    assert stages == [
        "cross_validate",
        "final_tree_count",
        "working_points",
        "effective_parameters",
        "final_fit",
        "score:final_development",
        "score:test",
        "evaluate",
        "plots",
        "write_artifacts",
        "input_recheck",
        "format_summary",
        "publish_manifest",
        "display_summary",
    ]
    assert scratch_directories and not scratch_directories[0].exists()
    assert (output / "artifacts/training_manifest.json").exists()
    stdout = capsys.readouterr().out
    for value in (
        "selected candidate",
        "final tree count",
        "OOF AUC",
        "test AUC",
        "loose threshold",
        "medium threshold",
        "tight threshold",
        "warning",
        str(output.resolve()),
    ):
        assert value in stdout


def test_cli_rejects_swap_restored_mc_bytes_before_any_fit(tmp_path, monkeypatch):
    frame = _training_frame()
    input_run = _training_task4a_run(tmp_path, frame)
    mc_path = input_run / "processed/mc_events.csv.gz"
    original_bytes = mc_path.read_bytes()
    alternate = frame.copy()
    alternate.loc[:, FEATURES] += 0.05
    alternate_path = tmp_path / "alternate-mc.csv.gz"
    alternate.to_csv(alternate_path, index=False)
    alternate_bytes = alternate_path.read_bytes()
    output = tmp_path / "swapped-task4b"
    original_resolve_input = train_full_mc.resolve_training_input
    original_read_bytes = Path.read_bytes
    original_read_csv = pd.read_csv
    armed = False
    fit_frames: list[pd.DataFrame] = []

    def resolving_then_arm(path):
        nonlocal armed
        resolved = original_resolve_input(path)
        armed = True
        return resolved

    def swapped_read_bytes(path):
        if not armed or path != mc_path:
            return original_read_bytes(path)
        path.write_bytes(alternate_bytes)
        try:
            return original_read_bytes(path)
        finally:
            path.write_bytes(original_bytes)

    def swapped_path_read_csv(source, *args, **kwargs):
        if not armed or not isinstance(source, (str, Path)) or Path(source) != mc_path:
            return original_read_csv(source, *args, **kwargs)
        mc_path.write_bytes(alternate_bytes)
        try:
            return original_read_csv(source, *args, **kwargs)
        finally:
            mc_path.write_bytes(original_bytes)

    def forbid_fit(received, policy):
        fit_frames.append(received.copy())
        raise AssertionError("swap-restored MC reached fitting")

    monkeypatch.setattr(
        train_full_mc, "resolve_training_input", resolving_then_arm
    )
    monkeypatch.setattr(Path, "read_bytes", swapped_read_bytes)
    monkeypatch.setattr(pd, "read_csv", swapped_path_read_csv)
    monkeypatch.setattr(train_full_mc, "cross_validate_candidates", forbid_fit)

    with pytest.raises(RuntimeError, match="Task 4A input changed during training"):
        train_full_mc.main(
            [
                "--input-run",
                str(input_run),
                "--config",
                "config/full_training.yaml",
                "--run-dir",
                str(output),
            ]
        )

    assert fit_frames == []
    assert original_read_bytes(mc_path) == original_bytes
    assert not (output / "artifacts/training_manifest.json").exists()
    assert json.loads((output / "failure.json").read_text())["status"] == "failed"


def test_claimed_run_failure_is_terminal_and_reraises_original_error(
    tmp_path, monkeypatch
):
    frame = _training_frame()
    input_run = _training_task4a_run(tmp_path, frame)
    output = tmp_path / "failed-task4b"
    original = RuntimeError("synthetic CV failure")

    def fail_cross_validation(received, policy):
        raise original

    monkeypatch.setattr(
        train_full_mc, "cross_validate_candidates", fail_cross_validation
    )

    with pytest.raises(RuntimeError) as raised:
        train_full_mc.main(
            [
                "--input-run",
                str(input_run),
                "--config",
                "config/full_training.yaml",
                "--run-dir",
                str(output),
            ]
        )

    assert raised.value is original
    assert not (output / "artifacts/training_manifest.json").exists()
    assert json.loads((output / "failure.json").read_text()) == {
        "status": "failed",
        "error_type": "RuntimeError",
        "message": "synthetic CV failure",
    }


def test_post_publication_broken_stdout_is_non_terminal(tmp_path, monkeypatch):
    frame = _training_frame()
    input_run = _training_task4a_run(tmp_path, frame)
    output = tmp_path / "broken-stdout-task4b"

    monkeypatch.setattr(
        train_full_mc,
        "cross_validate_candidates",
        lambda received, policy: _fake_selection(received, policy),
    )
    monkeypatch.setattr(
        train_full_mc,
        "fit_final_model",
        lambda received, selection, policy: _FakeModel(received, []),
    )

    def fake_plots(oof, test, cv_results, model, points, policy, output_dir):
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        for name in PLOT_NAMES:
            (destination / name).write_bytes(name.encode())

    def broken_print(*args, **kwargs):
        raise BrokenPipeError("stdout closed")

    monkeypatch.setattr(train_full_mc, "save_full_training_plots", fake_plots)
    monkeypatch.setattr(builtins, "print", broken_print)

    train_full_mc.main(
        [
            "--input-run",
            str(input_run),
            "--config",
            "config/full_training.yaml",
            "--run-dir",
            str(output),
        ]
    )

    manifest = json.loads(
        (output / "artifacts/training_manifest.json").read_text()
    )
    assert manifest["status"] == "complete"
    assert not (output / "failure.json").exists()


def test_post_publication_closed_stdout_value_error_is_non_terminal(
    tmp_path, monkeypatch
):
    frame = _training_frame()
    input_run = _training_task4a_run(tmp_path, frame)
    output = tmp_path / "closed-stdout-task4b"
    closed_stdout = io.StringIO()
    original_publish = train_full_mc.publish_training_manifest

    monkeypatch.setattr(
        train_full_mc,
        "cross_validate_candidates",
        lambda received, policy: _fake_selection(received, policy),
    )
    monkeypatch.setattr(
        train_full_mc,
        "fit_final_model",
        lambda received, selection, policy: _FakeModel(received, []),
    )

    def fake_plots(oof, test, cv_results, model, points, policy, output_dir):
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        for name in PLOT_NAMES:
            (destination / name).write_bytes(name.encode())

    def publish_then_close_stdout(*args, **kwargs):
        result = original_publish(*args, **kwargs)
        closed_stdout.close()
        monkeypatch.setattr(sys, "stdout", closed_stdout)
        return result

    monkeypatch.setattr(train_full_mc, "save_full_training_plots", fake_plots)
    monkeypatch.setattr(
        train_full_mc, "publish_training_manifest", publish_then_close_stdout
    )

    train_full_mc.main(
        [
            "--input-run",
            str(input_run),
            "--config",
            "config/full_training.yaml",
            "--run-dir",
            str(output),
        ]
    )

    manifest = json.loads(
        (output / "artifacts/training_manifest.json").read_text()
    )
    assert manifest["status"] == "complete"
    assert not (output / "failure.json").exists()


@pytest.mark.parametrize(
    "terminal_error",
    [KeyboardInterrupt("interrupt"), SystemExit(7)],
    ids=["KeyboardInterrupt", "SystemExit"],
)
def test_display_summary_propagates_terminal_control_exceptions(
    monkeypatch, terminal_error
):
    def terminal_print(*args, **kwargs):
        raise terminal_error

    monkeypatch.setattr(builtins, "print", terminal_print)

    with pytest.raises(type(terminal_error)) as raised:
        train_full_mc._display_summary("completed summary")

    assert raised.value is terminal_error


def test_true_tiny_xgboost_end_to_end_composes_six_candidate_public_tasks(tmp_path):
    pytest.importorskip("xgboost")
    frame = _tiny_xgboost_frame()
    development_folds = assign_development_folds(frame)
    development = frame.loc[development_folds.index].assign(
        development_fold=development_folds
    )
    assert (
        development.groupby(["label", "development_fold"]).size().min() >= 10
    )
    assert frame.loc[frame["split"] == "test"].groupby("label").size().min() >= 10
    input_run = _training_task4a_run(tmp_path, frame)
    output = tmp_path / "tiny-xgboost-task4b"
    policy = _tiny_test_policy()
    training_input = resolve_training_input(input_run)
    layout = claim_training_output(
        resolve_training_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            input_run=input_run,
            run_dir=output,
        )
    )
    loaded = load_training_mc_frame(training_input)
    validate_mc_frame(loaded)
    selection = cross_validate_candidates(loaded, policy)
    selected_tree_count = final_tree_count(selection.selected)
    audit_columns = [
        "channelNumber",
        "eventNumber",
        "split",
        "label",
        "physical_weight",
        "m4l",
        "mZ1",
        "mZ2",
        "pt4l",
    ]
    oof = loaded.loc[selection.oof_scores.index, audit_columns].copy()
    oof["development_fold"] = selection.development_folds.loc[oof.index]
    oof["oof_score"] = selection.oof_scores.loc[oof.index]
    points = build_working_points(oof, policy.working_points)
    parameters = effective_parameters(selection, policy, final=True)
    model = fit_final_model(loaded, selection, policy)

    development_rows = loaded.loc[loaded["split"] != "test"]
    final_development = development_rows.loc[:, audit_columns].copy()
    final_development["score"] = model.predict_proba(
        development_rows.loc[:, FEATURES]
    )[:, 1]
    test_rows = loaded.loc[loaded["split"] == "test"]
    test = test_rows.loc[:, audit_columns].copy()
    test["score"] = model.predict_proba(test_rows.loc[:, FEATURES])[:, 1]
    selection_metadata = {
        "candidate": selection.selected.candidate.name,
        "final_tree_count": selected_tree_count,
    }
    metrics = evaluate_full_training(
        oof,
        final_development,
        test,
        points,
        policy,
        selection=selection_metadata,
    )
    with tempfile.TemporaryDirectory(dir=tmp_path) as scratch:
        save_full_training_plots(
            oof,
            test,
            selection.candidates,
            model,
            points,
            policy,
            scratch,
        )
        plot_artifacts = {
            name: (Path(scratch) / name).read_bytes() for name in PLOT_NAMES
        }
    config_source = Path("config/full_training.yaml")
    config_bytes = config_source.read_bytes()
    receipt = write_training_artifacts(
        layout,
        config_source=config_source,
        config_bytes=config_bytes,
        model=model.get_booster(),
        json_artifacts={
            "weight_summary.json": train_full_mc._weight_summary(loaded),
            "metrics.json": metrics,
            "working_points.json": points,
        },
        artifact_tables={
            "cv_results.csv": train_full_mc._cv_table(selection.candidates)
        },
        prediction_frames={
            "oof_scores.csv.gz": oof,
            "test_scores.csv.gz": test,
        },
        plot_artifacts=plot_artifacts,
    )
    manifest = publish_training_manifest(
        layout,
        training_input,
        receipt=receipt,
        software=software_versions(),
        effective_parameters=parameters,
        features=FEATURES,
        sampling_fractions={"higgs": 1.0, "zz": 1.0},
        weight_policy={"training": "class-balanced absolute physical weight"},
        fold_policy={"folds": 5, "assignment": "event hash"},
        selected_model=selection_metadata,
        working_points=points,
        warnings=train_full_mc._warnings(metrics),
    )

    model_payload = json.loads((output / "model/xgboost_model.json").read_text())
    assert isinstance(model_payload, dict)
    metrics = json.loads((output / "artifacts/metrics.json").read_text())
    points = json.loads((output / "artifacts/working_points.json").read_text())
    manifest_payload = json.loads(
        (output / "artifacts/training_manifest.json").read_text()
    )
    for payload in (metrics, points, manifest_payload):
        _assert_finite_json(payload)
    cv_results = pd.read_csv(output / "artifacts/cv_results.csv")
    oof = pd.read_csv(output / "predictions/oof_scores.csv.gz")
    test = pd.read_csv(output / "predictions/test_scores.csv.gz")
    assert len(cv_results) == 6 * 5
    assert len(oof) == 2 * 5 * 10
    assert len(test) == 2 * 10
    for table in (cv_results, oof, test):
        assert np.isfinite(
            table.select_dtypes(include=[np.number]).to_numpy(dtype=float)
        ).all()
    assert cv_results["best_iteration"].between(0, 11).all()
    assert cv_results["best_iteration"].max() < (
        int(policy.common_parameters["n_estimators"]) - 1
    )
    assert manifest == manifest_payload
    assert manifest_payload["status"] == "complete"
    assert manifest_payload["selected_model"]["effective_parameters"][
        "n_estimators"
    ] >= 1
    for name in PLOT_NAMES:
        assert (output / "plots" / name).stat().st_size > 0
