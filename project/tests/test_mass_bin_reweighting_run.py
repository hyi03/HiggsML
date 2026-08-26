from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

import src.mass_bin_reweighting_run as mass_bin_reweighting_run

from src.features import FEATURES
from src.full_training_run import TrainingOutputLayout
from src.mass_bin_reweighting_run import (
    StudySource,
    approved_reweighting_artifacts,
    claim_reweighting_output,
    load_mass_bin_reweighting_config,
    policy_manifest_record,
    publish_reweighting_manifest,
    record_reweighting_failure,
    resolve_reweighting_output,
    resolve_reweighting_sources,
    write_reweighting_artifacts,
)


DROP_TOP4 = (
    "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
    "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
)
ANGULAR5_R3_ARM64 = (
    "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
    "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
    "cos_theta_star", "cos_theta_1", "cos_theta_2", "phi_decay_planes",
    "phi_production_plane",
)


NO_SELECTION = {
    "config.yaml",
    "artifacts/iteration_results.csv",
    "artifacts/bin_efficiencies.csv",
    "artifacts/weight_multipliers.csv",
    "artifacts/selection.json",
    "plots/iteration_tradeoff.png",
    "plots/zz_efficiency_by_mass.png",
    "artifacts/study_manifest.json",
}
SELECTED = NO_SELECTION | {
    "artifacts/test_metrics.json",
    "model/xgboost_model.json",
    "predictions/selected_oof_scores.csv.gz",
    "predictions/test_scores.csv.gz",
    "plots/selected_mass_sculpting.png",
}


def test_exact_checked_in_config_binds_all_frozen_decisions():
    config = load_mass_bin_reweighting_config("config/mass_bin_reweighting.yaml")
    assert config.schema_version == "1.0"
    assert config.input_run == "runs/full-baseline-363490-2026-08-11-r2"
    assert config.input_manifest_sha256 == "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8"
    assert config.reference_run == "runs/full-training-363490-2026-08-11-r2"
    assert config.reference_manifest_sha256 == "da015d0a00bb002e69dc98eb9631c1b561af65f8da44b78a641d4e013558bf65"
    assert config.ablation_run == "runs/mass-ablation-363490-2026-08-11"
    assert config.ablation_manifest_sha256 == "5120e6080e82b14f66917ba731c98715fa5d6190c25c396d8c675200e9ca52df"
    assert config.raw_zz_path == "data/raw/zz_363490.root"
    assert config.raw_zz_sha256 == "76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07"
    assert config.features == tuple(FEATURES)
    assert config.mass_bin_edges == tuple(float(x) for x in range(105, 161, 5))
    assert config.minimum_effective_count == 100.0
    assert config.epsilon_floor == 1e-6
    assert config.damping == 0.5
    assert config.round_factor_bounds == (0.5, 2.0)
    assert config.cumulative_bounds == (0.2, 5.0)
    assert config.maximum_corrections == 5
    assert config.auc_floor == 0.80
    assert config.ks_limit == 0.10
    assert config.require_signal_efficiency_above_zz is True
    assert set(config.artifacts_no_selection) == NO_SELECTION
    assert set(config.artifacts_selected) == SELECTED


def test_drop_top4_config_changes_only_the_approved_feature_profile():
    full = load_mass_bin_reweighting_config("config/mass_bin_reweighting.yaml")
    reduced = load_mass_bin_reweighting_config(
        "config/mass_bin_reweighting_drop_top4.yaml"
    )
    assert reduced.schema_version == "1.1"
    assert reduced.features == DROP_TOP4
    assert reduced.reweighting_reference_run == (
        "runs/mass-reweighting-363490-2026-08-11"
    )
    assert reduced.reweighting_reference_manifest_sha256 == (
        "145e38478dfd12310a82f4ed544c6cf0b09204cbc1c7d08e6e485941c00f9e38"
    )
    for name in (
        "mass_bin_edges", "minimum_effective_count", "epsilon_floor",
        "damping", "round_factor_bounds", "cumulative_bounds",
        "maximum_corrections", "auc_floor", "ks_limit",
        "require_signal_efficiency_above_zz", "artifacts_no_selection",
        "artifacts_selected",
    ):
        assert getattr(reduced, name) == getattr(full, name)


def test_angular5_r3_arm64_config_binds_the_exact_sealed_table_and_profile():
    config = load_mass_bin_reweighting_config(
        "config/mass_bin_reweighting_drop_top4_angular5_r3_arm64.yaml"
    )
    assert config.schema_version == "1.2"
    assert config.input_run == "runs/angular5-mc-363490-2026-08-26-r3-arm64"
    assert config.input_table_path == (
        "runs/angular5-mc-363490-2026-08-26-r3-arm64/processed/"
        "mc_events_angular5.csv.gz"
    )
    assert config.input_table_sha256 == (
        "bc31f4e65ccecc0a1962648cfe240b67d8ecc6df8eda2478b3f46c93d2f34f09"
    )
    assert config.features == ANGULAR5_R3_ARM64


def test_angular5_r3_arm64_source_binding_hashes_only_the_sealed_mc_table(monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: pytest.fail("source binding must not parse CSV"))
    sources = resolve_reweighting_sources(
        input_run="runs/angular5-mc-363490-2026-08-26-r3-arm64",
        reference_run="runs/full-training-363490-2026-08-11-r2",
        config_path="config/mass_bin_reweighting_drop_top4_angular5_r3_arm64.yaml",
    )
    assert sources.training_input.mc_path == Path(
        "runs/angular5-mc-363490-2026-08-26-r3-arm64/processed/mc_events_angular5.csv.gz"
    ).resolve()
    assert sources.training_input.hashes["mc"] == (
        "bc31f4e65ccecc0a1962648cfe240b67d8ecc6df8eda2478b3f46c93d2f34f09"
    )


