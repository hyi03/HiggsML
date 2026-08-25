from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts import run_decorrelation_training
from scripts.run_decorrelation_training import build_decorrelation_artifacts
from src import decorrelation_training_run as training_run
from src.decorrelation_training import (
    FlatnessOutcome,
    FlatnessSelection,
    SelectedFlatnessEvidence,
    evaluate_flatness_candidate,
)
from src.decorrelation_training_run import load_decorrelation_config


@pytest.fixture
def config():
    return load_decorrelation_config(
        Path("config/decorrelation_training_drop_top4.yaml")
    )


def _recorded_cli_stages(monkeypatch, *, selected: bool) -> list[str]:
    stages: list[str] = []
    software_inventory = {"hep_ml": "0.8.0"}
    unresolved = SimpleNamespace(run_dir=Path("out"), directory_identities=None)
    claimed = SimpleNamespace(
        run_dir=Path("out"), directory_identities={".": (1, 2)}
    )
    chosen = SimpleNamespace(coefficient=0.5) if selected else None
    selection = SimpleNamespace(selected=chosen)
    outcome = SimpleNamespace(
        selection=selection,
        evidence=object() if selected else None,
    )
    sources = SimpleNamespace(
        training_input=SimpleNamespace(input_run=Path("input")),
        config=object(),
        config_bytes=b"config",
    )
    partitions = SimpleNamespace(
        development=object(),
        open_test=lambda: stages.append("selected_test_gate") or pd.DataFrame(),
    )
    resolve_count = 0

    def resolve_output(**kwargs):
        nonlocal resolve_count
        stage = "output_preflight" if resolve_count == 0 else "output_rebind"
        resolve_count += 1
        stages.append(stage)
        return unresolved

    def score_test(development, test_gate, config, observed_selection):
        assert observed_selection is selection
        if observed_selection.selected is not None:
            test_gate.open()
        return outcome

    def dependency_preflight(config, software):
        assert software is software_inventory
        stages.append("dependency_preflight")

    def publish_manifest(**kwargs):
        assert kwargs["software"] is software_inventory
        stages.append("publish_manifest")
        return {}

    monkeypatch.setattr(
        run_decorrelation_training,
        "resolve_decorrelation_output",
        resolve_output,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "resolve_decorrelation_sources",
        lambda **kwargs: stages.append("source_resolve") or sources,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "claim_decorrelation_output",
        lambda layout: stages.append("output_claim") or claimed,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "preflight_decorrelation_dependencies",
        dependency_preflight,
        raising=False,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "load_training_mc_frame",
        lambda training_input: stages.append("mc_load") or object(),
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "bind_source_row_ids",
        lambda frame: stages.append("source_row_bind") or frame,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "MCStudyPartitions",
        SimpleNamespace(
            from_frame=lambda frame: stages.append("partition") or partitions
        ),
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "run_development_study",
        lambda development, config: stages.append("development_study")
        or selection,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "build_decorrelation_development_artifacts",
        lambda observed, config: stages.append("build_development_artifacts")
        or {
            "candidate_results": object(),
            "working_point_metrics": object(),
            "oof_scores": object(),
        },
        raising=False,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "validate_decorrelation_development_artifacts",
        lambda **kwargs: stages.append("validate_development_artifacts"),
        raising=False,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "fit_selected_and_score_test",
        score_test,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "build_decorrelation_artifacts",
        lambda observed, config: stages.append("build_artifacts")
        or {
            "selection": {
                "status": (
                    "eligible_candidate_test_reported"
                    if selected
                    else "no_eligible_candidate"
                ),
                "selected_candidate": "lambda_0p5" if selected else None,
                "test_opened": selected,
            }
        },
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "write_decorrelation_artifacts",
        lambda **kwargs: stages.append("write_artifacts") or object(),
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "assert_decorrelation_sources_unchanged",
        lambda observed: stages.append("source_recheck"),
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "publish_decorrelation_manifest",
        publish_manifest,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "software_versions",
        lambda: stages.append("software_inventory") or software_inventory,
    )

    assert run_decorrelation_training.main(
        ["--input-run", "in", "--config", "cfg", "--run-dir", "out"]
    ) == 0
    return stages


