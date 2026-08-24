from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import pickle
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

import src.decorrelation_training_run as training_run


_FEATURES = (
    "lep1_pt",
    "lep2_pt",
    "lep1_eta",
    "lep2_eta",
    "lep3_eta",
    "lep4_eta",
    "pt4l",
    "deltaR_Z1",
    "deltaR_Z2",
    "deltaPhi_ZZ",
)
_ALL_MC_FEATURES = (
    "lep1_pt",
    "lep2_pt",
    "lep3_pt",
    "lep4_pt",
    "lep1_eta",
    "lep2_eta",
    "lep3_eta",
    "lep4_eta",
    "mZ1",
    "mZ2",
    "pt4l",
    "deltaR_Z1",
    "deltaR_Z2",
    "deltaPhi_ZZ",
)
_COMMON_ARTIFACTS = {
    "artifacts/candidate_results.csv",
    "artifacts/working_point_metrics.csv",
    "artifacts/selection.json",
    "predictions/oof_scores.csv.gz",
    "plots/candidate_tradeoff.png",
    "plots/working_point_ks.png",
}
_SELECTED_ARTIFACTS = {
    "artifacts/test_metrics.json",
    "model/flatness_model.pkl",
    "predictions/selected_oof_scores.csv.gz",
    "predictions/test_scores.csv.gz",
    "plots/selected_mass_sculpting.png",
}


@pytest.fixture
def synthetic_task4a_run(tmp_path: Path) -> Path:
    from tests.test_full_training_run import _synthetic_task4a_run

    return _synthetic_task4a_run(tmp_path)


@pytest.fixture
def mc_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    event = 1
    for split in ("train", "validation", "test"):
        for label in (0, 1):
            row: dict[str, object] = {
                "eventNumber": event,
                "channelNumber": 363490 if label == 0 else 345060,
                "split": split,
                "label": label,
                "physical_weight": -0.5 if event % 2 else 1.0,
                "m4l": 105.0 + event,
            }
            row.update(
                {
                    feature: float(event + feature_index / 10)
                    for feature_index, feature in enumerate(_ALL_MC_FEATURES)
                }
            )
            rows.append(row)
            event += 1
    return pd.DataFrame(rows)


@pytest.fixture
def fitted_hep_model():
    from hep_ml.gradientboosting import UGradientBoostingClassifier
    from hep_ml.losses import LogLossFunction

    matrix = _verification_matrix()
    fitting = pd.concat([matrix, matrix + 0.5, matrix + 1.0], ignore_index=True)
    labels = np.asarray([0, 0, 1, 1, 0, 1], dtype=int)
    model = UGradientBoostingClassifier(
        loss=LogLossFunction(),
        n_estimators=2,
        min_samples_leaf=1,
        train_features=list(_FEATURES),
        random_state=42,
    )
    model.fit(fitting, labels)
    return model


def test_production_config_freezes_every_approved_decision():
    config = training_run.load_decorrelation_config(
        Path("config/decorrelation_training_drop_top4.yaml")
    )
    assert config.input_run == "runs/full-baseline-363490-2026-08-11-r2"
    assert config.input_manifest_sha256 == (
        "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8"
    )
    assert config.input_mc_sha256 == (
        "1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e"
    )
    assert config.coefficients == (0.0, 0.5, 1.0, 2.0, 3.0)
    assert config.auc_floor == 0.80
    assert config.ks_limit == 0.10
    assert config.require_signal_efficiency_above_background is True
    assert set(config.artifacts_no_selection) == (
        training_run.approved_decorrelation_artifacts(selected=False)
    )
    assert set(config.artifacts_selected) == (
        training_run.approved_decorrelation_artifacts(selected=True)
    )


def test_config_rejects_changed_coefficient(tmp_path: Path):
    source = Path("config/decorrelation_training_drop_top4.yaml").read_text()
    changed = tmp_path / "changed.yaml"
    changed.write_text(source.replace("  - 3.0\n", "  - 4.0\n"))
    with pytest.raises(ValueError, match="frozen decision"):
        training_run.load_decorrelation_config(changed)


def test_source_inventory_is_explicitly_mc_only(
    tmp_path: Path, synthetic_task4a_run: Path
):
    sources = _resolved_sources(tmp_path, synthetic_task4a_run)

    assert set(sources.records) == {
        "study_config",
        "task4a_config",
        "task4a_mc",
        "task4a_summary",
        "task4a_manifest",
    }
    assert all(
        "data_events" not in str(source.path)
        for source in sources.records.values()
    )
    assert all("periodA" not in str(source.path) for source in sources.records.values())