def test_angular5_r3_arm64_rejects_copied_config_before_protected_sources(
    tmp_path, monkeypatch
):
    copied = tmp_path / "copied-r3.yaml"
    copied.write_bytes(Path(
        "config/mass_bin_reweighting_drop_top4_angular5_r3_arm64.yaml"
    ).read_bytes())
    original = StudySource.from_path

    def config_only(cls, name, path, *, capture=False):
        if name != "study_config":
            pytest.fail("copied R3 config reached a protected source")
        return original(name, path, capture=capture)

    monkeypatch.setattr(StudySource, "from_path", classmethod(config_only))
    with pytest.raises(ValueError, match="canonical R3-ARM64 config"):
        resolve_reweighting_sources(
            input_run="runs/angular5-mc-363490-2026-08-26-r3-arm64",
            reference_run="runs/full-training-363490-2026-08-11-r2",
            config_path=copied,
        )


def test_policy_manifest_record_uses_bound_drop_top4_profile():
    config = load_mass_bin_reweighting_config(
        "config/mass_bin_reweighting_drop_top4.yaml"
    )
    assert policy_manifest_record(config)["features"] == list(DROP_TOP4)


@pytest.mark.parametrize(
    ("config_name", "mutate"),
    [
        (name, mutate)
        for name in (
            "mass_bin_reweighting.yaml",
            "mass_bin_reweighting_drop_top4.yaml",
        )
        for mutate in (
            lambda raw: raw.update(extra=True),
            lambda raw: raw.pop("features"),
            lambda raw: raw.update(features=list(reversed(raw["features"]))),
            lambda raw: raw.update(features=raw["features"] + ["m4l"]),
            lambda raw: raw.update(features=raw["features"] + [raw["features"][0]]),
            lambda raw: raw.update(features=["lep1_pt", "lep2_pt"]),
            lambda raw: raw.update(mass_bin_edges=[105, 120, 160]),
            lambda raw: raw.update(minimum_effective_count=99.0),
            lambda raw: raw.update(epsilon_floor=1e-5),
            lambda raw: raw.update(damping=0.4),
            lambda raw: raw.update(round_factor_bounds=[0.4, 2.0]),
            lambda raw: raw.update(cumulative_bounds=[0.1, 5.0]),
            lambda raw: raw.update(maximum_corrections=6),
            lambda raw: raw.update(auc_floor=0.79),
            lambda raw: raw.update(ks_limit=0.11),
            lambda raw: raw.update(require_signal_efficiency_above_zz=False),
            lambda raw: raw.update(input_manifest_sha256="0" * 64),
            lambda raw: raw.update(reference_manifest_sha256="0" * 64),
            lambda raw: raw.update(ablation_manifest_sha256="0" * 64),
            lambda raw: raw.update(raw_zz_sha256="0" * 64),
            lambda raw: raw["artifacts_no_selection"].append("model/xgboost_model.json"),
            lambda raw: raw["artifacts_selected"].remove("predictions/test_scores.csv.gz"),
        )
    ],
)
def test_config_rejects_every_frozen_decision_change(tmp_path, config_name, mutate):
    raw = yaml.safe_load((Path("config") / config_name).read_bytes())
    mutate(raw)
    path = tmp_path / "changed.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(ValueError):
        load_mass_bin_reweighting_config(path)


@pytest.mark.parametrize("kind", ["directory", "file", "symlink", "dangling_symlink"])
def test_output_preflight_refuses_every_occupied_target(tmp_path, kind):
    target = tmp_path / "study"
    if kind == "directory":
        target.mkdir()
    elif kind == "file":
        target.write_text("occupied")
    elif kind == "symlink":
        destination = tmp_path / "destination"
        destination.mkdir()
        target.symlink_to(destination, target_is_directory=True)
    else:
        target.symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(FileExistsError):
        resolve_reweighting_output(
            project_root=tmp_path,
            working_directory=tmp_path,
            input_run=tmp_path / "input",
            reference_run=tmp_path / "reference",
            run_dir=target,
        )


def test_output_inside_either_protected_source_is_refused(tmp_path):
    input_run = tmp_path / "input"
    reference = tmp_path / "reference"
    input_run.mkdir()
    reference.mkdir()
    for protected in (input_run, reference):
        with pytest.raises(ValueError, match="inside"):
            resolve_reweighting_output(
                project_root=tmp_path,
                working_directory=tmp_path,
                input_run=input_run,
                reference_run=reference,
                run_dir=protected / "new",
            )


def test_output_inside_any_additional_protected_source_is_refused(tmp_path):
    ablation = tmp_path / "ablation"
    raw_root = tmp_path / "data" / "raw" / "zz.root"
    reweighting_reference = tmp_path / "reweighting-reference"
    ablation.mkdir()
    raw_root.parent.mkdir(parents=True)
    raw_root.write_bytes(b"root")
    reweighting_reference.mkdir()
    for target in (
        ablation / "new", raw_root, raw_root / "new",
        reweighting_reference / "new",
    ):
        with pytest.raises(ValueError, match="protected"):
            resolve_reweighting_output(
                project_root=tmp_path,
                working_directory=tmp_path,
                input_run=tmp_path / "input",
                reference_run=tmp_path / "reference",
                ablation_run=ablation,
                raw_zz_path=raw_root,
                reweighting_reference_run=reweighting_reference,
                run_dir=target,
            )


def test_source_binding_hashes_ablation_and_raw_root_without_parsing(monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: pytest.fail("must not parse CSV"))
    sources = resolve_reweighting_sources(
        input_run="runs/full-baseline-363490-2026-08-11-r2",
        reference_run="runs/full-training-363490-2026-08-11-r2",
        config_path="config/mass_bin_reweighting.yaml",
    )
    assert sources.records["ablation_manifest"].sha256 == "5120e6080e82b14f66917ba731c98715fa5d6190c25c396d8c675200e9ca52df"
    assert sources.records["raw_zz"].sha256 == "76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07"


