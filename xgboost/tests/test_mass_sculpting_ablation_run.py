from __future__ import annotations

import json
import gzip
import hashlib
from pathlib import Path

import pandas as pd
import yaml

import pytest

from src.mass_sculpting_ablation_run import (
    StudySource,
    approved_ablation_artifacts,
    claim_ablation_output,
    load_ablation_config,
    publish_ablation_manifest,
    record_ablation_failure,
    resolve_ablation_sources,
    resolve_ablation_output,
    write_ablation_artifacts,
)
from src.external_zz_run import _TRAINING_OUTPUT_NAMES
from src.features import FEATURES


@pytest.mark.parametrize("entry_kind", ["directory", "file", "symlink"])
def test_existing_output_is_refused_before_input_load(tmp_path, entry_kind):
    target = tmp_path / "study"
    if entry_kind == "directory":
        target.mkdir()
    elif entry_kind == "file":
        target.write_text("occupied")
    else:
        target.symlink_to(tmp_path / "missing")
    with pytest.raises(FileExistsError):
        resolve_ablation_output(project_root=tmp_path, working_directory=tmp_path, input_run=tmp_path / "input", run_dir=target)


def test_conditional_allowlists_are_exact():
    assert approved_ablation_artifacts(selected=False) == {
        "artifacts/profile_results.csv", "artifacts/selection.json", "plots/oof_profile_tradeoff.png",
    }


def test_output_inside_immutable_reference_run_is_refused(tmp_path):
    reference = tmp_path / "reference"
    reference.mkdir()
    with pytest.raises(ValueError, match="reference training run"):
        resolve_ablation_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            input_run=tmp_path / "input",
            reference_run=reference,
            run_dir=reference / "nested-study",
        )
    assert approved_ablation_artifacts(selected=True) == {
        "artifacts/profile_results.csv", "artifacts/selection.json", "plots/oof_profile_tradeoff.png",
        "artifacts/test_metrics.json", "model/xgboost_model.json",
        "predictions/selected_oof_scores.csv.gz", "predictions/test_scores.csv.gz",
        "plots/selected_mass_sculpting.png",
    }


def test_manifest_is_last_and_failure_is_terminal(tmp_path):
    layout = claim_ablation_output(_fresh_layout(tmp_path))
    with pytest.raises(FileNotFoundError):
        publish_ablation_manifest(
            layout,
            receipt=object(),
            sources={},
            source_row_counts=_rows(),
            decision={"status": "no_eligible_profile"},
            software={},
        )
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_publisher_rejects_nonfinite_payload_before_completion(tmp_path):
    layout = claim_ablation_output(_fresh_layout(tmp_path))
    with pytest.raises(ValueError):
        write_ablation_artifacts(
            layout,
            config_source=_config(tmp_path),
            config_bytes=_config(tmp_path).read_bytes(),
            profile_results=pd.DataFrame({"weighted_auc": [float("inf")]}),
            selection={"status": "no_eligible_profile"},
            plot_artifacts={"oof_profile_tradeoff.png": b"\x89PNG\r\n\x1a\nplot"},
        )
    assert (layout.run_dir / "failure.json").exists()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_claim_is_atomic_and_writer_refuses_preexisting_entries(tmp_path):
    layout = _fresh_layout(tmp_path)
    claimed = claim_ablation_output(layout)
    assert set(path.name for path in claimed.run_dir.iterdir()) == {
        "artifacts", "model", "plots", "predictions"
    }
    with pytest.raises(FileExistsError):
        claim_ablation_output(layout)

    (claimed.artifacts_dir / "profile_results.csv").symlink_to(tmp_path / "outside")
    with pytest.raises(FileExistsError):
        write_ablation_artifacts(
            claimed,
            config_source=_config(tmp_path),
            config_bytes=_config(tmp_path).read_bytes(),
            profile_results=pd.DataFrame({"profile": ["shape8"], "weighted_auc": [0.81]}),
            selection={"status": "no_eligible_profile"},
            plot_artifacts={"oof_profile_tradeoff.png": b"\x89PNG\r\n\x1a\nplot"},
        )
    assert not (tmp_path / "outside").exists()


