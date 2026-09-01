from __future__ import annotations

from dataclasses import replace
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path

import awkward as ak
import numpy as np
import pandas as pd
import pytest
import uproot

from src.angular5 import ANGULAR5_FEATURES
from src.angular5_enrichment_run import (
    Angular5SourceReceipt,
    Angular5Sources,
    assert_angular5_sources_unchanged,
    claim_angular5_output,
    load_angular5_enrichment_config,
)
from src.pipeline import prepare_sample
from src.selection import SelectionConfig
from src.weights import MCNormalization


PROJECT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT / "config/angular5_mc_dsid363490.yaml"
FROZEN_MC_PATH = (
    PROJECT
    / "runs/full-baseline-363490-2026-08-11-r2/processed/mc_events.csv.gz"
)
KEY = ["runNumber", "eventNumber", "channelNumber"]
SUCCESS_FILES = {
    "config.yaml",
    "processed/mc_events_angular5.csv.gz",
    "artifacts/identity_validation.json",
    "artifacts/angular5_summary.json",
    "artifacts/run_manifest.json",
}


def _event(*, event_number: int, channel: int, unit_scale: float) -> dict:
    pt = np.asarray([45.0, 42.0, 20.0, 18.0]) * unit_scale
    energy = np.asarray([50.0, 45.0, 22.0, 20.0]) * unit_scale
    return {
        "runNumber": 284500,
        "eventNumber": event_number,
        "channelNumber": channel,
        "lep_n": 4,
        "lep_pt": pt.tolist(),
        "lep_eta": [0.3, -0.2, 0.4, -0.3],
        "lep_phi": [0.0, math.pi, 1.2, -1.9],
        "lep_e": energy.tolist(),
        "lep_charge": [-1, 1, -1, 1],
        "lep_type": [11, 11, 13, 13],
        "trigE": True,
        "trigM": False,
        "lep_isTrigMatched": [True] * 4,
        "lep_isTightID": [True] * 4,
        "lep_track_iso": (pt * 0.01).tolist(),
        "lep_calo_iso": (pt * 0.01).tolist(),
        "lep_d0sig": [0.1] * 4,
        "lep_z0": [0.1] * 4,
        "mcWeight": 2.0,
    }


def _write_release22(path: Path, event: dict, *, copies: int = 1) -> None:
    branches = {
        name: np.asarray([event[name]] * copies)
        for name in (
            "runNumber",
            "eventNumber",
            "channelNumber",
            "lep_n",
            "trigE",
            "trigM",
            "mcWeight",
        )
    }
    branches.update(
        {
            physical: ak.Array([event[canonical]] * copies)
            for canonical, physical in {
                "lep_pt": "lep_pt",
                "lep_eta": "lep_eta",
                "lep_phi": "lep_phi",
                "lep_e": "lep_e",
                "lep_charge": "lep_charge",
                "lep_type": "lep_type",
                "lep_isTrigMatched": "lep_isTrigMatched",
                "lep_isTightID": "lep_isTightID",
                "lep_track_iso": "lep_ptvarcone30",
                "lep_calo_iso": "lep_topoetcone20",
                "lep_d0sig": "lep_d0sig",
                "lep_z0": "lep_z0",
            }.items()
        }
    )
    branches.update(
        {
            "xsec": np.asarray([0.5] * copies),
            "kfac": np.asarray([1.0] * copies),
            "filteff": np.asarray([1.0] * copies),
            "sum_of_weights": np.asarray([100.0] * copies),
        }
    )
    with uproot.recreate(path) as root:
        root["analysis"] = branches


def _write_open_data(path: Path, event: dict) -> None:
    branches = {
        name: np.asarray([event[name]])
        for name in (
            "runNumber",
            "eventNumber",
            "channelNumber",
            "lep_n",
            "trigE",
            "trigM",
            "mcWeight",
        )
    }
    branches.update(
        {
            physical: ak.Array([event[canonical]])
            for canonical, physical in {
                "lep_pt": "lep_pt",
                "lep_eta": "lep_eta",
                "lep_phi": "lep_phi",
                "lep_e": "lep_E",
                "lep_charge": "lep_charge",
                "lep_type": "lep_type",
                "lep_isTrigMatched": "lep_trigMatched",
                "lep_isTightID": "lep_isTightID",
                "lep_track_iso": "lep_ptcone30",
                "lep_calo_iso": "lep_etcone20",
                "lep_d0sig": "lep_tracksigd0pvunbiased",
                "lep_z0": "lep_z0",
            }.items()
        }
    )
    with uproot.recreate(path) as root:
        root["mini"] = branches