def test_drop_top4_source_binding_records_the_frozen_reweighting_manifest(monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: pytest.fail("must not parse CSV"))
    sources = resolve_reweighting_sources(
        input_run="runs/full-baseline-363490-2026-08-11-r2",
        reference_run="runs/full-training-363490-2026-08-11-r2",
        config_path="config/mass_bin_reweighting_drop_top4.yaml",
    )
    reference = sources.records["reweighting_reference_manifest"]
    assert reference.sha256 == "145e38478dfd12310a82f4ed544c6cf0b09204cbc1c7d08e6e485941c00f9e38"
    assert reference.path == Path(
        "runs/mass-reweighting-363490-2026-08-11/artifacts/study_manifest.json"
    ).resolve()


def test_atomic_claim_has_one_winner_and_parent_substitution_fails(tmp_path):
    layout = _fresh_layout(tmp_path)
    first = claim_reweighting_output(layout)
    with pytest.raises(FileExistsError):
        claim_reweighting_output(layout)
    assert first.directory_identities is not None

    parent = tmp_path / "second-parent"
    parent.mkdir()
    second = resolve_reweighting_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=tmp_path / "input",
        reference_run=tmp_path / "reference",
        run_dir=parent / "study",
    )
    parent.rmdir()
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    parent.symlink_to(replacement, target_is_directory=True)
    with pytest.raises(ValueError):
        claim_reweighting_output(second)


def test_no_selection_publication_is_exact_manifest_last_and_hashed(tmp_path):
    config = _config(tmp_path)
    source = tmp_path / "source.json"
    source.write_text('{"status":"complete"}\n')
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    receipt = write_reweighting_artifacts(
        layout,
        config_source=config,
        config_bytes=config.read_bytes(),
        iteration_results=_iteration_results(),
        bin_efficiencies=_bin_efficiencies(),
        weight_multipliers=_weight_multipliers(),
        selection={"schema_version": "1.0", "status": "no_eligible_iteration", "selected_iteration": None, "test_opened": False},
        plot_artifacts={
            "iteration_tradeoff.png": _png(b"tradeoff"),
            "zz_efficiency_by_mass.png": _png(b"efficiency"),
        },
    )
    manifest = publish_reweighting_manifest(
        layout,
        receipt=receipt,
        sources=_sources(source),
        source_row_counts=_rows(),
        decision={"schema_version": "1.0", "status": "no_eligible_iteration", "selected_iteration": None, "test_opened": False},
        policy=_policy_record(),
        software={},
    )
    files = {
        path.relative_to(layout.run_dir).as_posix()
        for path in layout.run_dir.rglob("*")
        if path.is_file()
    }
    assert files == NO_SELECTION
    assert set(manifest["outputs"]) == NO_SELECTION - {"artifacts/study_manifest.json"}
    assert manifest["sources"]["task4a_mc"]["row_count"] == 3
    assert manifest["sources"]["task4a_mc"]["rows_by_split"] == {"train": 1, "validation": 1, "test": 1}
    for relative, record in manifest["outputs"].items():
        payload = (layout.run_dir / relative).read_bytes()
        assert record["size_bytes"] == len(payload)
        assert record["sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["outputs"]["artifacts/iteration_results.csv"]["row_count"] == 6
    assert manifest["fixed_bin_effective_counts"] == {
        f"[{lower},{lower + 5})" if lower < 155 else "[155,160]": 100.0
        for lower in range(105, 160, 5)
    }
    assert manifest["iteration_cumulative_multipliers"] == {
        str(iteration): {
            f"[{lower},{lower + 5})" if lower < 155 else "[155,160]": 1.0
            for lower in range(105, 160, 5)
        }
        for iteration in range(6)
    }
    written_bins = pd.read_csv(layout.artifacts_dir / "bin_efficiencies.csv")
    assert manifest["fixed_bin_effective_counts"] == {
        mass_bin: float(rows["effective_count"].iloc[0])
        for mass_bin, rows in written_bins.groupby("mass_bin", sort=False)
    }
    written_multipliers = pd.read_csv(
        layout.artifacts_dir / "weight_multipliers.csv"
    )
    assert manifest["iteration_cumulative_multipliers"] == {
        str(int(iteration)): dict(zip(rows["mass_bin"], rows["multiplier"]))
        for iteration, rows in written_multipliers.groupby("iteration", sort=True)
    }
    json.dumps(manifest, allow_nan=False)
    manifest_path = layout.artifacts_dir / "study_manifest.json"
    assert manifest_path.stat().st_mtime_ns >= max(
        path.stat().st_mtime_ns
        for path in layout.run_dir.rglob("*")
        if path.is_file() and path != manifest_path
    )


def test_selected_publication_has_exact_thirteen_files(tmp_path):
    config = _config(tmp_path)
    source = tmp_path / "source.json"
    source.write_text("source")
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    receipt = write_reweighting_artifacts(
        layout,
        config_source=config,
        config_bytes=config.read_bytes(),
        iteration_results=_iteration_results(selected=True),
        bin_efficiencies=_bin_efficiencies(iterations=1),
        weight_multipliers=_weight_multipliers(iterations=1),
        selection={"schema_version": "1.0", "status": "test_nonreproduction", "selected_iteration": 0, "test_opened": True},
        plot_artifacts={
            "iteration_tradeoff.png": _png(b"tradeoff"),
            "zz_efficiency_by_mass.png": _png(b"efficiency"),
            "selected_mass_sculpting.png": _png(b"mass"),
        },
        model=_FakeModel(),
        test_metrics={"schema_version": "1.0", "weighted_auc": 0.81},
        selected_oof_scores=pd.DataFrame({"label": [0, 1], "physical_weight": [1.0, 1.0], "oof_score": [0.2, 0.8]}),
        test_scores=pd.DataFrame({"label": [0, 1], "physical_weight": [1.0, 1.0], "score": [0.3, 0.7]}),
    )
    publish_reweighting_manifest(
        layout,
        receipt=receipt,
        sources=_sources(source),
        source_row_counts=_rows(),
        decision={"schema_version": "1.0", "status": "test_nonreproduction", "selected_iteration": 0, "test_opened": True},
        policy=_policy_record(),
        software={},
    )
    files = {p.relative_to(layout.run_dir).as_posix() for p in layout.run_dir.rglob("*") if p.is_file()}
    assert files == SELECTED


def test_nonfinite_or_contradictory_artifacts_fail_terminally(tmp_path):
    config = _config(tmp_path)
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    bad = _iteration_results()
    bad.loc[0, "weighted_oof_auc"] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        write_reweighting_artifacts(
            layout,
            config_source=config,
            config_bytes=config.read_bytes(),
            iteration_results=bad,
            bin_efficiencies=_bin_efficiencies(),
            weight_multipliers=_weight_multipliers(),
            selection={"status": "no_eligible_iteration", "selected_iteration": None, "test_opened": False},
            plot_artifacts={"iteration_tradeoff.png": _png(), "zz_efficiency_by_mass.png": _png()},
        )
    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_failure_is_no_clobber_and_prevents_future_publication(tmp_path):
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    record_reweighting_failure(layout, RuntimeError("first"))
    before = (layout.run_dir / "failure.json").read_bytes()
    record_reweighting_failure(layout, RuntimeError("second"))
    assert (layout.run_dir / "failure.json").read_bytes() == before
    with pytest.raises(RuntimeError, match="failed"):
        write_reweighting_artifacts(
            layout,
            config_source=_config(tmp_path),
            config_bytes=_config(tmp_path).read_bytes(),
            iteration_results=_iteration_results(),
            bin_efficiencies=_bin_efficiencies(),
            weight_multipliers=_weight_multipliers(),
            selection={"status": "no_eligible_iteration", "selected_iteration": None, "test_opened": False},
            plot_artifacts={"iteration_tradeoff.png": _png(), "zz_efficiency_by_mass.png": _png()},
        )


def test_manifest_row_counts_do_not_reparse_outputs_with_pandas(tmp_path, monkeypatch):
    config = _config(tmp_path)
    source = tmp_path / "source.json"
    source.write_text("source")
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    decision = {"status": "no_eligible_iteration", "selected_iteration": None, "test_opened": False}
    receipt = write_reweighting_artifacts(
        layout,
        config_source=config,
        config_bytes=config.read_bytes(),
        iteration_results=_iteration_results(),
        bin_efficiencies=_bin_efficiencies(),
        weight_multipliers=_weight_multipliers(),
        selection=decision,
        plot_artifacts={"iteration_tradeoff.png": _png(), "zz_efficiency_by_mass.png": _png()},
    )
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: pytest.fail("publication must not call pd.read_csv"))
    publish_reweighting_manifest(
        layout,
        receipt=receipt,
        sources=_sources(source),
        source_row_counts=_rows(),
        decision=decision,
        policy=_policy_record(),
        software={},
    )


