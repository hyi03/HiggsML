from __future__ import annotations

import base64
from dataclasses import replace
import gzip
import hashlib
import io
import json
from pathlib import Path
import pickle
from types import SimpleNamespace
import warnings

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
_AUDIT_COLUMNS = (
    "eventNumber",
    "channelNumber",
    "split",
    "label",
    "physical_weight",
    "m4l",
    "development_fold",
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
_VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


@pytest.fixture
def synthetic_task4a_run(tmp_path: Path) -> Path:
    from tests.test_full_training_run import _synthetic_task4a_run

    return _synthetic_task4a_run(tmp_path)


@pytest.fixture(scope="module")
def frozen_sources():
    return _strict_sources()


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


@pytest.fixture(scope="module")
def fitted_hep_model():
    from src.decorrelation_training import build_flatness_model

    config = training_run.load_decorrelation_config(
        Path("config/decorrelation_training_drop_top4.yaml")
    )
    generator = np.random.default_rng(42)
    labels = np.asarray([0] * 120 + [1] * 120, dtype=int)
    fitting = pd.DataFrame(
        {
            feature: generator.normal(size=len(labels))
            for feature in _FEATURES
        }
    )
    fitting["m4l"] = generator.uniform(105.0, 160.0, size=len(labels))
    model = build_flatness_model(config, 1.0)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="X has feature names, but NearestNeighbors was fitted without feature names",
            category=UserWarning,
        )
        model.fit(
            fitting,
            labels,
            sample_weight=np.ones(len(labels), dtype=float),
        )
    return model


@pytest.fixture(scope="module")
def wrong_hep_model():
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


def test_source_inventory_is_explicitly_mc_only(frozen_sources):
    assert set(frozen_sources.records) == {
        "study_config",
        "task4a_config",
        "task4a_mc",
        "task4a_summary",
        "task4a_manifest",
    }
    assert all(
        "data_events" not in str(source.path)
        for source in frozen_sources.records.values()
    )
    assert all(
        "periodA" not in str(source.path)
        for source in frozen_sources.records.values()
    )


def test_public_source_resolver_rejects_rebound_config(
    tmp_path: Path, synthetic_task4a_run: Path
):
    with pytest.raises(ValueError, match="canonical.*study config"):
        training_run.resolve_decorrelation_sources(
            input_run=synthetic_task4a_run,
            config_path=_bound_config(tmp_path, synthetic_task4a_run),
        )


def test_source_resolver_rejects_byte_identical_attacker_config(
    tmp_path: Path, frozen_sources
):
    attacker_config = tmp_path / "decorrelation_training_drop_top4.yaml"
    attacker_config.write_bytes(frozen_sources.config_bytes)

    with pytest.raises(ValueError, match="canonical.*study config"):
        training_run.resolve_decorrelation_sources(
            input_run=frozen_sources.training_input.input_run,
            config_path=attacker_config,
        )


def test_no_source_resolver_bypass_is_exposed():
    assert not hasattr(
        training_run, "_resolve_decorrelation_sources_with_validated_config"
    )


def test_source_capability_rejects_direct_construction(frozen_sources):
    with pytest.raises(TypeError, match="returned by resolve_decorrelation_sources"):
        training_run.DecorrelationSources(
            config=frozen_sources.config,
            config_bytes=frozen_sources.config_bytes,
            training_input=frozen_sources.training_input,
            records=frozen_sources.records,
        )


def test_source_capability_rejects_dataclass_replace(frozen_sources):
    rebound = replace(frozen_sources.config, input_run="runs/attacker-controlled")

    with pytest.raises(TypeError):
        replace(frozen_sources, config=rebound)


def test_publisher_reparses_resolved_source_config_binding(tmp_path: Path):
    sources = _strict_sources()
    object.__setattr__(
        sources,
        "config",
        replace(sources.config, input_run="runs/attacker-controlled"),
    )
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )

    with pytest.raises(ValueError, match="strict frozen config"):
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


def test_publisher_reconstructs_training_input_paths_and_rows(tmp_path: Path):
    sources = _strict_sources()
    attacker_config = tmp_path / "attacker-config.yaml"
    attacker_summary = tmp_path / "attacker-summary.json"
    attacker_config.write_bytes(sources.records["task4a_config"].snapshot)
    attacker_summary.write_bytes(sources.records["task4a_summary"].snapshot)
    forged_training_input = replace(
        sources.training_input,
        config_path=attacker_config,
        summary_path=attacker_summary,
        expected_rows=sources.training_input.expected_rows + 1,
    )
    forged_records = dict(sources.records)
    forged_records["task4a_config"] = training_run.StudySource.from_path(
        "task4a_config", attacker_config, capture=True
    )
    forged_records["task4a_summary"] = training_run.StudySource.from_path(
        "task4a_summary", attacker_summary, capture=True
    )
    object.__setattr__(sources, "training_input", forged_training_input)
    object.__setattr__(sources, "records", forged_records)
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )

    with pytest.raises(ValueError, match="independently resolved sources"):
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