def test_complete_no_eligible_manifest_hashes_outputs_and_is_last(tmp_path):
    config_path = _config(tmp_path)
    source_path = tmp_path / "source.json"
    source_path.write_text('{"status":"complete"}\n')
    sources = _sources(source_path)
    layout = claim_ablation_output(_fresh_layout(tmp_path))
    receipt = write_ablation_artifacts(
        layout,
        config_source=config_path,
        config_bytes=config_path.read_bytes(),
        profile_results=pd.DataFrame({
            "profile": ["shape8"], "weighted_auc": [0.81], "maximum_ks": [0.08]
        }),
        selection={"status": "no_eligible_profile", "selected_profile": None},
        plot_artifacts={"oof_profile_tradeoff.png": b"\x89PNG\r\n\x1a\nplot"},
    )
    manifest = publish_ablation_manifest(
        layout,
        receipt=receipt,
        sources=sources,
        source_row_counts={
            "row_count": 3,
            "rows_by_split": {"train": 1, "validation": 1, "test": 1},
        },
        decision={"status": "no_eligible_profile", "selected_profile": None},
        software={"python": "test"},
    )
    manifest_path = layout.artifacts_dir / "study_manifest.json"
    assert json.loads(manifest_path.read_text()) == manifest
    assert set(manifest["outputs"]) == {
        "config.yaml",
        "artifacts/profile_results.csv",
        "artifacts/selection.json",
        "plots/oof_profile_tradeoff.png",
    }
    assert manifest["outputs"]["artifacts/profile_results.csv"]["row_count"] == 1
    assert manifest["sources"]["task4a_mc"]["row_count"] == 3
    assert manifest["sources"]["task4a_mc"]["rows_by_split"] == {
        "train": 1, "validation": 1, "test": 1
    }
    assert manifest_path.stat().st_mtime_ns >= max(
        path.stat().st_mtime_ns
        for path in layout.run_dir.rglob("*")
        if path.is_file() and path != manifest_path
    )
    assert not (layout.run_dir / "failure.json").exists()


def test_selected_contract_publishes_exact_conditional_artifacts(tmp_path):
    config_path = _config(tmp_path)
    source_path = tmp_path / "source.json"
    source_path.write_text('{"status":"complete"}\n')
    layout = claim_ablation_output(_fresh_layout(tmp_path))
    receipt = write_ablation_artifacts(
        layout,
        config_source=config_path,
        config_bytes=config_path.read_bytes(),
        profile_results=pd.DataFrame({"profile": ["shape8"], "weighted_auc": [0.82]}),
        selection={"status": "successful_simple_mitigation", "selected_profile": "shape8"},
        plot_artifacts={
            "oof_profile_tradeoff.png": b"\x89PNG\r\n\x1a\ntradeoff",
            "selected_mass_sculpting.png": b"\x89PNG\r\n\x1a\nmass",
        },
        model=_FakeModel(),
        test_metrics={"weighted_auc": 0.83, "zz_ks_distances": {"loose": 0.05}},
        selected_oof_scores=pd.DataFrame({"label": [0, 1], "oof_score": [0.2, 0.8]}),
        test_scores=pd.DataFrame({"label": [0, 1], "score": [0.3, 0.7]}),
    )
    manifest = publish_ablation_manifest(
        layout,
        receipt=receipt,
        sources=_sources(source_path),
        source_row_counts=_rows(),
        decision={"status": "successful_simple_mitigation", "selected_profile": "shape8"},
        software={},
    )
    assert set(manifest["outputs"]) == {
        "config.yaml", *approved_ablation_artifacts(selected=True)
    }
    assert manifest["outputs"]["predictions/selected_oof_scores.csv.gz"]["row_count"] == 2
    assert manifest["outputs"]["predictions/test_scores.csv.gz"]["row_count"] == 2
    assert set(path.relative_to(layout.run_dir).as_posix() for path in layout.run_dir.rglob("*") if path.is_file()) == {
        "config.yaml", "artifacts/study_manifest.json", *approved_ablation_artifacts(selected=True)
    }