def _receipt(name: str, path: Path) -> Angular5SourceReceipt:
    metadata = path.stat()
    return Angular5SourceReceipt(
        name=name,
        path=path.resolve(),
        device=metadata.st_dev,
        inode=metadata.st_ino,
        size_bytes=metadata.st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def _fixture_sources(tmp_path: Path) -> tuple[Angular5Sources, pd.DataFrame]:
    root = tmp_path / "project"
    inputs = root / "inputs"
    inputs.mkdir(parents=True)
    config_path = inputs / "angular5.yaml"
    config_bytes = CONFIG_PATH.read_bytes()
    config_path.write_bytes(config_bytes)
    higgs_path = inputs / "higgs.root"
    zz_path = inputs / "zz.root"
    _write_release22(
        higgs_path,
        _event(event_number=101, channel=345060, unit_scale=1.0),
    )
    _write_open_data(
        zz_path,
        _event(event_number=202, channel=363490, unit_scale=1000.0),
    )

    config = load_angular5_enrichment_config(CONFIG_PATH)
    selection = SelectionConfig.from_mapping(config.selection)
    higgs = prepare_sample(
        higgs_path,
        sample_name="higgs_345060",
        selection=selection,
        tree_name="analysis",
        momentum_unit="GeV",
        is_data=False,
        label=1,
        expected_channels=(345060,),
        luminosity_pb=config.luminosity_pb,
        entry_stop=None,
        chunk_size_events=config.chunk_size_events,
        input_profile="release22",
    ).frame
    zz = prepare_sample(
        zz_path,
        sample_name="zz_363490",
        selection=selection,
        tree_name="mini",
        momentum_unit="MeV",
        is_data=False,
        label=0,
        expected_channels=(363490,),
        luminosity_pb=config.luminosity_pb,
        entry_stop=None,
        chunk_size_events=config.chunk_size_events,
        input_profile="open_data_2020",
        normalization_override=MCNormalization(1.2564, 1.0, 1.0, 7538705.808),
    ).frame
    authoritative = pd.concat([zz, higgs], ignore_index=True)
    table_path = inputs / "mc_events.csv.gz"
    authoritative.to_csv(table_path, index=False)
    manifest_path = inputs / "task4a_manifest.json"
    manifest_path.write_text('{"status":"complete"}\n', encoding="utf-8")
    frozen_path = inputs / "frozen.yaml"
    frozen_path.write_bytes(b"frozen: true\n")

    paths = {
        "enrichment_config": config_path,
        "frozen_config": frozen_path,
        "task4a_manifest": manifest_path,
        "task4a_mc": table_path,
        "higgs_root": higgs_path,
        "zz_root": zz_path,
    }
    sources = Angular5Sources(
        config=config,
        config_bytes=config_bytes,
        project_root=root.resolve(),
        receipts={name: _receipt(name, path) for name, path in paths.items()},
    )
    return sources, pd.read_csv(table_path)


def _claimed_layout(sources: Angular5Sources):
    return claim_angular5_output(
        sources=sources,
        project_root=sources.project_root,
        working_directory=sources.project_root,
        run_dir=sources.project_root / sources.config.output_run,
    )


def test_enrichment_preserves_authoritative_rows_and_appends_only_five_angles(
    tmp_path,
) -> None:
    from src.angular5_enrichment import enrich_angular5_mc

    sources, authoritative = _fixture_sources(tmp_path)

    outcome = enrich_angular5_mc(sources)

    assert outcome.frame.columns.tolist() == authoritative.columns.tolist() + list(
        ANGULAR5_FEATURES
    )
    pd.testing.assert_frame_equal(
        outcome.frame[authoritative.columns], authoritative, check_exact=True
    )
    assert outcome.frame[KEY].to_records(index=False).tolist() == authoritative[
        KEY
    ].to_records(index=False).tolist()
    assert outcome.identity_validation["matched_rows"] == 2
    assert outcome.identity_validation["old_columns_exact"] is True
    assert outcome.summary["sample_counts"] == {"higgs": 1, "zz": 1}
    values = outcome.frame[list(ANGULAR5_FEATURES)].to_numpy(dtype=float)
    assert np.isfinite(values).all()
    assert ((values[:, :3] >= -1.0) & (values[:, :3] <= 1.0)).all()
    assert ((values[:, 3:] >= -math.pi) & (values[:, 3:] < math.pi)).all()


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda frame: frame.drop(index=0).reset_index(drop=True), "coverage"),
        (lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True), "duplicate"),
        (
            lambda frame: frame.assign(
                eventNumber=[999 if index == 0 else value for index, value in enumerate(frame.eventNumber)]
            ),
            "coverage",
        ),
        (
            lambda frame: frame.assign(
                lep1_pt=[value + 1.0 if index == 0 else value for index, value in enumerate(frame.lep1_pt)]
            ),
            "old-column mismatch",
        ),
    ],
)
def test_enrichment_rejects_missing_extra_duplicate_or_semantically_changed_rows(
    tmp_path, mutation, message
) -> None:
    from src.angular5_enrichment import enrich_angular5_mc

    sources, authoritative = _fixture_sources(tmp_path)
    changed = mutation(authoritative.copy())
    table = sources.receipts["task4a_mc"].path
    changed.to_csv(table, index=False)
    sources = replace(
        sources,
        receipts={
            **sources.receipts,
            "task4a_mc": _receipt("task4a_mc", table),
        },
    )

    with pytest.raises(ValueError, match=message):
        enrich_angular5_mc(sources)