def test_no_selection_writes_exact_common_artifacts(tmp_path: Path, frozen_sources):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=frozen_sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )
    training_run.publish_decorrelation_manifest(
        layout=layout,
        sources=frozen_sources,
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
    tmp_path: Path, frozen_sources, fitted_hep_model
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=frozen_sources.config_bytes,
        artifacts=_artifacts(selected=True, model=fitted_hep_model),
    )
    training_run.publish_decorrelation_manifest(
        layout=layout,
        sources=frozen_sources,
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


def test_writer_eligibility_uses_frozen_target_not_achieved_efficiency(
    tmp_path: Path, frozen_sources, fitted_hep_model
):
    artifacts = _artifacts(selected=True, model=fitted_hep_model)
    working_points = artifacts["working_point_metrics"]
    working_points.loc[
        (working_points["candidate"] == "lambda_1p0")
        & (working_points["working_point"] == "loose"),
        "achieved_background_efficiency",
    ] = 0.9
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))

    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=frozen_sources.config_bytes,
        artifacts=artifacts,
    )

    assert receipt.selected is True


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


@pytest.mark.parametrize(
    "malformation",
    (
        "invalid_child_index",
        "invalid_feature_index",
        "invalid_leaf_sentinel",
        "unreachable_node",
        "unvisited_cycle",
        "incorrect_max_depth",
    ),
)
def test_static_model_audit_rejects_malformed_unvisited_tree_nodes(
    fitted_hep_model, malformation: str
):
    """Every serialized tree node must be valid, even if audit rows miss it."""
    model = pickle.loads(pickle.dumps(fitted_hep_model, protocol=5))
    raw_tree = model.estimators[0][0].tree_
    state = raw_tree.__getstate__()
    nodes = state["nodes"].copy()

    verification = training_run._model_verification_frame().to_numpy(dtype=float)
    visited = {0}
    for row in verification:
        node_index = 0
        while nodes[node_index]["left_child"] != -1:
            feature = int(nodes[node_index]["feature"])
            node_index = int(
                nodes[node_index]["left_child"]
                if row[feature] <= nodes[node_index]["threshold"]
                else nodes[node_index]["right_child"]
            )
            visited.add(node_index)
    assert 2 not in visited
    assert nodes[2]["left_child"] == -1
    assert nodes[2]["right_child"] == -1
    if malformation == "invalid_child_index":
        nodes[2]["left_child"] = len(nodes)
        nodes[2]["right_child"] = 4
        nodes[2]["feature"] = 0
    elif malformation == "invalid_feature_index":
        nodes[2]["left_child"] = 3
        nodes[2]["right_child"] = 4
        nodes[2]["feature"] = len(_FEATURES)
    elif malformation == "invalid_leaf_sentinel":
        nodes[2]["feature"] = 0
    elif malformation == "unreachable_node":
        nodes[1]["left_child"] = 3
    elif malformation == "unvisited_cycle":
        nodes[2]["left_child"] = 2
        nodes[2]["right_child"] = 2
        nodes[2]["feature"] = 0
    elif malformation == "incorrect_max_depth":
        state["max_depth"] = 3
    else:  # pragma: no cover - exhaustive parameter guard
        raise AssertionError(malformation)
    state["nodes"] = nodes
    raw_tree.__setstate__(state)

    with pytest.raises(ValueError, match="tree|branch|leaf|depth|reach|cycle"):
        training_run._validate_model_pickle_semantics(
            pickle.dumps(model, protocol=5),
            selected_coefficient=1.0,
        )