def test_public_source_resolver_rejects_rebound_config(
    tmp_path: Path, synthetic_task4a_run: Path
):
    with pytest.raises(ValueError, match="frozen decision"):
        training_run.resolve_decorrelation_sources(
            input_run=synthetic_task4a_run,
            config_path=_bound_config(tmp_path, synthetic_task4a_run),
        )


def test_no_source_resolver_bypass_is_exposed():
    assert not hasattr(
        training_run, "_resolve_decorrelation_sources_with_validated_config"
    )


def test_partitions_expose_development_and_open_test_once(mc_frame: pd.DataFrame):
    partitions = training_run.MCStudyPartitions.from_frame(mc_frame)

    development = partitions.development
    assert set(development["split"]) == {"train", "validation"}
    development.iloc[0, development.columns.get_loc("m4l")] = 999.0
    assert 999.0 not in set(partitions.development["m4l"])
    assert not hasattr(partitions, "test")
    first = partitions.open_test()
    assert set(first["split"]) == {"test"}
    with pytest.raises(RuntimeError, match="already opened"):
        partitions.open_test()


def test_no_selection_writes_exact_common_artifacts(
    tmp_path: Path, synthetic_task4a_run: Path
):
    sources = _resolved_sources(tmp_path, synthetic_task4a_run)
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )
    training_run.publish_decorrelation_manifest(
        layout=layout,
        sources=sources,
        outcome=_outcome(selected=False),
        receipt=receipt,
        software=_software(),
    )

    assert _published_files(layout.run_dir) == {
        "config.yaml",
        "artifacts/study_manifest.json",
        *_COMMON_ARTIFACTS,
    }


def test_selection_writes_exact_conditional_artifacts(
    tmp_path: Path, synthetic_task4a_run: Path, fitted_hep_model
):
    sources = _resolved_sources(tmp_path, synthetic_task4a_run)
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=sources.config_bytes,
        artifacts=_artifacts(selected=True, model=fitted_hep_model),
    )
    training_run.publish_decorrelation_manifest(
        layout=layout,
        sources=sources,
        outcome=_outcome(selected=True),
        receipt=receipt,
        software=_software(),
    )

    assert _published_files(layout.run_dir) == {
        "config.yaml",
        "artifacts/study_manifest.json",
        *_COMMON_ARTIFACTS,
        *_SELECTED_ARTIFACTS,
    }


def test_csv_gzip_is_byte_deterministic(tmp_path: Path):
    payloads: list[bytes] = []
    config_bytes = Path("config/decorrelation_training_drop_top4.yaml").read_bytes()
    for name in ("first", "second"):
        layout = training_run.claim_decorrelation_output(
            _fresh_layout(tmp_path, name=name)
        )
        training_run.write_decorrelation_artifacts(
            layout=layout,
            config_bytes=config_bytes,
            artifacts=_artifacts(selected=False),
        )
        payloads.append((layout.predictions_dir / "oof_scores.csv.gz").read_bytes())

    assert payloads[0] == payloads[1]


def test_model_pickle_round_trip_preserves_verification_predictions(
    tmp_path: Path, fitted_hep_model
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=Path("config/decorrelation_training_drop_top4.yaml").read_bytes(),
        artifacts=_artifacts(selected=True, model=fitted_hep_model),
    )

    serialized = (layout.model_dir / "flatness_model.pkl").read_bytes()
    restored = pickle.loads(serialized)
    verification = _verification_matrix()
    np.testing.assert_allclose(
        restored.predict_proba(verification),
        fitted_hep_model.predict_proba(verification),
    )


def test_write_receipt_binds_exact_trusted_model_bytes(
    tmp_path: Path, synthetic_task4a_run: Path, fitted_hep_model
):
    sources = _resolved_sources(tmp_path, synthetic_task4a_run)
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=sources.config_bytes,
        artifacts=_artifacts(selected=True, model=fitted_hep_model),
    )
    model_path = layout.model_dir / "flatness_model.pkl"
    original = model_path.read_bytes()
    model_path.write_bytes(bytes([original[0] ^ 1]) + original[1:])

    with pytest.raises(RuntimeError, match="output receipt changed"):
        training_run.publish_decorrelation_manifest(
            layout=layout,
            sources=sources,
            outcome=_outcome(selected=True),
            receipt=receipt,
            software=_software(),
        )
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_source_mutation_blocks_manifest(
    tmp_path: Path, synthetic_task4a_run: Path
):
    sources = _resolved_sources(tmp_path, synthetic_task4a_run)
    summary = sources.records["task4a_summary"].path
    summary.write_text(json.dumps({"replacement": True}))

    with pytest.raises(RuntimeError, match="source changed"):
        training_run.assert_decorrelation_sources_unchanged(sources)


