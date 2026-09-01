from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.decorrelation_training_run import (
    DecorrelationSources,
    MCStudyPartitions,
    StudySource,
    approved_decorrelation_artifacts,
    assert_decorrelation_sources_unchanged,
    claim_decorrelation_output,
    load_decorrelation_config,
    publish_decorrelation_manifest,
    resolve_decorrelation_output,
    write_decorrelation_artifacts,
)
from src.features import FEATURES
from src.full_training_run import TrainingInput


def test_production_config_freezes_every_approved_decision():
    config = load_decorrelation_config(
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
    assert set(config.artifacts_no_selection) == approved_decorrelation_artifacts(
        selected=False
    )
    assert set(config.artifacts_selected) == approved_decorrelation_artifacts(
        selected=True
    )


def test_config_rejects_changed_coefficient(tmp_path):
    source = Path("config/decorrelation_training_drop_top4.yaml").read_text()
    changed = tmp_path / "changed.yaml"
    changed.write_text(source.replace("  - 3.0\n", "  - 4.0\n"))

    with pytest.raises(ValueError, match="frozen decision"):
        load_decorrelation_config(changed)


def test_partitions_expose_development_and_open_test_once():
    frame = _mc_frame()
    partitions = MCStudyPartitions.from_frame(frame)

    assert set(partitions.development["split"]) == {"train", "validation"}
    first = partitions.open_test()
    assert set(first["split"]) == {"test"}
    with pytest.raises(RuntimeError, match="already opened"):
        partitions.open_test()


def test_existing_output_path_is_rejected_before_claim(tmp_path):
    occupied = tmp_path / "occupied"
    occupied.mkdir()

    with pytest.raises(FileExistsError):
        resolve_decorrelation_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            input_run=tmp_path / "input",
            run_dir=occupied,
        )


def test_no_selection_writes_exact_common_artifacts(tmp_path):
    config_bytes = Path("config/decorrelation_training_drop_top4.yaml").read_bytes()
    layout = claim_decorrelation_output(
        resolve_decorrelation_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            input_run=tmp_path / "input",
            run_dir=tmp_path / "study",
        )
    )
    artifacts = {
        "candidate_results": pd.DataFrame(
            {"candidate": ["lambda_0p0"], "weighted_oof_auc": [0.79]}
        ),
        "working_point_metrics": pd.DataFrame(
            {"candidate": ["lambda_0p0"], "oof_zz_mass_ks": [0.2]}
        ),
        "selection": {
            "schema_version": "1.0",
            "status": "no_eligible_candidate",
            "selected_candidate": None,
            "test_opened": False,
        },
        "oof_scores": pd.DataFrame(
            {"eventNumber": [1], "score_lambda_0p0": [0.5]}
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

    write_decorrelation_artifacts(
        layout=layout,
        config_bytes=config_bytes,
        artifacts=artifacts,
    )

    files = {
        path.relative_to(layout.run_dir).as_posix()
        for path in layout.run_dir.rglob("*")
        if path.is_file()
    }
    assert files == {"config.yaml", *approved_decorrelation_artifacts(selected=False)}


def test_manifest_rejects_decision_artifact_contradiction(tmp_path):
    config_bytes = Path("config/decorrelation_training_drop_top4.yaml").read_bytes()
    layout = claim_decorrelation_output(
        resolve_decorrelation_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            input_run=tmp_path / "input",
            run_dir=tmp_path / "study",
        )
    )
    receipt = write_decorrelation_artifacts(
        layout=layout,
        config_bytes=config_bytes,
        artifacts=_no_selection_artifacts(),
    )
    sources = _fake_sources(tmp_path)
    contradictory = SimpleNamespace(
        selection=SimpleNamespace(
            selected=SimpleNamespace(coefficient=1.0)
        ),
        evidence=object(),
    )

    with pytest.raises(ValueError, match="contradicts"):
        publish_decorrelation_manifest(
            layout=layout,
            sources=sources,
            outcome=contradictory,
            receipt=receipt,
            software={"hep_ml": "0.8.0"},
        )

    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_source_mutation_blocks_manifest_and_records_failure(tmp_path):
    config_bytes = Path("config/decorrelation_training_drop_top4.yaml").read_bytes()
    layout = claim_decorrelation_output(
        resolve_decorrelation_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            input_run=tmp_path / "input",
            run_dir=tmp_path / "study",
        )
    )
    receipt = write_decorrelation_artifacts(
        layout=layout,
        config_bytes=config_bytes,
        artifacts=_no_selection_artifacts(),
    )
    sources = _fake_sources(tmp_path)
    sources.records["task4a_summary"].path.write_bytes(b"changed")
    outcome = SimpleNamespace(
        selection=SimpleNamespace(selected=None), evidence=None
    )

    with pytest.raises(RuntimeError, match="source changed"):
        publish_decorrelation_manifest(
            layout=layout,
            sources=sources,
            outcome=outcome,
            receipt=receipt,
            software={"hep_ml": "0.8.0"},
        )

    assert not (layout.artifacts_dir / "study_manifest.json").exists()
    assert (layout.run_dir / "failure.json").exists()


def _no_selection_artifacts():
    return {
        "candidate_results": pd.DataFrame(
            {"candidate": ["lambda_0p0"], "weighted_oof_auc": [0.79]}
        ),
        "working_point_metrics": pd.DataFrame(
            {"candidate": ["lambda_0p0"], "oof_zz_mass_ks": [0.2]}
        ),
        "selection": {
            "schema_version": "1.0",
            "status": "no_eligible_candidate",
            "selected_candidate": None,
            "test_opened": False,
        },
        "oof_scores": pd.DataFrame(
            {"eventNumber": [1], "score_lambda_0p0": [0.5]}
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


def _fake_sources(tmp_path):
    records = {}
    for name in (
        "study_config",
        "task4a_config",
        "task4a_mc",
        "task4a_summary",
        "task4a_manifest",
    ):
        path = tmp_path / f"{name}.bin"
        path.write_bytes(name.encode())
        records[name] = StudySource.from_path(name, path)
    config = load_decorrelation_config(
        Path("config/decorrelation_training_drop_top4.yaml")
    )
    training_input = TrainingInput(
        input_run=tmp_path,
        config_path=records["task4a_config"].path,
        mc_path=records["task4a_mc"].path,
        summary_path=records["task4a_summary"].path,
        manifest_path=records["task4a_manifest"].path,
        hashes={},
        expected_rows=1,
    )
    sources = DecorrelationSources(
        config=config,
        config_bytes=records["study_config"].path.read_bytes(),
        training_input=training_input,
        records=records,
    )
    assert_decorrelation_sources_unchanged(sources)
    return sources


def _mc_frame():
    rows = []
    event = 1
    for split in ("train", "validation", "test"):
        for label in (0, 1):
            row = {name: float(event + offset) for offset, name in enumerate(FEATURES)}
            row.update(
                {
                    "m4l": 110.0 + event,
                    "eventNumber": event,
                    "channelNumber": 363490 if label == 0 else 345060,
                    "split": split,
                    "label": label,
                    "physical_weight": 1.0,
                }
            )
            rows.append(row)
            event += 1
    return pd.DataFrame(rows)