def test_real_hep_ml_synthetic_oof_and_manifest(
    tmp_path: Path, frozen_sources
):
    from hep_ml.gradientboosting import UGradientBoostingClassifier

    from scripts.run_decorrelation_training import build_decorrelation_artifacts
    from src.decorrelation_training import (
        FlatnessOutcome,
        evaluate_flatness_candidate,
        generate_flatness_oof,
        select_flatness_candidate,
    )
    from src.full_training_run import (
        load_training_mc_frame,
        resolve_training_input,
    )

    input_run = _real_hep_ml_task4a_run(tmp_path)
    training_input = resolve_training_input(input_run)
    production = frozen_sources.config
    test_config = replace(
        production,
        input_run=str(input_run.resolve()),
        input_manifest_sha256=training_input.hashes["manifest"],
        input_mc_sha256=training_input.hashes["mc"],
        coefficients=(0.5,),
    )
    assert test_config.model == production.model
    assert test_config.flatness == production.flatness
    assert test_config.input_manifest_sha256 == _sha(
        input_run / "artifacts/run_manifest.json"
    )
    assert test_config.input_mc_sha256 == _sha(
        input_run / "processed/mc_events.csv.gz"
    )

    frame = load_training_mc_frame(training_input)
    development = frame.loc[frame["split"].isin(("train", "validation"))]
    fitted_models: list[UGradientBoostingClassifier] = []

    def real_factory(**kwargs):
        model = UGradientBoostingClassifier(**kwargs)
        fitted_models.append(model)
        return model

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=(
                "X has feature names, but NearestNeighbors was fitted without "
                "feature names"
            ),
            category=UserWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message=".*events out of all bins.*",
            category=UserWarning,
        )
        oof = generate_flatness_oof(
            development,
            test_config,
            0.5,
            model_factory=real_factory,
        )

    assert len(oof) == len(development)
    assert np.isfinite(oof["score_lambda_0p5"]).all()
    assert len(fitted_models) == 5
    for model in fitted_models:
        assert tuple(model.train_features) == _FEATURES
        assert "m4l" not in model.train_features

    results = []
    for coefficient in production.coefficients:
        score_column = f"score_lambda_{str(float(coefficient)).replace('.', 'p')}"
        audit = oof.rename(columns={"score_lambda_0p5": score_column})
        results.append(
            evaluate_flatness_candidate(
                audit,
                production,
                coefficient=coefficient,
            )
        )
    selection = select_flatness_candidate(results)
    assert selection.selected is None
    outcome = FlatnessOutcome(selection=selection, evidence=None)
    artifacts = build_decorrelation_artifacts(outcome, production)

    layout = training_run.claim_decorrelation_output(
        _fresh_layout(tmp_path, name="real-hep-ml-study")
    )
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=frozen_sources.config_bytes,
        artifacts=artifacts,
    )
    manifest = training_run.publish_decorrelation_manifest(
        layout=layout,
        sources=frozen_sources,
        outcome=outcome,
        receipt=receipt,
        software=_software(),
    )

    expected_files = {
        "config.yaml",
        *production.artifacts_no_selection,
        "artifacts/study_manifest.json",
    }
    payloads = {
        path.relative_to(layout.run_dir).as_posix(): path.read_bytes()
        for path in layout.run_dir.rglob("*")
        if path.is_file()
    }
    assert set(payloads) == expected_files
    expected_outputs: dict[str, dict[str, object]] = {}
    output_paths = ["config.yaml", *sorted(production.artifacts_no_selection)]
    for relative in output_paths:
        payload = payloads[relative]
        record: dict[str, object] = {
            "path": str(layout.run_dir / relative),
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        if relative.endswith(".csv") or relative.endswith(".csv.gz"):
            record["row_count"] = len(
                pd.read_csv(
                    io.BytesIO(payload),
                    compression="gzip" if relative.endswith(".gz") else None,
                )
            )
        expected_outputs[relative] = record
    expected_sources = {
        name: {
            "path": str(source.path),
            "size_bytes": source.size_bytes,
            "sha256": source.sha256,
            **(
                {"expected_rows": frozen_sources.training_input.expected_rows}
                if name == "task4a_mc"
                else {}
            ),
        }
        for name, source in frozen_sources.records.items()
    }
    expected_manifest = {
        "schema_version": "1.0",
        "status": "complete",
        "decision": {
            "status": "no_eligible_candidate",
            "selected_candidate": None,
            "selected_coefficient": None,
            "test_opened": False,
        },
        "software": _software(),
        "sources": expected_sources,
        "outputs": expected_outputs,
    }
    expected_manifest_bytes = (
        json.dumps(
            expected_manifest,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    assert manifest == expected_manifest
    assert payloads["artifacts/study_manifest.json"] == expected_manifest_bytes


def test_writer_rejects_logloss_two_tree_model(
    tmp_path: Path, frozen_sources, wrong_hep_model
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))

    with pytest.raises(ValueError, match="flatness model|KnnFlatness|policy"):
        training_run.write_decorrelation_artifacts(
            layout=layout,
            config_bytes=frozen_sources.config_bytes,
            artifacts=_artifacts(selected=True, model=wrong_hep_model),
        )

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


def test_writer_rejects_inferior_eligible_selection(
    tmp_path: Path, frozen_sources, fitted_hep_model
):
    artifacts = _artifacts(selected=True, model=fitted_hep_model)
    candidates = artifacts["candidate_results"]
    better = candidates["candidate"] == "lambda_0p0"
    candidates.loc[better, "weighted_oof_auc"] = 0.90
    candidates.loc[better, "maximum_oof_zz_ks"] = 0.05
    candidates.loc[better, "eligible"] = True
    candidates.loc[better, "eligibility_reasons"] = ""
    points = artifacts["working_point_metrics"]
    better_points = points["candidate"] == "lambda_0p0"
    points.loc[better_points, "signal_efficiency"] = [0.8, 0.5, 0.3]
    points.loc[better_points, "zz_mass_ks_distance"] = 0.05
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))

    with pytest.raises(ValueError, match="deterministic.*winner"):
        training_run.write_decorrelation_artifacts(
            layout=layout,
            config_bytes=frozen_sources.config_bytes,
            artifacts=artifacts,
        )

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


@pytest.mark.parametrize("case", ("reasons", "candidate_range", "point_range"))
def test_writer_rejects_incorrect_eligibility_reasons_or_metric_ranges(
    tmp_path: Path, frozen_sources, case: str
):
    artifacts = _artifacts(selected=False)
    if case == "reasons":
        artifacts["candidate_results"].loc[
            0, "eligibility_reasons"
        ] = "weighted_auc_below_floor"
    elif case == "candidate_range":
        artifacts["candidate_results"].loc[
            0, "background_score_mass_correlation"
        ] = 1.01
    else:
        artifacts["working_point_metrics"].loc[0, "threshold"] = -0.01
    layout = training_run.claim_decorrelation_output(
        _fresh_layout(tmp_path, name=case)
    )

    with pytest.raises(ValueError, match="eligibility reasons|range"):
        training_run.write_decorrelation_artifacts(
            layout=layout,
            config_bytes=frozen_sources.config_bytes,
            artifacts=artifacts,
        )

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