def test_manifest_refuses_changed_source_and_records_failure(tmp_path):
    config_path = _config(tmp_path)
    source_path = tmp_path / "source.json"
    source_path.write_text("original")
    sources = _sources(source_path)
    layout = claim_ablation_output(_fresh_layout(tmp_path))
    receipt = write_ablation_artifacts(
        layout,
        config_source=config_path,
        config_bytes=config_path.read_bytes(),
        profile_results=pd.DataFrame({"profile": ["shape8"], "weighted_auc": [0.81]}),
        selection={"status": "no_eligible_profile"},
        plot_artifacts={"oof_profile_tradeoff.png": b"\x89PNG\r\n\x1a\nplot"},
    )
    source_path.write_text("changed")
    with pytest.raises(RuntimeError, match="source changed"):
        publish_ablation_manifest(
            layout,
            receipt=receipt,
            sources=sources,
            source_row_counts=_rows(),
            decision={"status": "no_eligible_profile"},
            software={},
        )
    assert (layout.run_dir / "failure.json").exists()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_manifest_rejects_decision_that_contradicts_conditional_artifacts(tmp_path):
    config_path = _config(tmp_path)
    source_path = tmp_path / "source.json"
    source_path.write_text("source")
    layout = claim_ablation_output(_fresh_layout(tmp_path))
    receipt = write_ablation_artifacts(
        layout,
        config_source=config_path,
        config_bytes=config_path.read_bytes(),
        profile_results=pd.DataFrame({"profile": ["shape8"], "weighted_auc": [0.81]}),
        selection={"status": "no_eligible_profile", "selected_profile": None},
        plot_artifacts={"oof_profile_tradeoff.png": b"\x89PNG\r\n\x1a\nplot"},
    )
    with pytest.raises(ValueError, match="decision contradicts"):
        publish_ablation_manifest(
            layout,
            receipt=receipt,
            sources=_sources(source_path),
            source_row_counts=_rows(),
            decision={"status": "successful_simple_mitigation", "selected_profile": "shape8"},
            software={},
        )


def test_failure_record_is_no_clobber_and_prevents_later_writes(tmp_path):
    layout = claim_ablation_output(_fresh_layout(tmp_path))
    record_ablation_failure(layout, RuntimeError("first"))
    first = (layout.run_dir / "failure.json").read_bytes()
    record_ablation_failure(layout, RuntimeError("second"))
    assert (layout.run_dir / "failure.json").read_bytes() == first
    with pytest.raises(RuntimeError, match="failed"):
        write_ablation_artifacts(
            layout,
            config_source=_config(tmp_path),
            config_bytes=_config(tmp_path).read_bytes(),
            profile_results=pd.DataFrame({"profile": ["shape8"]}),
            selection={"status": "no_eligible_profile"},
            plot_artifacts={"oof_profile_tradeoff.png": b"\x89PNG\r\n\x1a\nplot"},
        )


def test_manifest_rejects_incomplete_source_inventory(tmp_path):
    config_path = _config(tmp_path)
    source_path = tmp_path / "source.json"
    source_path.write_text("source")
    layout = claim_ablation_output(_fresh_layout(tmp_path))
    receipt = write_ablation_artifacts(
        layout,
        config_source=config_path,
        config_bytes=config_path.read_bytes(),
        profile_results=pd.DataFrame({"profile": ["shape8"], "weighted_auc": [0.81]}),
        selection={"status": "no_eligible_profile", "selected_profile": None},
        plot_artifacts={"oof_profile_tradeoff.png": b"\x89PNG\r\n\x1a\nplot"},
    )
    with pytest.raises(ValueError, match="source inventory"):
        publish_ablation_manifest(
            layout,
            receipt=receipt,
            sources={"reference_manifest": StudySource.from_path("reference_manifest", source_path)},
            source_row_counts=_rows(),
            decision={"status": "no_eligible_profile", "selected_profile": None},
            software={},
        )


def test_config_exactly_binds_profiles_gates_reference_and_allowlists():
    config = load_ablation_config(Path("config/mass_sculpting_ablation.yaml"))
    assert config.auc_floor == 0.80
    assert config.ks_limit == 0.10
    assert config.reference_run == "runs/full-training-363490-2026-08-11-r2"
    assert tuple(config.profiles) == (
        "drop_top4_mass_proxies", "shape8", "angular_eta7"
    )
    assert set(config.artifacts_no_selection) == approved_ablation_artifacts(selected=False)
    assert set(config.artifacts_selected) == approved_ablation_artifacts(selected=True)