def test_enrichment_rejects_duplicate_reconstructed_root_keys(tmp_path) -> None:
    from src.angular5_enrichment import enrich_angular5_mc

    sources, _ = _fixture_sources(tmp_path)
    root = sources.receipts["higgs_root"].path
    _write_release22(
        root,
        _event(event_number=101, channel=345060, unit_scale=1.0),
        copies=2,
    )
    sources = replace(
        sources,
        receipts={**sources.receipts, "higgs_root": _receipt("higgs_root", root)},
    )

    with pytest.raises(ValueError, match="reconstructed.*duplicate"):
        enrich_angular5_mc(sources)


def test_real_frozen_csv_lexemes_survive_exact_final_gzip_parse() -> None:
    from src import angular5_enrichment as module

    authoritative_payload = FROZEN_MC_PATH.read_bytes()
    authoritative = pd.read_csv(io.BytesIO(authoritative_payload), compression="gzip")
    angles = pd.DataFrame(
        np.zeros((len(authoritative), len(ANGULAR5_FEATURES))),
        columns=ANGULAR5_FEATURES,
    )

    enriched_payload = module._append_angular5_preserving_authoritative_csv(
        authoritative_payload,
        authoritative,
        angles,
    )

    enriched = pd.read_csv(io.BytesIO(enriched_payload), compression="gzip")
    pd.testing.assert_frame_equal(
        enriched[authoritative.columns], authoritative, check_exact=True
    )
    source_lines = gzip.decompress(authoritative_payload).splitlines()
    enriched_lines = gzip.decompress(enriched_payload).splitlines()
    assert len(source_lines) == len(enriched_lines)
    assert all(
        final.rsplit(b",", len(ANGULAR5_FEATURES))[0] == source
        for source, final in zip(source_lines, enriched_lines)
    )


def test_event_key_rejects_lossy_noninteger_dtype_above_float_precision(
    tmp_path,
) -> None:
    from src.angular5_enrichment import enrich_angular5_mc

    sources, authoritative = _fixture_sources(tmp_path)
    authoritative["eventNumber"] = authoritative["eventNumber"].astype(object)
    authoritative.loc[0, "eventNumber"] = "9007199254740993.5"
    table = sources.receipts["task4a_mc"].path
    authoritative.to_csv(table, index=False)
    sources = replace(
        sources,
        receipts={**sources.receipts, "task4a_mc": _receipt("task4a_mc", table)},
    )

    with pytest.raises(ValueError, match="invalid event key"):
        enrich_angular5_mc(sources)


def test_selected_event_with_undefined_geometry_fails_instead_of_being_dropped(
    tmp_path, monkeypatch
) -> None:
    from src import angular5_enrichment as module

    sources, _ = _fixture_sources(tmp_path)

    def undefined(candidate):
        raise ValueError("undefined angular geometry")

    monkeypatch.setattr(module, "build_angular5", undefined)

    with pytest.raises(ValueError, match="undefined angular geometry"):
        module.enrich_angular5_mc(sources)