def test_cli_runs_frozen_stages_in_order(monkeypatch):
    assert _recorded_cli_stages(monkeypatch, selected=True) == [
        "output_preflight",
        "source_resolve",
        "output_rebind",
        "software_inventory",
        "dependency_preflight",
        "output_claim",
        "mc_load",
        "source_row_bind",
        "partition",
        "development_study",
        "build_development_artifacts",
        "validate_development_artifacts",
        "selected_test_gate",
        "build_artifacts",
        "write_artifacts",
        "source_recheck",
        "publish_manifest",
    ]


def test_no_selection_skips_selected_test_gate(monkeypatch):
    assert _recorded_cli_stages(monkeypatch, selected=False) == [
        "output_preflight",
        "source_resolve",
        "output_rebind",
        "software_inventory",
        "dependency_preflight",
        "output_claim",
        "mc_load",
        "source_row_bind",
        "partition",
        "development_study",
        "build_development_artifacts",
        "validate_development_artifacts",
        "build_artifacts",
        "write_artifacts",
        "source_recheck",
        "publish_manifest",
    ]


def test_occupied_output_fails_before_source_resolution(monkeypatch):
    monkeypatch.setattr(
        run_decorrelation_training,
        "resolve_decorrelation_output",
        lambda **kwargs: (_ for _ in ()).throw(FileExistsError("occupied")),
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "resolve_decorrelation_sources",
        lambda **kwargs: pytest.fail("sources must remain unopened"),
    )

    with pytest.raises(FileExistsError, match="occupied"):
        run_decorrelation_training.main(
            ["--input-run", "in", "--config", "cfg", "--run-dir", "out"]
        )


@pytest.mark.parametrize(
    "dependency_error",
    (
        RuntimeError("hep_ml is unavailable"),
        ValueError("hep_ml must be exactly 0.8.0"),
        RuntimeError("hep_ml API is incompatible"),
    ),
)
def test_dependency_preflight_failure_leaves_requested_output_absent(
    tmp_path: Path,
    monkeypatch,
    dependency_error: Exception,
):
    """Moving dependency/API validation after output claim must fail."""
    unresolved = run_decorrelation_training.resolve_decorrelation_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=tmp_path / "input",
        run_dir=tmp_path / "study",
    )
    sources = SimpleNamespace(
        training_input=SimpleNamespace(input_run=tmp_path / "input"),
        config=object(),
        config_bytes=b"config",
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "resolve_decorrelation_output",
        lambda **kwargs: unresolved,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "resolve_decorrelation_sources",
        lambda **kwargs: sources,
    )
    monkeypatch.setattr(run_decorrelation_training, "software_versions", lambda: {})
    monkeypatch.setattr(
        run_decorrelation_training,
        "preflight_decorrelation_dependencies",
        lambda config, software: (_ for _ in ()).throw(dependency_error),
        raising=False,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "claim_decorrelation_output",
        lambda layout: pytest.fail("output must not be claimed"),
    )

    with pytest.raises(type(dependency_error), match=str(dependency_error)):
        run_decorrelation_training.main(
            ["--input-run", "in", "--config", "cfg", "--run-dir", "out"]
        )

    assert not unresolved.run_dir.exists()