def test_manifest_refuses_fixed_counts_different_from_published_bins_without_pandas(
    tmp_path, monkeypatch
):
    config = _config(tmp_path)
    source = tmp_path / "source.json"
    source.write_text("source")
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    fixed = _bin_efficiencies()[["mass_bin", "effective_count"]].drop_duplicates()
    fixed["effective_count"] = 200.0
    decision = {
        "status": "no_eligible_iteration",
        "selected_iteration": None,
        "test_opened": False,
    }
    receipt = write_reweighting_artifacts(
        layout,
        config_source=config,
        config_bytes=config.read_bytes(),
        iteration_results=_iteration_results(),
        bin_efficiencies=_bin_efficiencies(),
        weight_multipliers=_weight_multipliers(),
        selection=decision,
        plot_artifacts={
            "iteration_tradeoff.png": _png(),
            "zz_efficiency_by_mass.png": _png(),
        },
        fixed_bin_statistics=fixed,
    )
    monkeypatch.setattr(
        pd, "read_csv", lambda *args, **kwargs: pytest.fail("must not use pandas")
    )

    with pytest.raises(ValueError, match="effective-count.*published"):
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=_sources(source),
            source_row_counts=_rows(),
            decision=decision,
            policy=_policy_record(),
            software={},
        )

    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_manifest_refuses_multiplier_csv_different_from_receipt_without_pandas(
    tmp_path, monkeypatch
):
    config = _config(tmp_path)
    source = tmp_path / "source.json"
    source.write_text("source")
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    multipliers = _weight_multipliers()
    multipliers.loc[multipliers["iteration"].eq(1), "multiplier"] = 1.25
    decision = {
        "status": "no_eligible_iteration",
        "selected_iteration": None,
        "test_opened": False,
    }
    receipt = write_reweighting_artifacts(
        layout,
        config_source=config,
        config_bytes=config.read_bytes(),
        iteration_results=_iteration_results(),
        bin_efficiencies=_bin_efficiencies(),
        weight_multipliers=multipliers,
        selection=decision,
        plot_artifacts={
            "iteration_tradeoff.png": _png(),
            "zz_efficiency_by_mass.png": _png(),
        },
        fixed_bin_statistics=(
            _bin_efficiencies(iterations=1)[
                ["mass_bin", "effective_count"]
            ].drop_duplicates()
        ),
    )
    changed = multipliers.copy()
    changed.loc[
        changed["iteration"].eq(1) & changed["mass_bin"].eq("[105,110)"),
        "multiplier",
    ] = 1.5
    (layout.artifacts_dir / "weight_multipliers.csv").write_bytes(
        changed.to_csv(index=False).encode("utf-8")
    )
    monkeypatch.setattr(
        pd, "read_csv", lambda *args, **kwargs: pytest.fail("must not use pandas")
    )

    with pytest.raises(ValueError, match="multiplier.*published"):
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=_sources(source),
            source_row_counts=_rows(),
            decision=decision,
            policy=_policy_record(),
            software={},
        )

    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