def test_csv_swap_and_restore_cannot_redirect_bound_snapshot(
    tmp_path, monkeypatch
) -> None:
    from src import angular5_enrichment as module

    sources, authoritative = _fixture_sources(tmp_path)
    table = sources.receipts["task4a_mc"].path
    alternate = tmp_path / "alternate.csv.gz"
    alternate.write_bytes(
        gzip.compress(
            authoritative.iloc[::-1].to_csv(index=False).encode("utf-8"),
            mtime=0,
        )
    )
    swapped = False

    def swap_after_descriptor_open(name: str, path: Path) -> None:
        nonlocal swapped
        if not swapped and name == "task4a_mc":
            swapped = True
            backup = tmp_path / "authoritative.backup"
            os.replace(path, backup)
            os.replace(alternate, path)
            os.replace(path, alternate)
            os.replace(backup, path)

    monkeypatch.setattr(module, "_after_receipt_descriptor_opened", swap_after_descriptor_open)

    outcome = module.enrich_angular5_mc(sources)

    assert swapped is True
    assert outcome.frame[KEY].to_records(index=False).tolist() == authoritative[
        KEY
    ].to_records(index=False).tolist()


def test_root_swap_and_restore_cannot_redirect_bound_snapshot(
    tmp_path, monkeypatch
) -> None:
    from src import angular5_enrichment as module

    sources, authoritative = _fixture_sources(tmp_path)
    root = sources.receipts["higgs_root"].path
    alternate = tmp_path / "alternate.root"
    changed_event = _event(event_number=101, channel=345060, unit_scale=1.0)
    changed_event["lep_phi"] = [0.2, math.pi, 1.2, -1.9]
    _write_release22(alternate, changed_event)
    swapped = False

    def swap_after_descriptor_open(name: str, path: Path) -> None:
        nonlocal swapped
        if not swapped and name == "higgs_root":
            swapped = True
            backup = tmp_path / "higgs.backup"
            os.replace(path, backup)
            os.replace(alternate, path)
            os.replace(path, alternate)
            os.replace(backup, path)

    monkeypatch.setattr(module, "_after_receipt_descriptor_opened", swap_after_descriptor_open)

    outcome = module.enrich_angular5_mc(sources)

    assert swapped is True
    pd.testing.assert_frame_equal(
        outcome.frame[authoritative.columns], authoritative, check_exact=True
    )


def test_manifest_is_last_and_records_exact_descriptor_bound_outputs(tmp_path) -> None:
    from src.angular5_enrichment import (
        enrich_angular5_mc,
        publish_angular5_manifest,
        write_angular5_artifacts,
    )

    sources, _ = _fixture_sources(tmp_path)
    outcome = enrich_angular5_mc(sources)
    layout = _claimed_layout(sources)

    receipt = write_angular5_artifacts(layout, sources=sources, outcome=outcome)
    assert not (layout.artifacts_dir / "run_manifest.json").exists()
    manifest = publish_angular5_manifest(
        layout, sources=sources, receipt=receipt, software={"python": "test"}
    )

    files = {
        path.relative_to(layout.run_dir).as_posix()
        for path in layout.run_dir.rglob("*")
        if path.is_file()
    }
    assert files == SUCCESS_FILES
    assert manifest["status"] == "complete"
    assert set(manifest["inputs"]) == set(sources.receipts)
    assert set(manifest["outputs"]) == SUCCESS_FILES - {
        "artifacts/run_manifest.json"
    }
    for relative, record in manifest["outputs"].items():
        payload = (layout.run_dir / relative).read_bytes()
        assert record["sha256"] == hashlib.sha256(payload).hexdigest()
        assert record["size_bytes"] == len(payload)
    summary = json.loads((layout.artifacts_dir / "angular5_summary.json").read_text())
    assert set(summary["output_receipts"]) == {
        "config.yaml",
        "processed/mc_events_angular5.csv.gz",
        "artifacts/identity_validation.json",
    }
    assert all(
        {"path", "size_bytes", "sha256"} <= set(record)
        for record in summary["output_receipts"].values()
    )
    published = pd.read_csv(layout.processed_dir / "mc_events_angular5.csv.gz")
    pd.testing.assert_frame_equal(published, outcome.frame, check_exact=True)


def test_artifact_receipt_cannot_be_rebound_after_descriptor_capture(tmp_path) -> None:
    from src.angular5_enrichment import enrich_angular5_mc, write_angular5_artifacts

    sources, _ = _fixture_sources(tmp_path)
    layout = _claimed_layout(sources)
    receipt = write_angular5_artifacts(
        layout, sources=sources, outcome=enrich_angular5_mc(sources)
    )

    with pytest.raises(TypeError):
        receipt._records["config.yaml"]["sha256"] = "0" * 64