def test_post_claim_error_installs_failure(tmp_path: Path, monkeypatch):
    from src import decorrelation_training_run as training_run

    unresolved = training_run.resolve_decorrelation_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=tmp_path / "input",
        run_dir=tmp_path / "study",
    )
    sources = SimpleNamespace(
        training_input=SimpleNamespace(input_run=tmp_path / "input"),
        config=object(),
        config_bytes=b"config",
    )
    partitions = SimpleNamespace(development=object(), open_test=lambda: None)
    monkeypatch.setattr(
        run_decorrelation_training,
        "resolve_decorrelation_output",
        lambda **kwargs: unresolved,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "resolve_decorrelation_sources",
        lambda **kwargs: sources,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "claim_decorrelation_output",
        training_run.claim_decorrelation_output,
    )
    monkeypatch.setattr(run_decorrelation_training, "software_versions", lambda: {})
    monkeypatch.setattr(
        run_decorrelation_training,
        "preflight_decorrelation_dependencies",
        lambda config, software: None,
    )
    monkeypatch.setattr(
        run_decorrelation_training, "load_training_mc_frame", lambda value: object()
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "bind_source_row_ids",
        lambda frame: frame,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "MCStudyPartitions",
        SimpleNamespace(from_frame=lambda frame: partitions),
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "run_development_study",
        lambda development, config: (_ for _ in ()).throw(
            RuntimeError("study failed")
        ),
    )

    with pytest.raises(RuntimeError, match="study failed"):
        run_decorrelation_training.main(
            ["--input-run", "in", "--config", "cfg", "--run-dir", "out"]
        )

    assert (unresolved.run_dir / ".terminal.failed").is_dir()
    assert (unresolved.run_dir / "failure.json").is_file()


def test_post_claim_print_error_installs_failure(tmp_path: Path, monkeypatch):
    from src import decorrelation_training_run as training_run

    unresolved = training_run.resolve_decorrelation_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=tmp_path / "input",
        run_dir=tmp_path / "study",
    )
    selection = SimpleNamespace(selected=None)
    outcome = SimpleNamespace(selection=selection, evidence=None)
    sources = SimpleNamespace(
        training_input=SimpleNamespace(input_run=tmp_path / "input"),
        config=object(),
        config_bytes=b"config",
    )
    partitions = SimpleNamespace(development=object(), open_test=lambda: None)
    artifacts = {
        "selection": {
            "status": "no_eligible_candidate",
            "selected_candidate": None,
            "test_opened": False,
        }
    }
    monkeypatch.setattr(
        run_decorrelation_training,
        "resolve_decorrelation_output",
        lambda **kwargs: unresolved,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "resolve_decorrelation_sources",
        lambda **kwargs: sources,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "claim_decorrelation_output",
        training_run.claim_decorrelation_output,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "preflight_decorrelation_dependencies",
        lambda config, software: None,
    )
    monkeypatch.setattr(
        run_decorrelation_training, "load_training_mc_frame", lambda value: object()
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "bind_source_row_ids",
        lambda frame: frame,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "MCStudyPartitions",
        SimpleNamespace(from_frame=lambda frame: partitions),
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "run_development_study",
        lambda development, config: selection,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "build_decorrelation_development_artifacts",
        lambda observed, config: {
            "candidate_results": object(),
            "working_point_metrics": object(),
            "oof_scores": object(),
        },
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "validate_decorrelation_development_artifacts",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "fit_selected_and_score_test",
        lambda development, gate, config, observed: outcome,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "build_decorrelation_artifacts",
        lambda observed, config: artifacts,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "write_decorrelation_artifacts",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "assert_decorrelation_sources_unchanged",
        lambda observed: None,
    )
    monkeypatch.setattr(
        run_decorrelation_training,
        "publish_decorrelation_manifest",
        lambda **kwargs: pytest.fail("printing must succeed before publication"),
    )
    monkeypatch.setattr(run_decorrelation_training, "software_versions", lambda: {})
    monkeypatch.setattr(
        "builtins.print",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("stdout failed")),
    )

    with pytest.raises(OSError, match="stdout failed"):
        run_decorrelation_training.main(
            ["--input-run", "in", "--config", "cfg", "--run-dir", "out"]
        )

    assert (unresolved.run_dir / ".terminal.failed").is_dir()
    assert (unresolved.run_dir / "failure.json").is_file()


def test_parser_exposes_only_frozen_paths():
    parser = run_decorrelation_training._build_parser()

    assert {action.dest for action in parser._actions} == {
        "help",
        "input_run",
        "config",
        "run_dir",
    }