def test_decision_artifact_contradiction_is_rejected(tmp_path: Path):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    artifacts = _artifacts(selected=False)
    artifacts["selection"] = {
        "schema_version": "1.0",
        "status": "eligible_candidate_test_reported",
        "selected_candidate": "lambda_1p0",
        "test_opened": True,
        "auc_floor": 0.80,
        "ks_limit": 0.10,
    }

    with pytest.raises(ValueError, match="contradicts"):
        training_run.write_decorrelation_artifacts(
            layout=layout,
            config_bytes=Path(
                "config/decorrelation_training_drop_top4.yaml"
            ).read_bytes(),
            artifacts=artifacts,
        )
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "1.1"),
        ("auc_floor", 0.79),
        ("ks_limit", 0.11),
    ],
)
def test_selection_contract_rejects_changed_schema_or_gate(
    tmp_path: Path, field: str, value: object
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    artifacts = _artifacts(selected=False)
    artifacts["selection"][field] = value

    with pytest.raises(ValueError, match="selection contract"):
        training_run.write_decorrelation_artifacts(
            layout=layout,
            config_bytes=Path(
                "config/decorrelation_training_drop_top4.yaml"
            ).read_bytes(),
            artifacts=artifacts,
        )
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_existing_output_path_is_rejected_before_claim(tmp_path: Path):
    occupied = tmp_path / "study"
    occupied.mkdir()

    with pytest.raises(FileExistsError):
        training_run.resolve_decorrelation_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            input_run=tmp_path / "task4a",
            run_dir=occupied,
        )


def test_foreign_output_receipt_is_rejected(
    tmp_path: Path, synthetic_task4a_run: Path
):
    sources = _resolved_sources(tmp_path, synthetic_task4a_run)
    first = training_run.claim_decorrelation_output(_fresh_layout(tmp_path, name="first"))
    second = training_run.claim_decorrelation_output(
        _fresh_layout(tmp_path, name="second")
    )
    receipt = training_run.write_decorrelation_artifacts(
        layout=first,
        config_bytes=sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )

    with pytest.raises(ValueError, match="does not belong"):
        training_run.publish_decorrelation_manifest(
            layout=second,
            sources=sources,
            outcome=_outcome(selected=False),
            receipt=receipt,
            software=_software(),
        )
    assert (second.run_dir / ".terminal.failed").is_dir()
    assert (second.run_dir / "failure.json").is_file()
    assert not (second.artifacts_dir / "study_manifest.json").exists()


def test_dangling_manifest_does_not_suppress_terminal_failure(tmp_path: Path):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    (layout.artifacts_dir / "study_manifest.json").symlink_to(
        tmp_path / "missing-manifest"
    )

    training_run.record_decorrelation_failure(layout, RuntimeError("failed"))

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


def test_promotion_seam_substitution_fails_closed(
    tmp_path: Path, synthetic_task4a_run: Path, monkeypatch
):
    sources = _resolved_sources(tmp_path, synthetic_task4a_run)
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )

    def substitute_output(_destination: Path) -> None:
        (layout.artifacts_dir / "candidate_results.csv").write_bytes(
            b"candidate,weighted_oof_auc,eligible\nreplacement,0.99,True\n"
        )

    monkeypatch.setattr(
        training_run,
        "_before_decorrelation_manifest_promotion",
        substitute_output,
    )
    with pytest.raises(RuntimeError, match="output receipt changed"):
        training_run.publish_decorrelation_manifest(
            layout=layout,
            sources=sources,
            outcome=_outcome(selected=False),
            receipt=receipt,
            software=_software(),
        )
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_manifest_requires_pinned_hep_ml_version(
    tmp_path: Path, synthetic_task4a_run: Path
):
    sources = _resolved_sources(tmp_path, synthetic_task4a_run)
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )

    with pytest.raises(ValueError, match="hep_ml 0.8.0"):
        training_run.publish_decorrelation_manifest(
            layout=layout,
            sources=sources,
            outcome=_outcome(selected=False),
            receipt=receipt,
            software={"hep_ml": "0.8.1"},
        )
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_manifest_is_newer_than_every_published_artifact(
    tmp_path: Path, synthetic_task4a_run: Path
):
    sources = _resolved_sources(tmp_path, synthetic_task4a_run)
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )
    manifest = training_run.publish_decorrelation_manifest(
        layout=layout,
        sources=sources,
        outcome=_outcome(selected=False),
        receipt=receipt,
        software=_software(),
    )

    manifest_path = layout.artifacts_dir / "study_manifest.json"
    assert json.loads(manifest_path.read_text()) == manifest
    assert manifest_path.stat().st_mtime_ns >= max(
        path.stat().st_mtime_ns
        for path in layout.run_dir.rglob("*")
        if path.is_file() and path != manifest_path
    )