def test_outcome_exposure_cannot_mutate_bound_payload_or_nested_evidence(
    tmp_path,
) -> None:
    from src.angular5_enrichment import enrich_angular5_mc, write_angular5_artifacts

    sources, authoritative = _fixture_sources(tmp_path)
    outcome = enrich_angular5_mc(sources)
    exposed = outcome.frame
    exposed.loc[0, "lep1_pt"] = 999.0

    with pytest.raises(TypeError):
        outcome.summary["angular5_ranges"]["cos_theta_star"]["minimum"] = -999.0

    layout = _claimed_layout(sources)
    write_angular5_artifacts(layout, sources=sources, outcome=outcome)
    published = pd.read_csv(layout.processed_dir / "mc_events_angular5.csv.gz")
    pd.testing.assert_frame_equal(
        published[authoritative.columns], authoritative, check_exact=True
    )


def test_outcome_is_bound_to_the_sources_that_created_its_payload(tmp_path) -> None:
    from src.angular5_enrichment import enrich_angular5_mc, write_angular5_artifacts

    first_sources, _ = _fixture_sources(tmp_path / "first")
    second_sources, _ = _fixture_sources(tmp_path / "second")
    outcome = enrich_angular5_mc(first_sources)
    layout = _claimed_layout(second_sources)

    with pytest.raises(ValueError, match="bound sources"):
        write_angular5_artifacts(layout, sources=second_sources, outcome=outcome)


def test_writer_parses_and_rejects_corrupt_bound_gzip_before_first_promotion(
    tmp_path,
) -> None:
    from src.angular5_enrichment import enrich_angular5_mc, write_angular5_artifacts

    sources, _ = _fixture_sources(tmp_path)
    outcome = enrich_angular5_mc(sources)
    object.__setattr__(
        outcome,
        "_table_payload",
        b"not a gzip payload",
    )
    layout = _claimed_layout(sources)

    with pytest.raises(ValueError, match="bound enriched Angular5 table"):
        write_angular5_artifacts(layout, sources=sources, outcome=outcome)

    assert not layout.config_snapshot.exists()
    assert (layout.run_dir / ".terminal.failed").is_dir()


def test_final_source_mutation_installs_failure_terminal_without_manifest(
    tmp_path, monkeypatch
) -> None:
    from src import angular5_enrichment as module

    sources, _ = _fixture_sources(tmp_path)
    layout = _claimed_layout(sources)
    receipt = module.write_angular5_artifacts(
        layout,
        sources=sources,
        outcome=module.enrich_angular5_mc(sources),
    )
    source = sources.receipts["task4a_manifest"].path

    def mutate() -> None:
        source.write_text('{"status":"mutated"}\n', encoding="utf-8")

    monkeypatch.setattr(module, "_before_final_source_revalidation", mutate)

    with pytest.raises(RuntimeError, match="changed before publication"):
        module.publish_angular5_manifest(
            layout, sources=sources, receipt=receipt, software={}
        )

    assert (layout.run_dir / ".terminal.failed").is_dir()
    failure = json.loads((layout.run_dir / "failure.json").read_text())
    assert failure["status"] == "failed"
    assert not (layout.artifacts_dir / "run_manifest.json").exists()


def test_bound_output_replacement_and_no_clobber_race_fail_closed(
    tmp_path, monkeypatch
) -> None:
    from src import angular5_enrichment as module

    sources, _ = _fixture_sources(tmp_path)
    layout = _claimed_layout(sources)
    outcome = module.enrich_angular5_mc(sources)

    def collide(destination: Path) -> None:
        if destination.name == "config.yaml":
            destination.write_bytes(b"racer")

    monkeypatch.setattr(module, "_before_no_clobber_promote", collide)

    with pytest.raises(FileExistsError, match="already exists"):
        module.write_angular5_artifacts(layout, sources=sources, outcome=outcome)

    assert layout.config_snapshot.read_bytes() == b"racer"
    assert (layout.run_dir / ".terminal.failed").is_dir()
    assert not (layout.artifacts_dir / "run_manifest.json").exists()
    with pytest.raises(RuntimeError, match="failed"):
        module.write_angular5_artifacts(layout, sources=sources, outcome=outcome)


def test_assert_sources_unchanged_detects_fixture_mutation(tmp_path) -> None:
    sources, _ = _fixture_sources(tmp_path)
    sources.receipts["higgs_root"].path.write_bytes(b"changed")

    with pytest.raises(RuntimeError, match="changed before publication"):
        assert_angular5_sources_unchanged(sources)