@pytest.mark.parametrize("case", ("test_score", "weighted_auc", "threshold"))
def test_writer_rejects_inconsistent_test_scores_metrics_or_thresholds(
    tmp_path: Path, frozen_sources, fitted_hep_model, case: str
):
    artifacts = _artifacts(selected=True, model=fitted_hep_model)
    if case == "test_score":
        artifacts["test_scores"].loc[0, "score"] = 0.9
    elif case == "weighted_auc":
        artifacts["test_metrics"]["weighted_auc"] = 0.5
    else:
        artifacts["test_metrics"]["working_points"]["loose"][
            "threshold"
        ] = 0.2
    layout = training_run.claim_decorrelation_output(
        _fresh_layout(tmp_path, name=case)
    )

    with pytest.raises(ValueError, match="test_metrics|frozen.*threshold"):
        training_run.write_decorrelation_artifacts(
            layout=layout,
            config_bytes=frozen_sources.config_bytes,
            artifacts=artifacts,
        )

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


def test_write_receipt_binds_exact_trusted_model_bytes(
    tmp_path: Path, frozen_sources, fitted_hep_model
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=frozen_sources.config_bytes,
        artifacts=_artifacts(selected=True, model=fitted_hep_model),
    )
    model_path = layout.model_dir / "flatness_model.pkl"
    original = model_path.read_bytes()
    model_path.write_bytes(bytes([original[0] ^ 1]) + original[1:])

    with pytest.raises(RuntimeError, match="output receipt changed"):
        training_run.publish_decorrelation_manifest(
            layout=layout,
            sources=frozen_sources,
            outcome=_outcome(selected=True),
            receipt=receipt,
            software=_software(),
        )
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_forged_receipt_cannot_authorize_untrusted_selected_outputs(
    tmp_path: Path, frozen_sources
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    _write_manual_selected_outputs(
        layout,
        config_bytes=frozen_sources.config_bytes,
        artifacts=_artifacts(selected=True),
    )
    receipt = object.__new__(training_run.DecorrelationArtifactReceipt)
    object.__setattr__(receipt, "_run_identity", layout.directory_identities["."])
    object.__setattr__(receipt, "selected", True)
    object.__setattr__(receipt, "_outputs", _filesystem_output_records(layout, True))
    object.__setattr__(receipt, "_model", b"not-a-model-object")
    object.__setattr__(
        receipt,
        "_model_bytes",
        b"not-a-trusted-hep-ml-pickle",
    )

    with pytest.raises((TypeError, ValueError), match="writer-bound"):
        training_run.publish_decorrelation_manifest(
            layout=layout,
            sources=frozen_sources,
            outcome=_outcome(selected=True),
            receipt=receipt,
            software=_software(),
        )
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_token_bearing_forged_receipt_does_not_authorize_publication(
    tmp_path: Path, frozen_sources
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    legitimate = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=frozen_sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )
    forged = object.__new__(training_run.DecorrelationArtifactReceipt)
    for name in (
        "_run_identity",
        "selected",
        "_selected_coefficient",
        "_outputs",
        "_model",
        "_model_bytes",
    ):
        object.__setattr__(forged, name, getattr(legitimate, name))
    object.__setattr__(
        forged,
        "_authorization",
        _reachable_authorization_token(layout),
    )

    with pytest.raises(ValueError, match="receipt|writer"):
        training_run.publish_decorrelation_manifest(
            layout=layout,
            sources=frozen_sources,
            outcome=_outcome(selected=False),
            receipt=forged,
            software=_software(),
        )

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_source_mutation_blocks_manifest(frozen_sources, monkeypatch):
    original = training_run.StudySource.from_path

    def changed_source(cls, name, path, *, capture=False):
        source = original(name, path, capture=capture)
        if name == "task4a_summary":
            return replace(source, sha256="0" * 64)
        return source

    monkeypatch.setattr(
        training_run.StudySource,
        "from_path",
        classmethod(changed_source),
    )

    with pytest.raises(RuntimeError, match="source changed"):
        training_run.assert_decorrelation_sources_unchanged(frozen_sources)


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
    tmp_path: Path, frozen_sources
):
    first = training_run.claim_decorrelation_output(_fresh_layout(tmp_path, name="first"))
    second = training_run.claim_decorrelation_output(
        _fresh_layout(tmp_path, name="second")
    )
    receipt = training_run.write_decorrelation_artifacts(
        layout=first,
        config_bytes=frozen_sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )

    with pytest.raises(ValueError, match="does not belong"):
        training_run.publish_decorrelation_manifest(
            layout=second,
            sources=frozen_sources,
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


@pytest.mark.parametrize(
    ("record_group", "record_name"),
    [
        ("outputs", "config.yaml"),
        ("sources", "task4a_mc"),
    ],
)
def test_counterfeit_complete_manifest_hash_does_not_suppress_failure(
    tmp_path: Path, frozen_sources, record_group: str, record_name: str
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=frozen_sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )
    manifest = training_run.publish_decorrelation_manifest(
        layout=layout,
        sources=frozen_sources,
        outcome=_outcome(selected=False),
        receipt=receipt,
        software=_software(),
    )
    manifest[record_group][record_name]["sha256"] = "0" * 64
    manifest_path = layout.artifacts_dir / "study_manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    training_run.record_decorrelation_failure(layout, RuntimeError("failed"))

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


def test_contradictory_selection_with_rebound_hash_does_not_complete(
    tmp_path: Path, frozen_sources
):
    layout = _publish_no_selection(tmp_path, frozen_sources)
    contradictory = {
        "schema_version": "1.0",
        "status": "eligible_candidate_test_reported",
        "selected_candidate": "lambda_1p0",
        "test_opened": True,
        "auc_floor": 0.80,
        "ks_limit": 0.10,
    }
    _replace_output_and_rebind_manifest(
        layout,
        "artifacts/selection.json",
        json.dumps(contradictory, sort_keys=True).encode("utf-8"),
    )

    training_run.record_decorrelation_failure(layout, RuntimeError("failed"))

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


def test_pickle_none_with_rebound_hash_does_not_complete(
    tmp_path: Path, frozen_sources, fitted_hep_model
):
    layout = _publish_selection(tmp_path, frozen_sources, fitted_hep_model)
    _replace_output_and_rebind_manifest(
        layout,
        "model/flatness_model.pkl",
        pickle.dumps(None, protocol=5),
    )

    training_run.record_decorrelation_failure(layout, RuntimeError("failed"))

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


def test_pickle_none_with_rebound_manifest_and_authorization_does_not_complete(
    tmp_path: Path, frozen_sources, fitted_hep_model
):
    layout = _publish_selection(tmp_path, frozen_sources, fitted_hep_model)
    _replace_output_and_rebind_manifest(
        layout,
        "model/flatness_model.pkl",
        pickle.dumps(None, protocol=5),
    )
    _rebind_reachable_completion_authorization(layout)

    training_run.record_decorrelation_failure(layout, RuntimeError("failed"))

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


def test_non_png_with_rebound_hash_does_not_complete(
    tmp_path: Path, frozen_sources
):
    layout = _publish_no_selection(tmp_path, frozen_sources)
    _replace_output_and_rebind_manifest(
        layout,
        "plots/candidate_tradeoff.png",
        b"not-a-decodable-png",
    )

    training_run.record_decorrelation_failure(layout, RuntimeError("failed"))

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


def test_wrong_csv_schema_with_rebound_hash_does_not_complete(
    tmp_path: Path, frozen_sources
):
    layout = _publish_no_selection(tmp_path, frozen_sources)
    _replace_output_and_rebind_manifest(
        layout,
        "artifacts/candidate_results.csv",
        b"wrong_column\n1\n",
    )

    training_run.record_decorrelation_failure(layout, RuntimeError("failed"))

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


@pytest.mark.parametrize("dangling", [False, True])
def test_foreign_training_manifest_does_not_suppress_failure(
    tmp_path: Path, dangling: bool
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    foreign = layout.artifacts_dir / "training_manifest.json"
    if dangling:
        foreign.symlink_to(tmp_path / "missing-training-manifest")
    else:
        foreign.write_text("{}")

    training_run.record_decorrelation_failure(layout, RuntimeError("failed"))

    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()


def test_verified_study_completion_prevents_failure_overwrite(
    tmp_path: Path, frozen_sources
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=frozen_sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )
    training_run.publish_decorrelation_manifest(
        layout=layout,
        sources=frozen_sources,
        outcome=_outcome(selected=False),
        receipt=receipt,
        software=_software(),
    )
    manifest_path = layout.artifacts_dir / "study_manifest.json"
    original = manifest_path.read_bytes()

    training_run.record_decorrelation_failure(layout, RuntimeError("late failure"))

    assert manifest_path.read_bytes() == original
    assert not (layout.run_dir / ".terminal.failed").exists()
    assert not (layout.run_dir / "failure.json").exists()


def test_verified_selected_completion_prevents_failure_overwrite(
    tmp_path: Path, frozen_sources, fitted_hep_model
):
    layout = _publish_selection(tmp_path, frozen_sources, fitted_hep_model)

    training_run.record_decorrelation_failure(
        layout, RuntimeError("late selected failure")
    )

    assert not (layout.run_dir / ".terminal.failed").exists()
    assert not (layout.run_dir / "failure.json").exists()


@pytest.mark.parametrize("selected", [False, True])
def test_verified_completion_survives_process_authorization_state_loss(
    tmp_path: Path, frozen_sources, fitted_hep_model, selected: bool
):
    if selected:
        layout = _publish_selection(tmp_path, frozen_sources, fitted_hep_model)
    else:
        layout = _publish_no_selection(tmp_path, frozen_sources)
    manifest_path = layout.artifacts_dir / "study_manifest.json"
    original = manifest_path.read_bytes()
    _clear_reachable_authorization_registries()

    training_run.record_decorrelation_failure(
        layout, RuntimeError("simulated post-restart failure")
    )

    assert manifest_path.read_bytes() == original
    assert not (layout.run_dir / ".terminal.failed").exists()
    assert not (layout.run_dir / "failure.json").exists()


def test_promotion_seam_substitution_fails_closed(
    tmp_path: Path, frozen_sources, monkeypatch
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=frozen_sources.config_bytes,
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
            sources=frozen_sources,
            outcome=_outcome(selected=False),
            receipt=receipt,
            software=_software(),
        )
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_manifest_requires_pinned_hep_ml_version(
    tmp_path: Path, frozen_sources
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=frozen_sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )

    with pytest.raises(ValueError, match="hep_ml 0.8.0"):
        training_run.publish_decorrelation_manifest(
            layout=layout,
            sources=frozen_sources,
            outcome=_outcome(selected=False),
            receipt=receipt,
            software={**_software(), "hep_ml": "0.8.1"},
        )
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_manifest_requires_exact_software_inventory(
    tmp_path: Path, frozen_sources
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=frozen_sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )
    software = {**_software(), "unexpected": "1.0"}

    with pytest.raises(ValueError, match="software.*approved contract"):
        training_run.publish_decorrelation_manifest(
            layout=layout,
            sources=frozen_sources,
            outcome=_outcome(selected=False),
            receipt=receipt,
            software=software,
        )
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_manifest_is_newer_than_every_published_artifact(
    tmp_path: Path, frozen_sources
):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=frozen_sources.config_bytes,
        artifacts=_artifacts(selected=False),
    )
    manifest = training_run.publish_decorrelation_manifest(
        layout=layout,
        sources=frozen_sources,
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


def _real_hep_ml_task4a_run(tmp_path: Path) -> Path:
    from tests.test_full_training_run import _synthetic_task4a_run
    from src.full_training_policy import development_fold

    run = _synthetic_task4a_run(tmp_path)
    counts = {(fold, label): 0 for fold in range(5) for label in (0, 1)}
    label_ordinals = {0: 0, 1: 0}
    rows: list[dict[str, object]] = []
    event_number = 1

    def feature_values(event: int) -> dict[str, float]:
        return {
            feature: float(
                np.sin(event * (index + 1) * 0.013)
                + 0.5 * np.cos(event * 0.007 + index)
            )
            for index, feature in enumerate(_ALL_MC_FEATURES)
        }

    while min(counts.values()) < 110:
        for label in (0, 1):
            channel = 363490 if label == 0 else 345060
            fold = development_fold(channel, event_number, folds=5)
            bucket = (fold, label)
            if counts[bucket] >= 110:
                continue
            ordinal = label_ordinals[label]
            row: dict[str, object] = feature_values(event_number)
            row.update(
                {
                    "eventNumber": event_number,
                    "channelNumber": channel,
                    "split": "train" if counts[bucket] % 2 == 0 else "validation",
                    "label": label,
                    "physical_weight": (
                        -0.75 if event_number % 13 == 0 else 1.0 + 0.25 * label
                    ),
                    "m4l": (
                        105.0 + 55.0 * ((ordinal * 17) % 111) / 110.0
                        if label == 0
                        else 125.0 + 1.5 * np.sin(ordinal * 0.19)
                    ),
                }
            )
            rows.append(row)
            counts[bucket] += 1
            label_ordinals[label] += 1
        event_number += 1

    for label in (0, 1):
        channel = 363490 if label == 0 else 345060
        for offset in range(20):
            event = 10_000_000 + label * 1_000 + offset
            row = feature_values(event)
            row.update(
                {
                    "eventNumber": event,
                    "channelNumber": channel,
                    "split": "test",
                    "label": label,
                    "physical_weight": -0.5 if offset % 9 == 0 else 1.0,
                    "m4l": (
                        105.0 + 55.0 * offset / 19.0
                        if label == 0
                        else 125.0 + np.sin(offset)
                    ),
                }
            )
            rows.append(row)

    frame = pd.DataFrame(rows)
    assert counts == {(fold, label): 110 for fold in range(5) for label in (0, 1)}
    background_development = frame.loc[
        (frame["label"] == 0) & frame["split"].isin(("train", "validation"))
    ]
    mass_grid = background_development["m4l"].to_numpy(dtype=float)
    unique_masses = np.unique(mass_grid)
    assert len(unique_masses) == 111
    np.testing.assert_allclose(unique_masses, np.linspace(105.0, 160.0, 111))
    first_cycle_indices = np.rint((mass_grid[:111] - 105.0) * 2.0).astype(int)
    assert set(first_cycle_indices) == set(range(111))
    assert abs(np.corrcoef(np.arange(111), first_cycle_indices)[0, 1]) < 0.02
    feature_mass_correlations = (
        background_development.loc[:, [*_FEATURES, "m4l"]]
        .corr()["m4l"]
        .drop("m4l")
        .abs()
    )
    assert float(feature_mass_correlations.max()) < 0.03
    for label in (0, 1):
        assert set(frame.loc[frame["label"] == label, "split"]) == {
            "train",
            "validation",
            "test",
        }
    frame.to_csv(run / "processed/mc_events.csv.gz", index=False)
    summary_path = run / "artifacts/data_summary.json"
    summary = json.loads(summary_path.read_text())
    summary["mc"]["higgs"]["selected_events"] = int(
        (frame["label"] == 1).sum()
    )
    summary["mc"]["zz"]["selected_events"] = int(
        (frame["label"] == 0).sum()
    )
    summary_path.write_text(json.dumps(summary, sort_keys=True))
    return run


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


def _strict_sources():
    return training_run.resolve_decorrelation_sources(
        input_run=Path("runs/full-baseline-363490-2026-08-11-r2"),
        config_path=Path("config/decorrelation_training_drop_top4.yaml"),
    )


def _publish_no_selection(tmp_path: Path, sources):
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
    return layout


def _publish_selection(tmp_path: Path, sources, model):
    layout = training_run.claim_decorrelation_output(_fresh_layout(tmp_path))
    receipt = training_run.write_decorrelation_artifacts(
        layout=layout,
        config_bytes=sources.config_bytes,
        artifacts=_artifacts(selected=True, model=model),
    )
    training_run.publish_decorrelation_manifest(
        layout=layout,
        sources=sources,
        outcome=_outcome(selected=True),
        receipt=receipt,
        software=_software(),
    )
    return layout


def _replace_output_and_rebind_manifest(
    layout, relative: str, payload: bytes
) -> None:
    output = layout.run_dir / relative
    output.write_bytes(payload)
    record: dict[str, object] = {
        "path": str(output),
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    if relative.endswith(".csv") or relative.endswith(".csv.gz"):
        record["row_count"] = len(pd.read_csv(output))
    manifest_path = layout.artifacts_dir / "study_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["outputs"][relative] = record
    manifest_path.write_text(json.dumps(manifest))


def _reachable_authorization_registries() -> list[dict]:
    return [
        value
        for name, value in vars(training_run).items()
        if "AUTHORIZ" in name.upper() and isinstance(value, dict)
    ]


def _reachable_authorization_token(layout) -> object:
    for registry in _reachable_authorization_registries():
        for authorization in registry.values():
            if getattr(authorization, "layout", None) is layout and hasattr(
                authorization, "token"
            ):
                return authorization.token
    return object()


def _rebind_reachable_completion_authorization(layout) -> None:
    manifest = (layout.artifacts_dir / "study_manifest.json").read_bytes()
    model = (layout.model_dir / "flatness_model.pkl").read_bytes()
    for registry in _reachable_authorization_registries():
        for authorization in registry.values():
            if getattr(authorization, "layout", None) is not layout:
                continue
            if hasattr(authorization, "completion_manifest_sha256"):
                authorization.completion_manifest_sha256 = hashlib.sha256(
                    manifest
                ).hexdigest()
            if hasattr(authorization, "completion_model_sha256"):
                authorization.completion_model_sha256 = hashlib.sha256(
                    model
                ).hexdigest()
            if hasattr(authorization, "completion_selected"):
                authorization.completion_selected = True


def _clear_reachable_authorization_registries() -> None:
    for registry in _reachable_authorization_registries():
        registry.clear()


def _write_manual_selected_outputs(
    layout,
    *,
    config_bytes: bytes,
    artifacts: dict[str, object],
) -> None:
    plots = artifacts["plot_artifacts"]
    payloads = {
        "config.yaml": config_bytes,
        "artifacts/candidate_results.csv": artifacts[
            "candidate_results"
        ].to_csv(index=False).encode("utf-8"),
        "artifacts/working_point_metrics.csv": artifacts[
            "working_point_metrics"
        ].to_csv(index=False).encode("utf-8"),
        "artifacts/selection.json": json.dumps(
            artifacts["selection"], sort_keys=True
        ).encode("utf-8"),
        "artifacts/test_metrics.json": json.dumps(
            artifacts["test_metrics"], sort_keys=True
        ).encode("utf-8"),
        "model/flatness_model.pkl": b"not-a-trusted-hep-ml-pickle",
        "predictions/oof_scores.csv.gz": gzip.compress(
            artifacts["oof_scores"].to_csv(index=False).encode("utf-8"),
            mtime=0,
        ),
        "predictions/selected_oof_scores.csv.gz": gzip.compress(
            artifacts["selected_oof_scores"].to_csv(index=False).encode("utf-8"),
            mtime=0,
        ),
        "predictions/test_scores.csv.gz": gzip.compress(
            artifacts["test_scores"].to_csv(index=False).encode("utf-8"),
            mtime=0,
        ),
        "plots/candidate_tradeoff.png": b"not-a-decodable-png",
        "plots/working_point_ks.png": plots["working_point_ks.png"],
        "plots/selected_mass_sculpting.png": plots[
            "selected_mass_sculpting.png"
        ],
    }
    for relative, payload in payloads.items():
        (layout.run_dir / relative).write_bytes(payload)


def _filesystem_output_records(layout, selected: bool):
    relative_paths = {
        "config.yaml",
        *_COMMON_ARTIFACTS,
        *(_SELECTED_ARTIFACTS if selected else set()),
    }
    records = {}
    for relative in relative_paths:
        path = layout.run_dir / relative
        payload = path.read_bytes()
        record = {
            "path": str(path),
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        if relative.endswith(".csv") or relative.endswith(".csv.gz"):
            record["row_count"] = len(pd.read_csv(path))
        records[relative] = record
    return records


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
    coefficients = [0.0, 0.5, 1.0, 2.0, 3.0]
    candidates = [f"lambda_{str(value).replace('.', 'p')}" for value in coefficients]
    eligible = [False, False, selected, False, False]
    maximum_ks = [0.2, 0.2, 0.08 if selected else 0.2, 0.2, 0.2]
    aucs = [0.79, 0.78, 0.82 if selected else 0.79, 0.77, 0.76]
    ineligible_reasons = ",".join(
        (
            "weighted_auc_below_floor",
            "loose_zz_mass_ks_exceeds_limit",
            "medium_zz_mass_ks_exceeds_limit",
            "tight_zz_mass_ks_exceeds_limit",
            "loose_signal_efficiency_not_above_background",
            "medium_signal_efficiency_not_above_background",
            "tight_signal_efficiency_not_above_background",
        )
    )
    candidate_results = pd.DataFrame(
        {
            "candidate": candidates,
            "coefficient": coefficients,
            "weighted_oof_auc": aucs,
            "maximum_oof_zz_ks": maximum_ks,
            "background_score_mass_correlation": [-0.2] * 5,
            "eligible": eligible,
            "eligibility_reasons": [
                "" if value else ineligible_reasons for value in eligible
            ],
        }
    )
    point_rows = []
    for candidate, coefficient, is_eligible, candidate_ks in zip(
        candidates, coefficients, eligible, maximum_ks
    ):
        for point, threshold, target, signal_efficiency in zip(
            ("loose", "medium", "tight"),
            (0.25, 0.5, 0.75),
            (0.5, 0.2, 0.1),
            (0.8, 0.5, 0.3) if is_eligible else (0.4, 0.1, 0.05),
        ):
            point_rows.append(
                {
                    "candidate": candidate,
                    "coefficient": coefficient,
                    "working_point": point,
                    "threshold": threshold,
                    "target_background_efficiency": target,
                    "achieved_background_efficiency": target,
                    "signal_efficiency": signal_efficiency,
                    "zz_mass_ks_distance": candidate_ks,
                }
            )
    oof_scores = pd.DataFrame(
        {
            "eventNumber": [1, 2],
            "channelNumber": [363490, 345060],
            "split": ["train", "validation"],
            "label": [0, 1],
            "physical_weight": [1.0, 1.0],
            "m4l": [120.0, 130.0],
            "development_fold": [0, 1],
            "score_lambda_0p0": [0.2, 0.8],
            "score_lambda_0p5": [0.25, 0.75],
            "score_lambda_1p0": [0.3, 0.7],
            "score_lambda_2p0": [0.35, 0.65],
            "score_lambda_3p0": [0.4, 0.6],
        }
    )
    artifacts: dict[str, object] = {
        "candidate_results": candidate_results,
        "working_point_metrics": pd.DataFrame(point_rows),
        "selection": selection,
        "oof_scores": oof_scores,
        "plot_artifacts": {
            "candidate_tradeoff.png": _VALID_PNG,
            "working_point_ks.png": _VALID_PNG,
        },
        "model": None,
        "selected_oof_scores": None,
        "test_scores": None,
        "test_metrics": None,
    }
    if selected:
        artifacts.update(
            model=model,
            selected_oof_scores=oof_scores.loc[:, list(_AUDIT_COLUMNS)]
            .copy()
            .assign(oof_score=oof_scores["score_lambda_1p0"]),
            test_scores=pd.DataFrame(
                {
                    "eventNumber": [3, 4, 5, 6, 7, 8, 9, 10],
                    "channelNumber": [363490] * 4 + [345060] * 4,
                    "split": ["test"] * 8,
                    "label": [0] * 4 + [1] * 4,
                    "physical_weight": [1.0] * 8,
                    "m4l": [
                        110.0,
                        120.0,
                        140.0,
                        150.0,
                        111.0,
                        125.0,
                        143.0,
                        158.0,
                    ],
                    "score": [0.2, 0.4, 0.6, 0.8, 0.3, 0.55, 0.85, 0.95],
                }
            ),
            test_metrics={
                "schema_version": "1.0",
                "weighted_auc": 0.6875,
                "background_score_mass_correlation": 0.9899494936611665,
                "working_points": {
                    name: {
                        "threshold": threshold,
                        "target_background_efficiency": target,
                        "achieved_background_efficiency": background,
                        "signal_efficiency": signal,
                    }
                    for name, threshold, target, background, signal in zip(
                        ("loose", "medium", "tight"),
                        (0.25, 0.5, 0.75),
                        (0.5, 0.2, 0.1),
                        (0.75, 0.5, 0.25),
                        (1.0, 0.75, 0.5),
                    )
                },
                "zz_ks_distances": {
                    "loose": 0.25,
                    "medium": 0.5,
                    "tight": 0.75,
                },
            },
        )
        artifacts["plot_artifacts"][
            "selected_mass_sculpting.png"
        ] = _VALID_PNG
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
    return {
        "python": "test",
        "numpy": "test",
        "pandas": "test",
        "pyyaml": "test",
        "uproot": "test",
        "xgboost": "test",
        "scikit-learn": "test",
        "hep_ml": "0.8.0",
    }


def _published_files(run_dir: Path) -> set[str]:
    return {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file()
    }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