@pytest.mark.parametrize("artifact", ["bin_efficiencies.csv", "weight_multipliers.csv"])
def test_manifest_refuses_audit_csv_substitution_between_semantics_and_receipt(
    tmp_path, monkeypatch, artifact
):
    config = _config(tmp_path)
    source = tmp_path / "source.json"
    source.write_text("source")
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    decision = {
        "status": "no_eligible_iteration",
        "selected_iteration": None,
        "test_opened": False,
    }
    receipt = write_reweighting_artifacts(
        layout,
        config_source=config,
        config_bytes=config.read_bytes(),
        iteration_results=_iteration_results(),
        bin_efficiencies=_bin_efficiencies(),
        weight_multipliers=_weight_multipliers(),
        selection=decision,
        plot_artifacts={
            "iteration_tradeoff.png": _png(),
            "zz_efficiency_by_mass.png": _png(),
        },
    )
    if artifact == "bin_efficiencies.csv":
        changed = _bin_efficiencies().assign(effective_count=200.0)
    else:
        changed = _weight_multipliers().assign(multiplier=1.5)
    changed_bytes = changed.to_csv(index=False).encode("utf-8")
    original = mass_bin_reweighting_run._build_output_records
    calls = 0

    def substitute_before_receipt(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            (layout.artifacts_dir / artifact).write_bytes(changed_bytes)
        return original(*args, **kwargs)

    monkeypatch.setattr(
        mass_bin_reweighting_run,
        "_build_output_records",
        substitute_before_receipt,
    )

    with pytest.raises(RuntimeError, match="audit CSV changed"):
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=_sources(source),
            source_row_counts=_rows(),
            decision=decision,
            policy=_policy_record(),
            software={},
        )

    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda frame: frame.loc[frame["working_point"].ne("medium")].copy(),
        lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True),
        lambda frame: pd.concat(
            [frame, frame.iloc[[0]].assign(working_point="unexpected")],
            ignore_index=True,
        ),
        lambda frame: frame.iloc[:-1].copy(),
        lambda frame: pd.concat(
            [frame, frame.iloc[[0]].assign(mass_bin="[160,165)")],
            ignore_index=True,
        ),
    ],
)
def test_manifest_refuses_noncanonical_bin_evidence_before_promotion(
    tmp_path, mutate
):
    bins = mutate(_bin_efficiencies())
    layout, receipt, source, decision = _written_no_selection(
        tmp_path, bin_efficiencies=bins
    )

    with pytest.raises(ValueError, match="bin-efficiency"):
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=_sources(source),
            source_row_counts=_rows(),
            decision=decision,
            policy=_policy_record(),
            software={},
        )

    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda frame: frame.assign(eligible=True),
        lambda frame: frame.assign(eligibility_reasons=""),
        lambda frame: frame.assign(weighted_oof_auc=0.81),
        lambda frame: frame.assign(maximum_oof_zz_ks=0.04),
        lambda frame: frame.assign(loose_oof_zz_ks=0.20),
        lambda frame: frame.assign(loose_signal_efficiency=0.4),
        lambda frame: pd.concat(
            [frame, frame.assign(iteration=1)], ignore_index=True
        ),
    ],
)
def test_manifest_refuses_gate_or_terminal_contradictory_iterations(
    tmp_path, mutate
):
    iterations = mutate(_iteration_results())
    layout, receipt, source, decision = _written_no_selection(
        tmp_path, iteration_results=iterations
    )

    with pytest.raises(ValueError, match="iteration|eligib|terminal|gate"):
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=_sources(source),
            source_row_counts=_rows(),
            decision=decision,
            policy=_policy_record(),
            software={},
        )

    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


@pytest.mark.parametrize("selected_iteration", [0, 5])
def test_manifest_accepts_selected_iteration_within_frozen_range(
    tmp_path, selected_iteration
):
    layout, receipt, source, decision = _written_selected(
        tmp_path, selected_iteration=selected_iteration
    )

    manifest = publish_reweighting_manifest(
        layout,
        receipt=receipt,
        sources=_sources(source),
        source_row_counts=_rows(),
        decision=decision,
        policy=_policy_record(),
        software={},
    )

    assert manifest["decision"]["selected_iteration"] == selected_iteration


def test_manifest_refuses_selected_iteration_above_frozen_maximum(tmp_path):
    layout, receipt, source, decision = _written_selected(
        tmp_path, selected_iteration=6
    )

    with pytest.raises(ValueError, match="selected iteration.*0.*5"):
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=_sources(source),
            source_row_counts=_rows(),
            decision=decision,
            policy=_policy_record(),
            software={},
        )

    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_manifest_refuses_iteration_six_after_live_cap_rebinding(
    tmp_path, monkeypatch
):
    layout, receipt, source, decision = _written_selected(
        tmp_path, selected_iteration=6
    )
    monkeypatch.setattr(mass_bin_reweighting_run, "_MAXIMUM_CORRECTIONS", 6)

    with pytest.raises(ValueError, match="selected iteration.*0.*5"):
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=_sources(source),
            source_row_counts=_rows(),
            decision=decision,
            policy=_policy_record(),
            software={},
        )

    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