def test_source_resolver_binds_bytes_without_parsing_mc_before_claim(
    tmp_path, monkeypatch
):
    from tests.test_full_training_run import _synthetic_task4a_run

    input_run = _synthetic_task4a_run(tmp_path)
    from src.full_training_run import resolve_training_input

    training_input = resolve_training_input(input_run)
    reference = tmp_path / "reference"
    _synthetic_reference(reference, training_input.hashes)
    input_manifest_hash = _sha(input_run / "artifacts/run_manifest.json")
    reference_manifest_hash = _sha(reference / "artifacts/training_manifest.json")
    config = tmp_path / "ablation.yaml"
    config.write_text(yaml.safe_dump({
        "schema_version": "1.0",
        "input_run": str(input_run.resolve()),
        "input_manifest_sha256": input_manifest_hash,
        "reference_run": str(reference.resolve()),
        "reference_manifest_sha256": reference_manifest_hash,
        "auc_floor": 0.80,
        "ks_limit": 0.10,
        "profiles": {
            "drop_top4_mass_proxies": [
                "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
                "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
            ],
            "shape8": [
                "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta", "pt4l",
                "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
            ],
            "angular_eta7": [
                "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta",
                "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
            ],
        },
        "artifacts_no_selection": sorted(approved_ablation_artifacts(selected=False)),
        "artifacts_selected": sorted(approved_ablation_artifacts(selected=True)),
    }, sort_keys=False))
    monkeypatch.setattr(
        pd,
        "read_csv",
        lambda *args, **kwargs: pytest.fail("MC CSV must not parse before output claim"),
    )
    sources = resolve_ablation_sources(
        input_run=input_run, reference_run=reference, config_path=config
    )
    assert set(sources.records) == {
        "study_config", "task4a_config", "task4a_mc", "task4a_summary",
        "task4a_manifest", "reference_config", "reference_manifest", "reference_model",
        "reference_metrics",
    }
    assert sources.training_input.expected_rows == 3
    assert sources.policy.folds == 5


def _synthetic_reference(reference, task4a_hashes):
    (reference / "model").mkdir(parents=True)
    (reference / "artifacts").mkdir()
    (reference / "predictions").mkdir()
    (reference / "plots").mkdir()
    (reference / "config.yaml").write_bytes(Path("config/full_training.yaml").read_bytes())
    for relative in sorted(_TRAINING_OUTPUT_NAMES - {"config.yaml"}):
        path = reference / relative
        if relative == "model/xgboost_model.json":
            payload = b'{"model":"synthetic"}'
        elif relative.endswith(".csv.gz"):
            payload = gzip.compress(b"label,score\n0,0.1\n", mtime=0)
        elif relative.endswith(".csv"):
            payload = b"candidate,fold\ndepth2_child20,0\n"
        elif relative.endswith(".png"):
            payload = b"\x89PNG\r\n\x1a\nsynthetic"
        elif relative == "artifacts/metrics.json":
            payload = json.dumps({
                "development_oof": {"weighted_auc": 0.88},
                "mass_sculpting": {
                    "oof_zz": {
                        "weighted_score_mass_correlation": -0.6,
                        "working_points": {
                            name: {"inclusive_to_selected_ks_distance": value}
                            for name, value in (("loose", 0.2), ("medium", 0.3), ("tight", 0.4))
                        },
                    }
                },
            }).encode()
        else:
            payload = b"{}\n"
        path.write_bytes(payload)
    outputs = {}
    for relative in sorted(_TRAINING_OUTPUT_NAMES):
        path = reference / relative
        outputs[relative] = {
            "path": str(path), "size_bytes": path.stat().st_size, "sha256": _sha(path)
        }
    manifest = {
        "schema_version": "1.0",
        "status": "complete",
        "features": list(FEATURES),
        "input_task4a": {"hashes": dict(task4a_hashes)},
        "selected_model": {
            "candidate": "depth4_child20", "final_tree_count": 10
        },
        "working_points": {
            name: {
                "threshold": threshold,
                "signal_efficiency": signal,
                "target_background_efficiency": target,
            }
            for name, threshold, signal, target in (
                ("loose", 0.2, 0.9, 0.5),
                ("medium", 0.5, 0.8, 0.2),
                ("tight", 0.8, 0.7, 0.1),
            )
        },
        "outputs": outputs,
    }
    (reference / "artifacts/training_manifest.json").write_text(
        json.dumps(manifest) + "\n"
    )


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _fresh_layout(tmp_path):
    return resolve_ablation_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=tmp_path / "input",
        run_dir=tmp_path / "study",
    )


def _config(tmp_path):
    path = tmp_path / "study-config.yaml"
    if not path.exists():
        path.write_text("schema_version: '1.0'\n")
    return path


class _FakeModel:
    def save_raw(self, *, raw_format):
        assert raw_format == "json"
        return b'{"model":"fake"}'


def _sources(path):
    names = {
        "study_config", "task4a_config", "task4a_mc", "task4a_summary",
        "task4a_manifest", "reference_config", "reference_manifest",
        "reference_model", "reference_metrics",
    }
    return {name: StudySource.from_path(name, path) for name in names}


def _rows():
    return {
        "row_count": 3,
        "rows_by_split": {"train": 1, "validation": 1, "test": 1},
    }
