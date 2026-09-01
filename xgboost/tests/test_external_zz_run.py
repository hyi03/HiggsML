from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from src.features import FEATURES


TRAINING_PLOTS = (
    "roc_curve.png",
    "score_distributions.png",
    "cv_stability.png",
    "feature_importance.png",
    "mc_mass_sculpting.png",
    "mc_mass_signal_background.png",
    "mc_mass_working_points.png",
)

EXTERNAL_OUTPUTS = {
    "config.yaml",
    "artifacts/metrics.json",
    "predictions/external_zz_scores.csv.gz",
    "plots/external_score_comparison.png",
    "plots/external_kinematics_comparison.png",
    "plots/external_mass_comparison.png",
}


def _module():
    assert importlib.util.find_spec("src.external_zz_run") is not None
    return importlib.import_module("src.external_zz_run")


def _record(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    record: dict[str, object] = {
        "path": str(path),
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    if path.suffix == ".csv" or path.name.endswith(".csv.gz"):
        record["row_count"] = len(pd.read_csv(path))
    return record


def synthetic_training_run(tmp_path: Path) -> Path:
    run = tmp_path / "training"
    for directory in ("model", "artifacts", "predictions", "plots"):
        (run / directory).mkdir(parents=True, exist_ok=True)
    (run / "config.yaml").write_bytes(b"training: frozen\n")
    (run / "model/xgboost_model.json").write_bytes(b'{"frozen":"model"}')
    points = {
        "loose": {"threshold": 0.25},
        "medium": {"threshold": 0.65},
        "tight": {"threshold": 0.85},
    }
    for name, payload in (
        ("weight_summary.json", {"rows": 5}),
        ("metrics.json", {"weighted_auc": 0.8}),
        ("working_points.json", points),
    ):
        (run / "artifacts" / name).write_text(
            json.dumps(payload), encoding="utf-8"
        )
    pd.DataFrame({"candidate": ["depth2_child20"]}).to_csv(
        run / "artifacts/cv_results.csv", index=False
    )
    pd.DataFrame({"score": [0.2]}).to_csv(
        run / "predictions/oof_scores.csv.gz", index=False
    )
    pd.DataFrame(
        {
            "channelNumber": [363490, 345060],
            "eventNumber": [10, 11],
            "split": ["test", "test"],
            "label": [0, 1],
            "physical_weight": [1.0, 2.0],
            "m4l": [130.0, 125.0],
            "mZ1": [90.0, 91.0],
            "mZ2": [30.0, 31.0],
            "pt4l": [20.0, 30.0],
            "score": [0.2, 0.8],
        }
    ).to_csv(run / "predictions/test_scores.csv.gz", index=False)
    for name in TRAINING_PLOTS:
        (run / "plots" / name).write_bytes(f"png:{name}".encode())
    relative_paths = (
        "config.yaml",
        "model/xgboost_model.json",
        "artifacts/weight_summary.json",
        "artifacts/metrics.json",
        "artifacts/working_points.json",
        "artifacts/cv_results.csv",
        "predictions/oof_scores.csv.gz",
        "predictions/test_scores.csv.gz",
        *(f"plots/{name}" for name in TRAINING_PLOTS),
    )
    manifest = {
        "schema_version": "1.0",
        "status": "complete",
        "features": FEATURES,
        "working_points": points,
        "outputs": {
            relative: _record(run / relative) for relative in relative_paths
        },
    }
    (run / "artifacts/training_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return run


def fake_config_and_root(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "external.root"
    root.write_bytes(b"synthetic-root-not-opened")
    config = tmp_path / "external.yaml"
    config.write_bytes(b"external: frozen\n")
    return config, root


def test_resolve_external_inputs_validates_full_training_contract_and_snapshots(tmp_path):
    """Missing training outputs or a partial plot set must not define a frozen input."""
    training = synthetic_training_run(tmp_path)
    config, root = fake_config_and_root(tmp_path)

    resolved = _module().resolve_external_zz_inputs(
        training_run=training, config_path=config, external_root=root
    )

    assert set(resolved.hashes) == {
        "training_manifest",
        "model",
        "working_points",
        "test_scores",
        "external_root",
        "config",
    }
    assert set(resolved.snapshots) == {
        "training_manifest",
        "model",
        "working_points",
        "test_scores",
        "config",
    }
    assert resolved.working_points["medium"]["threshold"] == pytest.approx(0.65)
    assert set(resolved.training_test["label"]) == {0, 1}


def test_resolve_external_inputs_rejects_incomplete_seven_plot_contract(tmp_path):
    """Six plots must not be accepted as a complete Task 4 frozen run."""
    training = synthetic_training_run(tmp_path)
    config, root = fake_config_and_root(tmp_path)
    manifest_path = training / "artifacts/training_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["outputs"].pop(f"plots/{TRAINING_PLOTS[-1]}")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="training output contract"):
        _module().resolve_external_zz_inputs(
            training_run=training, config_path=config, external_root=root
        )


def test_resolve_external_inputs_never_reads_development_oof_scores(
    tmp_path, monkeypatch
):
    """External validation may inspect the contract but must never open OOF rows."""
    module = _module()
    training = synthetic_training_run(tmp_path)
    config, root = fake_config_and_root(tmp_path)
    original = module._read_safe_regular

    def reject_development_read(path, name):
        if Path(path).name == "oof_scores.csv.gz":
            raise AssertionError("external resolver opened development OOF scores")
        return original(path, name)

    monkeypatch.setattr(module, "_read_safe_regular", reject_development_read)

    resolved = module.resolve_external_zz_inputs(
        training_run=training, config_path=config, external_root=root
    )

    assert set(resolved.training_test["split"]) == {"test"}


def test_resolve_external_inputs_rejects_complete_training_run_with_failure_marker(
    tmp_path,
):
    """A frozen run cannot be both complete and failed at its root."""
    training = synthetic_training_run(tmp_path)
    config, root = fake_config_and_root(tmp_path)
    (training / "failure.json").write_text(
        json.dumps({"status": "failed", "message": "contradictory"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="training run root contract"):
        _module().resolve_external_zz_inputs(
            training_run=training,
            config_path=config,
            external_root=root,
        )


@pytest.mark.parametrize("kind", ["directory", "file", "dangling_symlink"])
def test_external_output_preflight_refuses_every_existing_entry(tmp_path, kind):
    """An existing or dangling output target must never be reused or followed."""
    target = tmp_path / "runs/external"
    target.parent.mkdir()
    if kind == "directory":
        target.mkdir()
    elif kind == "file":
        target.write_bytes(b"owner")
    else:
        target.symlink_to(tmp_path / "missing")

    with pytest.raises(FileExistsError, match="already exists"):
        _module().resolve_external_zz_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            training_run=tmp_path / "training",
            run_dir=target,
        )


def _publish_fake_run(tmp_path: Path):
    module = _module()
    training = synthetic_training_run(tmp_path)
    config, root = fake_config_and_root(tmp_path)
    inputs = module.resolve_external_zz_inputs(
        training_run=training, config_path=config, external_root=root
    )
    layout = module.claim_external_zz_output(
        module.resolve_external_zz_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            training_run=training,
            run_dir=tmp_path / "runs/external",
        )
    )
    scores = pd.DataFrame(
        {
            "channelNumber": [700600],
            "eventNumber": [20],
            "split": ["test"],
            "label": [0],
            "physical_weight": [1.0],
            "m4l": [135.0],
            "mZ1": [91.0],
            "mZ2": [32.0],
            "pt4l": [28.0],
            "score": [0.3],
        }
    )
    receipt = module.write_external_zz_artifacts(
        layout,
        config_source=config,
        config_bytes=inputs.snapshots["config"],
        metrics={"external_auc": {"weighted_auc": 0.75}},
        scores=scores,
        plots={
            "external_score_comparison.png": b"score",
            "external_kinematics_comparison.png": b"kinematics",
            "external_mass_comparison.png": b"mass",
        },
    )
    return module, inputs, layout, receipt


def test_external_manifest_is_last_and_hashes_every_input_and_output(tmp_path):
    """A complete marker without exact input/output hashes would be unauditable."""
    module, inputs, layout, receipt = _publish_fake_run(tmp_path)
    assert not (layout.run_dir / "manifest.json").exists()

    manifest = module.publish_external_zz_manifest(
        layout, inputs, receipt=receipt, software={"python": "test"}
    )

    assert manifest["schema_version"] == "1.0"
    assert manifest["status"] == "complete"
    assert set(manifest["inputs"]) == set(inputs.hashes)
    assert {
        path.relative_to(layout.run_dir).as_posix()
        for path in layout.run_dir.rglob("*")
        if path.is_file()
    } == EXTERNAL_OUTPUTS | {"manifest.json"}
    assert set(manifest["outputs"]) == EXTERNAL_OUTPUTS
    for name, expected_hash in inputs.hashes.items():
        assert manifest["inputs"][name]["sha256"] == expected_hash
    for relative, record in manifest["outputs"].items():
        path = layout.run_dir / relative
        assert record["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert record["size_bytes"] == path.stat().st_size
    assert json.loads((layout.run_dir / "manifest.json").read_text()) == manifest


def test_external_manifest_rechecks_all_inputs_after_artifact_writes(tmp_path):
    """A changed frozen model must block the final complete manifest."""
    module, inputs, layout, receipt = _publish_fake_run(tmp_path)
    inputs.model_path.write_bytes(b"changed-model")

    with pytest.raises(RuntimeError, match="input changed"):
        module.publish_external_zz_manifest(
            layout, inputs, receipt=receipt, software={}
        )

    assert not (layout.run_dir / "manifest.json").exists()


def test_external_manifest_rechecks_output_hashes_at_final_promotion(
    tmp_path, monkeypatch
):
    """An output changed after hashing must block publication of stale hashes."""
    module, inputs, layout, receipt = _publish_fake_run(tmp_path)
    target = layout.run_dir / "manifest.json"
    metrics = layout.artifacts_dir / "metrics.json"

    def mutate_output_before_final_check(destination):
        if destination == target:
            metrics.write_bytes(b'{"changed":true}')

    monkeypatch.setattr(
        module._safety,
        "_before_no_clobber_promote",
        mutate_output_before_final_check,
    )

    with pytest.raises(RuntimeError, match="output changed"):
        module.publish_external_zz_manifest(
            layout, inputs, receipt=receipt, software={}
        )

    assert not target.exists()


def test_external_manifest_rechecks_exact_layout_before_final_link(
    tmp_path, monkeypatch
):
    """A last-boundary extra file must be rejected before manifest visibility."""
    module, inputs, layout, receipt = _publish_fake_run(tmp_path)
    manifest = layout.run_dir / "manifest.json"

    def insert_unapproved_output(destination):
        if destination == manifest:
            (layout.plots_dir / "unapproved.png").write_bytes(b"unapproved")

    monkeypatch.setattr(
        module._safety,
        "_before_no_clobber_promote",
        insert_unapproved_output,
    )

    with pytest.raises(FileExistsError, match="already exists|missing"):
        module.publish_external_zz_manifest(
            layout, inputs, receipt=receipt, software={}
        )

    assert not manifest.exists()
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


def test_external_manifest_refuses_staged_symlink_substitution_before_visibility(
    tmp_path, monkeypatch
):
    """The ignored staged name must remain the publisher-owned regular file."""
    module, inputs, layout, receipt = _publish_fake_run(tmp_path)
    manifest = layout.run_dir / "manifest.json"
    config_bytes = inputs.config_path.read_bytes()

    def substitute_staged_manifest(destination):
        if destination != manifest:
            return
        staged = [
            path
            for path in layout.run_dir.iterdir()
            if path.name.startswith(".manifest.json.")
            and path.name.endswith(".tmp")
        ]
        assert len(staged) == 1
        staged[0].unlink()
        staged[0].symlink_to(inputs.config_path)

    monkeypatch.setattr(
        module._safety,
        "_before_no_clobber_promote",
        substitute_staged_manifest,
    )

    with pytest.raises(ValueError, match="staged manifest|unsafe|regular"):
        module.publish_external_zz_manifest(
            layout, inputs, receipt=receipt, software={}
        )

    assert not manifest.exists()
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()
    assert inputs.config_path.read_bytes() == config_bytes


def test_external_manifest_refuses_symlink_substitution_at_link_syscall(
    tmp_path, monkeypatch
):
    """Promotion must bind the verified inode, not re-resolve its staged name."""
    module, inputs, layout, receipt = _publish_fake_run(tmp_path)
    manifest = layout.run_dir / "manifest.json"
    config_bytes = inputs.config_path.read_bytes()

    def substitute_after_final_check(destination):
        if destination != manifest:
            return
        staged = [
            path
            for path in layout.run_dir.iterdir()
            if path.name.startswith(".manifest.json.")
            and path.name.endswith(".tmp")
        ]
        assert len(staged) == 1
        staged[0].unlink()
        staged[0].symlink_to(inputs.config_path)

    monkeypatch.setattr(
        module,
        "_before_bound_external_manifest_publish",
        substitute_after_final_check,
        raising=False,
    )

    with pytest.raises(ValueError, match="staged manifest|unsafe|regular"):
        module.publish_external_zz_manifest(
            layout, inputs, receipt=receipt, software={}
        )

    assert not manifest.exists()
    assert not manifest.is_symlink()
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()
    assert inputs.config_path.read_bytes() == config_bytes


def test_external_writer_refuses_existing_fixed_artifact_without_overwrite(tmp_path):
    """A competing file at an approved name must remain byte-for-byte untouched."""
    module = _module()
    training = synthetic_training_run(tmp_path)
    layout = module.claim_external_zz_output(
        module.resolve_external_zz_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            training_run=training,
            run_dir=tmp_path / "runs/external",
        )
    )
    existing = layout.artifacts_dir / "metrics.json"
    existing.write_bytes(b"competing-owner")

    with pytest.raises(FileExistsError, match="already exists"):
        module.write_external_zz_artifacts(
            layout,
            config_source=tmp_path / "unused",
            config_bytes=b"config",
            metrics={},
            scores=pd.DataFrame({"score": [0.1]}),
            plots={
                "external_score_comparison.png": b"score",
                "external_kinematics_comparison.png": b"kinematics",
                "external_mass_comparison.png": b"mass",
            },
        )

    assert existing.read_bytes() == b"competing-owner"


def test_external_writer_failure_is_terminal_and_future_writes_refuse(
    tmp_path
):
    """A claimed run that fails must retain one authoritative terminal failure."""
    module = _module()
    training = synthetic_training_run(tmp_path)
    layout = module.claim_external_zz_output(
        module.resolve_external_zz_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            training_run=training,
            run_dir=tmp_path / "runs/external",
        )
    )
    config = tmp_path / "config.yaml"
    config.write_bytes(b"config")

    with pytest.raises(ValueError, match="plot outputs"):
        module.write_external_zz_artifacts(
            layout,
            config_source=config,
            config_bytes=b"config",
            metrics={},
            scores=pd.DataFrame({"score": [0.1]}),
            plots={},
        )

    assert (layout.run_dir / ".terminal.failed").is_dir()
    failure = json.loads((layout.run_dir / "failure.json").read_text())
    assert failure["status"] == "failed"
    assert failure["error_type"] == "ValueError"

    with pytest.raises(RuntimeError, match="failed external validation run"):
        module.write_external_zz_artifacts(
            layout,
            config_source=config,
            config_bytes=b"config",
            metrics={},
            scores=pd.DataFrame({"score": [0.1]}),
            plots={name: b"plot" for name in module.EXTERNAL_PLOT_NAMES},
        )


def test_record_external_failure_is_no_clobber_and_complete_run_wins(tmp_path):
    """Failure publication is first-writer-wins and cannot contradict completion."""
    module, inputs, layout, receipt = _publish_fake_run(tmp_path)

    module.record_external_zz_failure(layout, RuntimeError("first failure"))
    module.record_external_zz_failure(layout, OSError("later failure"))

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert json.loads((layout.run_dir / "failure.json").read_text())["message"] == (
        "first failure"
    )
    with pytest.raises(RuntimeError, match="failed external validation run"):
        module.publish_external_zz_manifest(
            layout, inputs, receipt=receipt, software={}
        )