@pytest.mark.parametrize("flag", ("--data", "--test", "--model"))
def test_parser_rejects_unapproved_paths(flag: str):
    with pytest.raises(SystemExit) as error:
        run_decorrelation_training._build_parser().parse_args(
            [
                "--input-run",
                "in",
                "--config",
                "cfg",
                "--run-dir",
                "out",
                flag,
                "attacker-controlled",
            ]
        )

    assert error.value.code == 2


def _audit(coefficient: float, *, reverse: bool = False) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "source_row_id": np.arange(8, dtype=np.int64),
            "eventNumber": [11, 12, 13, 14, 21, 22, 23, 24],
            "channelNumber": [363490] * 4 + [345060] * 4,
            "split": ["train", "validation"] * 4,
            "label": [0, 0, 0, 0, 1, 1, 1, 1],
            "physical_weight": [1.0, -0.5, 1.5, 2.0, 1.0, 2.0, -1.0, 0.5],
            "m4l": [108.0, 121.0, 139.0, 154.0, 111.0, 125.0, 143.0, 158.0],
            "development_fold": [0, 1, 2, 3, 4, 0, 1, 2],
            f"score_lambda_{str(float(coefficient)).replace('.', 'p')}": np.asarray(
                [0.30, 0.60, 0.80, 0.95, 0.20, 0.55, 0.85, 0.98]
            )
            + coefficient / 100.0,
        }
    )
    return frame.iloc[::-1].copy(deep=True) if reverse else frame


def _candidate(config, coefficient, *, eligible: bool, reverse: bool = False):
    audit = _audit(coefficient)
    score_column = f"score_lambda_{str(float(coefficient)).replace('.', 'p')}"
    shift = coefficient / 100.0
    audit.loc[:, score_column] = np.asarray(
        [0.2] * 4 + [0.8] * 4 if eligible else [0.8] * 4 + [0.2] * 4
    ) + shift
    if reverse:
        audit = audit.iloc[::-1].copy(deep=True)
    return evaluate_flatness_candidate(
        audit,
        config=config,
        coefficient=coefficient,
    )


def _outcome(
    config, *, selected: bool, empty_test_selection: bool = False
) -> FlatnessOutcome:
    results = tuple(
        _candidate(
            config,
            coefficient,
            eligible=selected and coefficient == 1.0,
            reverse=coefficient == 0.5,
        )
        for coefficient in config.coefficients
    )
    chosen = results[2] if selected else None
    selection = FlatnessSelection(results=results, selected=chosen)
    if chosen is None:
        return FlatnessOutcome(selection=selection, evidence=None)
    test_scores = pd.DataFrame(
        {
            "source_row_id": np.arange(8, 16, dtype=np.int64),
            "eventNumber": [101, 102, 103, 104, 201, 202, 203, 204],
            "channelNumber": [363490] * 4 + [345060] * 4,
            "split": ["test"] * 8,
            "label": [0, 0, 0, 0, 1, 1, 1, 1],
            "physical_weight": [1.0, -0.5, 1.5, 2.0, 1.0, 2.0, -1.0, 0.5],
            "m4l": [109.0, 122.0, 140.0, 155.0, 112.0, 126.0, 144.0, 157.0],
            "score": [0.1 if empty_test_selection else 0.3] * 4 + [0.8] * 4,
        }
    )
    test_background_efficiency = 0.0 if empty_test_selection else 1.0
    test_points = {
        name: {
            **dict(chosen.working_points[name]),
            "achieved_background_efficiency": test_background_efficiency,
            "signal_efficiency": 1.0,
        }
        for name in ("loose", "medium", "tight")
    }
    test_distance = None if empty_test_selection else 0.0
    evidence = SelectedFlatnessEvidence(
        candidate=chosen,
        model=SimpleNamespace(name="frozen-flatness-model"),
        test_scores=test_scores,
        test_weighted_auc=1.0,
        test_background_score_mass_correlation=0.0,
        working_points=chosen.working_points,
        test_working_points=test_points,
        test_background_efficiencies={
            name: test_points[name]["achieved_background_efficiency"]
            for name in test_points
        },
        test_signal_efficiencies={
            name: test_points[name]["signal_efficiency"] for name in test_points
        },
        test_zz_ks_distances={
            name: test_distance for name in ("loose", "medium", "tight")
        },
        test_zz_diagnostics={
            "working_points": {
                name: {"inclusive_to_selected_ks_distance": test_distance}
                for name in ("loose", "medium", "tight")
            }
        },
    )
    return FlatnessOutcome(selection=selection, evidence=evidence)