def _bound_config(tmp_path: Path, input_run: Path) -> Path:
    raw = yaml.safe_load(
        Path("config/decorrelation_training_drop_top4.yaml").read_text()
    )
    raw["input_run"] = str(input_run.resolve())
    raw["input_manifest_sha256"] = _sha(
        input_run / "artifacts/run_manifest.json"
    )
    raw["input_mc_sha256"] = _sha(input_run / "processed/mc_events.csv.gz")
    path = tmp_path / "bound-decorrelation.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    return path


def _resolved_sources(tmp_path: Path, input_run: Path):
    from src.full_training_run import resolve_training_input

    training_input = resolve_training_input(input_run)
    frozen = training_run.load_decorrelation_config(
        Path("config/decorrelation_training_drop_top4.yaml")
    )
    validated = replace(
        frozen,
        input_run=str(input_run.resolve()),
        input_manifest_sha256=_sha(input_run / "artifacts/run_manifest.json"),
        input_mc_sha256=_sha(input_run / "processed/mc_events.csv.gz"),
    )
    config_source = training_run.StudySource.from_path(
        "study_config",
        Path("config/decorrelation_training_drop_top4.yaml"),
        capture=True,
    )
    records = {
        "study_config": config_source,
        "task4a_config": training_run.StudySource.from_path(
            "task4a_config", training_input.config_path, capture=True
        ),
        "task4a_mc": training_run.StudySource.from_path(
            "task4a_mc", training_input.mc_path
        ),
        "task4a_summary": training_run.StudySource.from_path(
            "task4a_summary", training_input.summary_path, capture=True
        ),
        "task4a_manifest": training_run.StudySource.from_path(
            "task4a_manifest", training_input.manifest_path, capture=True
        ),
    }
    return training_run.DecorrelationSources(
        config=validated,
        config_bytes=config_source.snapshot,
        training_input=training_input,
        records=records,
    )


def _fresh_layout(tmp_path: Path, *, name: str = "study"):
    return training_run.resolve_decorrelation_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=tmp_path / "task4a",
        run_dir=tmp_path / name,
    )


def _artifacts(*, selected: bool, model=None) -> dict[str, object]:
    selection = {
        "schema_version": "1.0",
        "status": (
            "eligible_candidate_test_reported"
            if selected
            else "no_eligible_candidate"
        ),
        "selected_candidate": "lambda_1p0" if selected else None,
        "test_opened": selected,
        "auc_floor": 0.80,
        "ks_limit": 0.10,
    }
    artifacts: dict[str, object] = {
        "candidate_results": pd.DataFrame(
            {
                "candidate": ["lambda_0p0", "lambda_1p0"],
                "weighted_oof_auc": [0.79, 0.82],
                "eligible": [False, selected],
            }
        ),
        "working_point_metrics": pd.DataFrame(
            {
                "candidate": ["lambda_0p0", "lambda_1p0"],
                "working_point": ["loose", "tight"],
                "zz_mass_ks_distance": [0.2, 0.08],
            }
        ),
        "selection": selection,
        "oof_scores": pd.DataFrame(
            {
                "eventNumber": [1, 2],
                "split": ["train", "validation"],
                "score_lambda_0p0": [0.2, 0.8],
            }
        ),
        "plot_artifacts": {
            "candidate_tradeoff.png": b"\x89PNG\r\n\x1a\ntradeoff",
            "working_point_ks.png": b"\x89PNG\r\n\x1a\nks",
        },
        "model": None,
        "selected_oof_scores": None,
        "test_scores": None,
        "test_metrics": None,
    }
    if selected:
        artifacts.update(
            model=model,
            selected_oof_scores=pd.DataFrame(
                {"eventNumber": [1, 2], "oof_score": [0.25, 0.75]}
            ),
            test_scores=pd.DataFrame(
                {
                    "eventNumber": [3, 4],
                    "split": ["test", "test"],
                    "score": [0.3, 0.7],
                }
            ),
            test_metrics={"schema_version": "1.0", "weighted_auc": 0.81},
        )
        artifacts["plot_artifacts"][
            "selected_mass_sculpting.png"
        ] = b"\x89PNG\r\n\x1a\nmass"
    return artifacts


def _outcome(*, selected: bool):
    candidate = SimpleNamespace(coefficient=1.0) if selected else None
    return SimpleNamespace(
        selection=SimpleNamespace(selected=candidate),
        evidence=object() if selected else None,
    )


def _verification_matrix() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {feature: float(index + 1) for index, feature in enumerate(_FEATURES)},
            {feature: float(-(index + 1)) for index, feature in enumerate(_FEATURES)},
        ]
    )


def _software() -> dict[str, str]:
    return {"python": "test", "hep_ml": "0.8.0"}


def _published_files(run_dir: Path) -> set[str]:
    return {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file()
    }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