@pytest.mark.parametrize(
    ("decision_status", "auc_floor"),
    [
        ("insufficient_bin_statistics", 0.80),
        ("no_eligible_iteration", 0.79),
    ],
)
def test_manifest_rejects_selection_or_policy_that_differs_from_written_contract(tmp_path, decision_status, auc_floor):
    config = _config(tmp_path)
    source = tmp_path / "source.json"
    source.write_text("source")
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    written = {"status": "no_eligible_iteration", "selected_iteration": None, "test_opened": False}
    decision = {"status": decision_status, "selected_iteration": None, "test_opened": False}
    policy = {**_policy_record(), "auc_floor": auc_floor}
    receipt = write_reweighting_artifacts(
        layout,
        config_source=config,
        config_bytes=config.read_bytes(),
        iteration_results=_iteration_results(),
        bin_efficiencies=_bin_efficiencies(),
        weight_multipliers=_weight_multipliers(),
        selection=written,
        plot_artifacts={"iteration_tradeoff.png": _png(), "zz_efficiency_by_mass.png": _png()},
    )
    with pytest.raises(ValueError):
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=_sources(source),
            source_row_counts=_rows(),
            decision=decision,
            policy=policy,
            software={},
        )
    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.artifacts_dir / "study_manifest.json").exists()


def test_drop_top4_cross_profile_policy_substitution_fails_before_manifest_promotion(
    tmp_path,
):
    config = load_mass_bin_reweighting_config(
        "config/mass_bin_reweighting_drop_top4.yaml"
    )
    source = tmp_path / "source.json"
    source.write_text("source")
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    decision = {"status": "no_eligible_iteration", "selected_iteration": None, "test_opened": False}
    receipt = write_reweighting_artifacts(
        layout,
        config_source=Path("config/mass_bin_reweighting_drop_top4.yaml"),
        config_bytes=Path("config/mass_bin_reweighting_drop_top4.yaml").read_bytes(),
        iteration_results=_iteration_results(),
        bin_efficiencies=_bin_efficiencies(),
        weight_multipliers=_weight_multipliers(),
        selection=decision,
        plot_artifacts={"iteration_tradeoff.png": _png(), "zz_efficiency_by_mass.png": _png()},
        features=config.features,
    )
    with pytest.raises(ValueError, match="policy differs"):
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=_sources(source, features=config.features),
            source_row_counts=_rows(),
            decision=decision,
            policy=_policy_record(),
            software={},
        )
    residue = layout.artifacts_dir / ".study_manifest.controlled.tmp"
    residue.write_text("controlled residue")
    with pytest.raises(AssertionError):
        _assert_exact_failed_terminal(
            layout,
            retained_files=approved_reweighting_artifacts(selected=False) - {
                "artifacts/study_manifest.json"
            },
        )
    residue.unlink()
    _assert_exact_failed_terminal(
        layout,
        retained_files=approved_reweighting_artifacts(selected=False) - {
            "artifacts/study_manifest.json"
        },
    )


def test_drop_top4_feature_list_mutation_after_source_bind_fails_terminally(
    tmp_path,
):
    layout, receipt, source, decision, config = _written_drop_top4_no_selection(
        tmp_path
    )
    policy = policy_manifest_record(config)
    policy["features"][0] = "m4l"

    with pytest.raises(ValueError, match="policy differs"):
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=_sources(source, features=DROP_TOP4),
            source_row_counts=_rows(),
            decision=decision,
            policy=policy,
            software={},
        )

    _assert_exact_failed_terminal(
        layout,
        retained_files=approved_reweighting_artifacts(selected=False) - {
            "artifacts/study_manifest.json"
        },
    )


def test_drop_top4_config_byte_substitution_after_claim_fails_terminally(tmp_path):
    config_path = tmp_path / "drop-top4.yaml"
    captured = Path("config/mass_bin_reweighting_drop_top4.yaml").read_bytes()
    config_path.write_bytes(captured)
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    config_path.write_bytes(Path("config/mass_bin_reweighting.yaml").read_bytes())

    with pytest.raises(RuntimeError, match="config changed"):
        write_reweighting_artifacts(
            layout,
            config_source=config_path,
            config_bytes=captured,
            iteration_results=_iteration_results(),
            bin_efficiencies=_bin_efficiencies(),
            weight_multipliers=_weight_multipliers(),
            selection={
                "status": "no_eligible_iteration",
                "selected_iteration": None,
                "test_opened": False,
            },
            plot_artifacts={
                "iteration_tradeoff.png": _png(),
                "zz_efficiency_by_mass.png": _png(),
            },
            features=DROP_TOP4,
        )

    assert not (layout.run_dir / "config.yaml").exists()
    _assert_exact_failed_terminal(layout, retained_files=set())


def test_drop_top4_source_symlink_replacement_fails_before_manifest_promotion(
    tmp_path,
):
    layout, receipt, source, decision, config = _written_drop_top4_no_selection(
        tmp_path
    )
    sources = _sources(source, features=DROP_TOP4)
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(source.read_bytes())
    source.unlink()
    source.symlink_to(replacement)

    with pytest.raises(ValueError, match="symlink"):
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=sources,
            source_row_counts=_rows(),
            decision=decision,
            policy=policy_manifest_record(config),
            software={},
        )

    _assert_exact_failed_terminal(
        layout,
        retained_files=approved_reweighting_artifacts(selected=False) - {
            "artifacts/study_manifest.json"
        },
    )