def test_no_selection_artifacts_include_all_oof_audits_and_no_test(config):
    """Omitting a coefficient score or leaking selected/test evidence must fail."""
    artifacts = build_decorrelation_artifacts(_outcome(config, selected=False), config)

    assert artifacts["selection"] == {
        "schema_version": "1.0",
        "status": "no_eligible_candidate",
        "selected_candidate": None,
        "test_opened": False,
        "auc_floor": 0.80,
        "ks_limit": 0.10,
    }
    assert set(artifacts["plot_artifacts"]) == {
        "candidate_tradeoff.png",
        "working_point_ks.png",
    }
    assert list(artifacts["oof_scores"].columns) == [
        "source_row_id",
        "eventNumber",
        "channelNumber",
        "split",
        "label",
        "physical_weight",
        "m4l",
        "development_fold",
        "score_lambda_0p0",
        "score_lambda_0p5",
        "score_lambda_1p0",
        "score_lambda_2p0",
        "score_lambda_3p0",
    ]
    event_12 = artifacts["oof_scores"].set_index("eventNumber").loc[12]
    assert event_12["score_lambda_0p5"] == 0.805
    assert artifacts["model"] is None
    assert artifacts["selected_oof_scores"] is None
    assert artifacts["test_scores"] is None
    assert artifacts["test_metrics"] is None


@pytest.mark.parametrize(
    ("selected", "expected_winner"),
    ((False, None), (True, "lambda_1p0")),
)
def test_artifact_builder_tables_are_recomputable_from_oof_evidence(
    config,
    selected: bool,
    expected_winner: str | None,
):
    """Hand-written candidate summaries that disagree with OOF must fail."""
    artifacts = build_decorrelation_artifacts(
        _outcome(config, selected=selected),
        config,
    )

    winner = training_run._validate_candidate_metrics_from_oof(
        artifacts["candidate_results"],
        artifacts["working_point_metrics"],
        artifacts["oof_scores"],
        config,
    )

    assert winner == expected_winner


def test_artifact_tables_preserve_evaluated_metrics_and_ordered_reasons(config):
    """Replacing evaluated metrics or reordering reasons must fail the contract."""
    artifacts = build_decorrelation_artifacts(_outcome(config, selected=False), config)

    candidates = artifacts["candidate_results"]
    assert candidates["candidate"].tolist() == [
        "lambda_0p0",
        "lambda_0p5",
        "lambda_1p0",
        "lambda_2p0",
        "lambda_3p0",
    ]
    assert candidates.loc[0, "background_score_mass_correlation"] == 0.0
    assert candidates.loc[0, "eligibility_reasons"] == (
        "weighted_auc_below_floor,"
        "loose_signal_efficiency_not_above_background,"
        "medium_signal_efficiency_not_above_background,"
        "tight_signal_efficiency_not_above_background"
    )
    metrics = artifacts["working_point_metrics"]
    assert len(metrics) == 15
    assert (
        metrics.groupby("candidate", sort=False)["working_point"]
        .apply(tuple)
        .tolist()
        == [("loose", "medium", "tight")] * 5
    )
    assert metrics.loc[0, "zz_mass_ks_distance"] == 0.0


