from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from scripts import run_mass_sculpting_ablation

import pytest


def test_cli_module_exposes_main():
    assert callable(run_mass_sculpting_ablation.main)


def test_cli_preflights_and_claims_output_before_input_load(monkeypatch):
    stages = []
    unresolved = SimpleNamespace(run_dir="out", directory_identities=None)
    claimed = SimpleNamespace(run_dir="out", directory_identities={".": (1, 2)})
    sources = SimpleNamespace(
        training_input=SimpleNamespace(input_run="input", expected_rows=1),
        reference_run="reference",
        policy=None,
        reference_summary=_reference_summary(),
        config_bytes=b"config",
        records={"study_config": SimpleNamespace(path="cfg")},
    )
    outcome = SimpleNamespace(selected=None, evidence=None, development_results={})

    resolves = iter((unresolved, unresolved))
    monkeypatch.setattr(
        run_mass_sculpting_ablation,
        "resolve_ablation_output",
        lambda **kwargs: stages.append(
            "output_preflight" if not stages else "output_rebind"
        ) or next(resolves),
    )
    monkeypatch.setattr(
        run_mass_sculpting_ablation,
        "resolve_ablation_sources",
        lambda **kwargs: stages.append("input_resolve") or sources,
    )
    monkeypatch.setattr(
        run_mass_sculpting_ablation,
        "claim_ablation_output",
        lambda layout: stages.append("output_claim") or claimed,
    )
    monkeypatch.setattr(
        run_mass_sculpting_ablation,
        "load_training_mc_frame",
        lambda value: stages.append("input_load") or [object()],
    )
    monkeypatch.setattr(
        run_mass_sculpting_ablation,
        "summarize_mc_source_rows",
        lambda frame, expected: {
            "row_count": 3,
            "rows_by_split": {"train": 1, "validation": 1, "test": 1},
        },
    )
    monkeypatch.setattr(
        run_mass_sculpting_ablation,
        "select_and_score_test",
        lambda frame, policy: stages.append("study") or outcome,
    )
    monkeypatch.setattr(
        run_mass_sculpting_ablation,
        "build_ablation_artifacts",
        lambda outcome, policy, reference_summary: stages.append("build_artifacts")
        or {"selection": {"status": "no_eligible_profile"}},
    )
    monkeypatch.setattr(
        run_mass_sculpting_ablation,
        "write_ablation_artifacts",
        lambda layout, **kwargs: stages.append("write_artifacts") or object(),
    )
    monkeypatch.setattr(
        run_mass_sculpting_ablation,
        "assert_ablation_sources_unchanged",
        lambda value: stages.append("input_recheck"),
    )
    monkeypatch.setattr(
        run_mass_sculpting_ablation,
        "publish_ablation_manifest",
        lambda layout, **kwargs: stages.append("publish_manifest") or {},
    )
    monkeypatch.setattr(run_mass_sculpting_ablation, "software_versions", lambda: {})
    assert run_mass_sculpting_ablation.main(["--input-run", "in", "--reference-run", "ref", "--config", "cfg", "--run-dir", "out"]) == 0
    assert stages == [
        "output_preflight", "input_resolve", "output_rebind", "output_claim",
        "input_load", "study", "build_artifacts", "write_artifacts",
        "input_recheck", "publish_manifest",
    ]


def test_existing_output_refuses_before_source_resolution(monkeypatch):
    monkeypatch.setattr(
        run_mass_sculpting_ablation,
        "resolve_ablation_output",
        lambda **kwargs: (_ for _ in ()).throw(FileExistsError("occupied")),
    )
    monkeypatch.setattr(
        run_mass_sculpting_ablation,
        "resolve_ablation_sources",
        lambda **kwargs: pytest.fail("sources must stay unopened"),
    )
    with pytest.raises(FileExistsError, match="occupied"):
        run_mass_sculpting_ablation.main(
            ["--input-run", "in", "--reference-run", "ref", "--config", "cfg", "--run-dir", "out"]
        )


def test_selected_artifact_builder_classifies_test_nonreproduction():
    points = {
        "loose": {"threshold": 0.2},
        "medium": {"threshold": 0.5},
        "tight": {"threshold": 0.8},
    }
    oof = _score_frame("oof_score")
    test = _score_frame("score")
    result = SimpleNamespace(
        profile=SimpleNamespace(name="shape8", features=("lep1_eta",)),
        candidate_name="depth2_child20",
        final_tree_count=12,
        weighted_auc=0.82,
        score_mass_correlation=0.02,
        working_points=points,
        signal_efficiencies={"loose": 0.9, "medium": 0.8, "tight": 0.7},
        target_background_efficiencies={"loose": 0.5, "medium": 0.2, "tight": 0.1},
        zz_ks_distances={"loose": 0.05, "medium": 0.06, "tight": 0.07},
        eligibility_reasons=(),
        oof_scores=oof,
    )
    evidence = SimpleNamespace(
        model=object(),
        test_scores=test,
        test_weighted_auc=0.84,
        test_zz_diagnostics={
            "working_points": {
                "loose": {"inclusive_to_selected_ks_distance": 0.08},
                "medium": {"inclusive_to_selected_ks_distance": 0.11},
                "tight": {"inclusive_to_selected_ks_distance": 0.09},
            }
        },
    )
    outcome = SimpleNamespace(
        development_results={"shape8": result}, selected=result, evidence=evidence
    )
    artifacts = run_mass_sculpting_ablation.build_ablation_artifacts(
        outcome,
        SimpleNamespace(mass_bins_gev=(105, 120, 135, 160)),
        _reference_summary(),
    )
    assert artifacts["selection"]["status"] == "test_nonreproduction"
    assert artifacts["selection"]["selected_profile"] == "shape8"
    assert set(artifacts["plot_artifacts"]) == {
        "oof_profile_tradeoff.png", "selected_mass_sculpting.png"
    }
    assert artifacts["test_metrics"]["zz_ks_distances"]["medium"] == 0.11
    assert artifacts["selected_oof_scores"] is oof
    assert artifacts["test_scores"] is test
    assert artifacts["profile_results"].iloc[0]["profile"] == "full14_reference"
    assert artifacts["profile_results"].iloc[0]["eligible"] == False


def _score_frame(score_column):
    return pd.DataFrame({
        "label": [0, 0, 0, 1, 1],
        "physical_weight": [1.0, -0.5, 1.5, 1.0, 2.0],
        "m4l": [110.0, 127.0, 150.0, 124.0, 126.0],
        score_column: [0.25, 0.65, 0.95, 0.7, 0.9],
    })


def _reference_summary():
    return {
        "profile": "full14_reference",
        "features": ("lep1_pt", "mZ1"),
        "candidate": "depth4_child20",
        "final_tree_count": 998,
        "weighted_auc": 0.8852959102354316,
        "score_mass_correlation": -0.6335027723645155,
        "working_points": {
            "loose": {
                "threshold": 0.256,
                "signal_efficiency": 0.98,
                "target_background_efficiency": 0.50,
                "zz_ks_distance": 0.291,
            },
            "medium": {
                "threshold": 0.632,
                "signal_efficiency": 0.81,
                "target_background_efficiency": 0.20,
                "zz_ks_distance": 0.408,
            },
            "tight": {
                "threshold": 0.783,
                "signal_efficiency": 0.59,
                "target_background_efficiency": 0.10,
                "zz_ks_distance": 0.458,
            },
        },
        "eligibility_reasons": ("reference_only", "zz_mass_ks_exceeds_limit"),
    }