def test_drop_top4_same_path_config_publication_fails_terminally(tmp_path):
    payload = Path("config/mass_bin_reweighting_drop_top4.yaml").read_bytes()
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    layout.config_snapshot.write_bytes(payload)

    with pytest.raises(FileExistsError, match="config.yaml"):
        write_reweighting_artifacts(
            layout,
            config_source=layout.config_snapshot,
            config_bytes=payload,
            iteration_results=_iteration_results(),
            bin_efficiencies=_bin_efficiencies(),
            weight_multipliers=_weight_multipliers(),
            selection={
                "status": "no_eligible_iteration",
                "selected_iteration": None,
                "test_opened": False,
            },
            plot_artifacts={
                "iteration_tradeoff.png": _png(),
                "zz_efficiency_by_mass.png": _png(),
            },
            features=DROP_TOP4,
        )

    _assert_exact_failed_terminal(layout, retained_files={"config.yaml"})


def test_drop_top4_manifest_policy_mismatch_fails_terminally(tmp_path):
    layout, receipt, source, decision, config = _written_drop_top4_no_selection(
        tmp_path
    )
    policy = {**policy_manifest_record(config), "ks_limit": 0.11}

    with pytest.raises(ValueError, match="policy differs"):
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=_sources(source, features=DROP_TOP4),
            source_row_counts=_rows(),
            decision=decision,
            policy=policy,
            software={},
        )

    _assert_exact_failed_terminal(
        layout,
        retained_files=approved_reweighting_artifacts(selected=False) - {
            "artifacts/study_manifest.json"
        },
    )


def test_artifact_writer_rejects_full14_profile_for_drop_top4_config_bytes(tmp_path):
    config_path = Path("config/mass_bin_reweighting_drop_top4.yaml")
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    with pytest.raises(ValueError, match="artifact features differ"):
        write_reweighting_artifacts(
            layout,
            config_source=config_path,
            config_bytes=config_path.read_bytes(),
            iteration_results=_iteration_results(),
            bin_efficiencies=_bin_efficiencies(),
            weight_multipliers=_weight_multipliers(),
            selection={
                "status": "no_eligible_iteration",
                "selected_iteration": None,
                "test_opened": False,
            },
            plot_artifacts={
                "iteration_tradeoff.png": _png(),
                "zz_efficiency_by_mass.png": _png(),
            },
            features=tuple(FEATURES),
        )
    assert (layout.run_dir / "failure.json").is_file()
    assert not (layout.run_dir / "config.yaml").exists()


def _written_no_selection(
    tmp_path,
    *,
    iteration_results: pd.DataFrame | None = None,
    bin_efficiencies: pd.DataFrame | None = None,
):
    config = _config(tmp_path)
    source = tmp_path / "source.json"
    source.write_text("source")
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    decision = {
        "status": "no_eligible_iteration",
        "selected_iteration": None,
        "test_opened": False,
    }
    receipt = write_reweighting_artifacts(
        layout,
        config_source=config,
        config_bytes=config.read_bytes(),
        iteration_results=(
            _iteration_results()
            if iteration_results is None
            else iteration_results
        ),
        bin_efficiencies=(
            _bin_efficiencies()
            if bin_efficiencies is None
            else bin_efficiencies
        ),
        weight_multipliers=_weight_multipliers(),
        selection=decision,
        plot_artifacts={
            "iteration_tradeoff.png": _png(),
            "zz_efficiency_by_mass.png": _png(),
        },
        fixed_bin_statistics=(
            _bin_efficiencies(iterations=1)[
                ["mass_bin", "effective_count"]
            ].drop_duplicates()
        ),
    )
    return layout, receipt, source, decision


def _written_drop_top4_no_selection(tmp_path):
    config_path = tmp_path / "drop-top4.yaml"
    config_path.write_bytes(
        Path("config/mass_bin_reweighting_drop_top4.yaml").read_bytes()
    )
    config = load_mass_bin_reweighting_config(config_path)
    source = tmp_path / "source.json"
    source.write_text("source")
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    decision = {
        "status": "no_eligible_iteration",
        "selected_iteration": None,
        "test_opened": False,
    }
    receipt = write_reweighting_artifacts(
        layout,
        config_source=config_path,
        config_bytes=config_path.read_bytes(),
        iteration_results=_iteration_results(),
        bin_efficiencies=_bin_efficiencies(),
        weight_multipliers=_weight_multipliers(),
        selection=decision,
        plot_artifacts={
            "iteration_tradeoff.png": _png(),
            "zz_efficiency_by_mass.png": _png(),
        },
        features=DROP_TOP4,
    )
    return layout, receipt, source, decision, config


def _assert_exact_failed_terminal(
    layout: TrainingOutputLayout, *, retained_files: set[str]
) -> None:
    failure = json.loads((layout.run_dir / "failure.json").read_text())
    assert failure["status"] == "failed"
    assert set(failure) == {"status", "error_type", "message"}
    actual_files = {
        path.relative_to(layout.run_dir).as_posix()
        for path in layout.run_dir.rglob("*")
        if path.is_file()
    }
    assert actual_files == retained_files | {"failure.json"}
    actual_directories = {
        path.relative_to(layout.run_dir).as_posix()
        for path in layout.run_dir.rglob("*")
        if path.is_dir()
    }
    assert actual_directories == {
        ".terminal.failed", "artifacts", "model", "plots", "predictions"
    }
    assert not [path for path in layout.run_dir.rglob("*") if path.is_symlink()]
    assert not [
        path
        for path in layout.run_dir.rglob("*")
        if ".tmp" in path.name or "staged" in path.name
    ]