def test_selected_artifacts_report_test_without_reselecting(config):
    """Selected artifacts must retain the OOF winner and frozen thresholds."""
    outcome = _outcome(config, selected=True)
    artifacts = build_decorrelation_artifacts(outcome, config)

    assert artifacts["selection"]["status"] == "eligible_candidate_test_reported"
    assert artifacts["selection"]["selected_candidate"] == "lambda_1p0"
    assert artifacts["selection"]["test_opened"] is True
    assert set(artifacts["plot_artifacts"]) == {
        "candidate_tradeoff.png",
        "working_point_ks.png",
        "selected_mass_sculpting.png",
    }
    assert artifacts["model"] is outcome.evidence.model
    assert artifacts["selected_oof_scores"]["oof_score"].equals(
        outcome.selection.selected.oof_scores["score_lambda_1p0"]
    )
    pd.testing.assert_frame_equal(
        artifacts["test_scores"], outcome.evidence.test_scores
    )
    assert artifacts["test_metrics"]["weighted_auc"] == 1.0
    assert artifacts["test_metrics"]["working_points"]["tight"]["threshold"] == (
        0.21000000000000002
    )
    assert artifacts["test_metrics"]["zz_ks_distances"] == {
        "loose": 0.0,
        "medium": 0.0,
        "tight": 0.0,
    }


def test_selected_artifacts_preserve_empty_test_working_point(config):
    """An empty frozen test selection is evidence, not a software failure."""
    outcome = _outcome(config, selected=True, empty_test_selection=True)

    artifacts = build_decorrelation_artifacts(outcome, config)

    assert artifacts["selection"]["status"] == "eligible_candidate_test_reported"
    assert artifacts["test_metrics"]["zz_ks_distances"]["tight"] is None
    assert artifacts["plot_artifacts"]["selected_mass_sculpting.png"].startswith(
        b"\x89PNG\r\n\x1a\n"
    )


def test_wide_oof_audit_rejects_contradictory_identity_evidence(config):
    """A score from a row with changed mass must not be silently joined by position."""
    outcome = _outcome(config, selected=False)
    outcome.selection.results[1].oof_scores.loc[
        outcome.selection.results[1].oof_scores.index[0], "m4l"
    ] = 999.0

    with pytest.raises(ValueError, match="contradictory OOF audit"):
        build_decorrelation_artifacts(outcome, config)


@pytest.mark.parametrize("invalid_source_row_id", (0.5, np.inf))
def test_wide_oof_audit_rejects_non_integer_source_row_ordinals(
    config,
    invalid_source_row_id: float,
):
    """Allowing fractional or non-finite row ordinals must fail."""
    outcome = _outcome(config, selected=False)
    for result in outcome.selection.results:
        source_ids = result.oof_scores["source_row_id"].astype(float)
        source_ids.loc[0] = invalid_source_row_id
        result.oof_scores["source_row_id"] = source_ids

    with pytest.raises(ValueError, match="source_row_id|row ordinal"):
        build_decorrelation_artifacts(outcome, config)


def test_wide_oof_audit_joins_source_shaped_collisions_by_csv_row_ordinal(config):
    """Joining candidate scores on the non-unique event tuple must fail."""
    results = []
    for coefficient in config.coefficients:
        audit = _audit(coefficient)
        audit.loc[
            1,
            ["channelNumber", "eventNumber", "split"],
        ] = audit.loc[
            0,
            ["channelNumber", "eventNumber", "split"],
        ].to_numpy()
        if coefficient == 0.5:
            audit = audit.iloc[::-1].copy(deep=True)
        results.append(SimpleNamespace(coefficient=coefficient, oof_scores=audit))

    wide = run_decorrelation_training._wide_oof_audit(tuple(results))

    assert wide["source_row_id"].tolist() == list(range(8))
    collision = wide.loc[
        (wide["channelNumber"] == wide.loc[0, "channelNumber"])
        & (wide["eventNumber"] == wide.loc[0, "eventNumber"])
        & (wide["split"] == wide.loc[0, "split"])
    ]
    assert collision["source_row_id"].tolist() == [0, 1]
    assert collision["score_lambda_0p5"].tolist() == [0.305, 0.605]