def _written_selected(tmp_path, *, selected_iteration: int):
    config = _config(tmp_path)
    source = tmp_path / "source.json"
    source.write_text("source")
    layout = claim_reweighting_output(_fresh_layout(tmp_path))
    decision = {
        "status": "test_nonreproduction",
        "selected_iteration": selected_iteration,
        "test_opened": True,
    }
    receipt = write_reweighting_artifacts(
        layout,
        config_source=config,
        config_bytes=config.read_bytes(),
        iteration_results=_selected_iteration_results(selected_iteration),
        bin_efficiencies=_bin_efficiencies(iterations=selected_iteration + 1),
        weight_multipliers=_weight_multipliers(iterations=selected_iteration + 1),
        selection=decision,
        plot_artifacts={
            "iteration_tradeoff.png": _png(),
            "zz_efficiency_by_mass.png": _png(),
            "selected_mass_sculpting.png": _png(),
        },
        model=_FakeModel(),
        test_metrics={"weighted_auc": 0.79},
        selected_oof_scores=pd.DataFrame({"score": [0.4]}),
        test_scores=pd.DataFrame({"score": [0.4]}),
        fixed_bin_statistics=(
            _bin_efficiencies(iterations=1)[
                ["mass_bin", "effective_count"]
            ].drop_duplicates()
        ),
    )
    return layout, receipt, source, decision


def _fresh_layout(tmp_path: Path) -> TrainingOutputLayout:
    return resolve_reweighting_output(
        project_root=tmp_path,
        working_directory=tmp_path,
        input_run=tmp_path / "input",
        reference_run=tmp_path / "reference",
        run_dir=tmp_path / "study",
    )


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    if not path.exists():
        path.write_bytes(Path("config/mass_bin_reweighting.yaml").read_bytes())
    return path


def _iteration_results(*, selected: bool = False) -> pd.DataFrame:
    rows = []
    for iteration in range(1 if selected else 6):
        eligible = bool(selected)
        row = {
            "iteration": iteration,
            "candidate": "depth4_child20",
            "final_tree_count": 10,
            "weighted_oof_auc": 0.81 if eligible else 0.79,
            "maximum_oof_zz_ks": 0.05,
            "eligible": eligible,
            "eligibility_reasons": "" if eligible else "weighted_auc_below_floor",
        }
        for name in ("loose", "medium", "tight"):
            row[f"{name}_threshold"] = 0.5
            row[f"{name}_signal_efficiency"] = 0.6
            row[f"{name}_achieved_zz_efficiency"] = 0.5
            row[f"{name}_oof_zz_ks"] = 0.05
        rows.append(row)
    return pd.DataFrame(rows)


def _selected_iteration_results(selected_iteration: int) -> pd.DataFrame:
    rows = []
    for iteration in range(selected_iteration + 1):
        eligible = iteration == selected_iteration
        row = {
            "iteration": iteration,
            "candidate": "depth4_child20",
            "final_tree_count": 10,
            "weighted_oof_auc": 0.81 if eligible else 0.79,
            "maximum_oof_zz_ks": 0.05,
            "eligible": eligible,
            "eligibility_reasons": "" if eligible else "weighted_auc_below_floor",
        }
        for name in ("loose", "medium", "tight"):
            row[f"{name}_threshold"] = 0.5
            row[f"{name}_signal_efficiency"] = 0.6
            row[f"{name}_achieved_zz_efficiency"] = 0.5
            row[f"{name}_oof_zz_ks"] = 0.05
        rows.append(row)
    return pd.DataFrame(rows)


def _bin_efficiencies(*, iterations: int = 6) -> pd.DataFrame:
    bins = [f"[{lower},{lower + 5})" if lower < 155 else "[155,160]" for lower in range(105, 160, 5)]
    rows = []
    for iteration in range(iterations):
      for mass_bin in bins:
        for working_point, efficiency in (("loose", 0.5), ("medium", 0.2), ("tight", 0.1)):
            rows.append({
                "iteration": iteration,
                "mass_bin": mass_bin,
                "working_point": working_point,
                "numerator": efficiency * 100.0,
                "denominator": 100.0,
                "efficiency": efficiency,
                "effective_count": 100.0,
                "standard_error": float(np.sqrt(efficiency * (1.0 - efficiency) / 100.0)),
            })
    return pd.DataFrame(rows)


def _weight_multipliers(*, iterations: int = 6) -> pd.DataFrame:
    bins = [f"[{lower},{lower + 5})" if lower < 155 else "[155,160]" for lower in range(105, 160, 5)]
    return pd.DataFrame(
        [
            {"iteration": iteration, "mass_bin": mass_bin, "multiplier": 1.0}
            for iteration in range(iterations)
            for mass_bin in bins
        ]
    )


def _png(suffix: bytes = b"plot") -> bytes:
    return b"\x89PNG\r\n\x1a\n" + suffix


def _sources(path: Path, *, features: tuple[str, ...] = tuple(FEATURES)):
    names = {
        "study_config", "task4a_config", "task4a_mc", "task4a_summary",
        "task4a_manifest", "reference_config", "reference_manifest",
        "reference_model", "reference_metrics", "ablation_manifest", "raw_zz",
    }
    if features == DROP_TOP4:
        names.add("reweighting_reference_manifest")
    return {name: StudySource.from_path(name, path) for name in names}


def _rows():
    return {"row_count": 3, "rows_by_split": {"train": 1, "validation": 1, "test": 1}}


def _policy_record():
    return {
        "features": list(FEATURES),
        "mass_bin_edges": list(range(105, 161, 5)),
        "minimum_effective_count": 100.0,
        "epsilon_floor": 1e-6,
        "damping": 0.5,
        "round_factor_bounds": [0.5, 2.0],
        "cumulative_bounds": [0.2, 5.0],
        "maximum_corrections": 5,
        "auc_floor": 0.8,
        "ks_limit": 0.1,
        "require_signal_efficiency_above_zz": True,
    }


class _FakeModel:
    def save_raw(self, *, raw_format):
        assert raw_format == "json"
        return b'{"model":"fake"}'
