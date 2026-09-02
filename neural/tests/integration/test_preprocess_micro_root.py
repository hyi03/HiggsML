from __future__ import annotations

from dataclasses import replace
import json
from math import cosh, pi
from pathlib import Path

import awkward as ak
import pandas as pd
import pytest
import uproot

from src.artifacts.manifest import sha256_file
from src.config import PreprocessRunConfig, load_preprocess_protocol
from src.config import InputBindingError
from src.preprocessing import pipeline as pipeline_module
from src.preprocessing.pipeline import execute_preprocess, prepare_table
from src.preprocessing.root_reader import iter_events


PROJECT = Path(__file__).resolve().parents[2]


def _canonical_events(dsid: int, *, mev: bool) -> dict:
    pt = [40.0, 35.0, 30.0, 25.0]
    eta = [0.2, -0.2, 0.4, -0.4]
    scale = 1000.0 if mev else 1.0
    event = {
        "runNumber": [284500, 284500],
        "eventNumber": [1001, 1002],
        "channelNumber": [dsid, dsid],
        "lep_n": [4, 4],
        "lep_pt": ak.Array([[p * scale for p in pt]] * 2),
        "lep_eta": ak.Array([eta] * 2),
        "lep_phi": ak.Array([[0.0, pi, 1.1, 1.1 + pi]] * 2),
        "lep_e": ak.Array([[p * cosh(e) * scale for p, e in zip(pt, eta)]] * 2),
        "lep_charge": ak.Array([[-1, 1, -1, 1]] * 2),
        "lep_type": ak.Array([[11, 11, 13, 13]] * 2),
        "trigE": [True, True],
        "trigM": [False, False],
        "lep_isTrigMatched": ak.Array([[True, False, False, False]] * 2),
        "lep_isTightID": ak.Array([[True] * 4] * 2),
        "lep_track_iso": ak.Array([[1.0 * scale] * 4] * 2),
        "lep_calo_iso": ak.Array([[1.0 * scale] * 4] * 2),
        "lep_d0sig": ak.Array([[1.0] * 4] * 2),
        "lep_z0": ak.Array([[0.1] * 4] * 2),
        "mcWeight": [1.0, -0.5],
    }
    return event


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    higgs = tmp_path / "higgs.root"
    zz = tmp_path / "zz_363490.root"
    higgs_events = _canonical_events(345060, mev=False)
    higgs_events.update(
        xsec=[28.3, 28.3], kfac=[1.717, 1.717], filteff=[0.000124, 0.000124],
        sum_of_weights=[45231011.19517517, 45231011.19517517],
    )
    higgs_events["lep_ptvarcone30"] = higgs_events.pop("lep_track_iso")
    higgs_events["lep_topoetcone20"] = higgs_events.pop("lep_calo_iso")
    with uproot.recreate(higgs) as root:
        root["analysis"] = higgs_events
    zz_events = _canonical_events(363490, mev=True)
    zz_profile_names = {
        "lep_e": "lep_E", "lep_isTrigMatched": "lep_trigMatched",
        "lep_track_iso": "lep_ptcone30", "lep_calo_iso": "lep_etcone20",
        "lep_d0sig": "lep_tracksigd0pvunbiased",
    }
    zz_events = {zz_profile_names.get(key, key): value for key, value in zz_events.items()}
    with uproot.recreate(zz) as root:
        root["mini"] = zz_events
    return higgs, zz


def _bound_synthetic_protocol(higgs: Path, zz: Path):
    protocol = load_preprocess_protocol(PROJECT / "config/preprocess_protocol_v1.yaml")
    samples = {
        "higgs": replace(
            protocol.samples["higgs"], sha256=sha256_file(higgs), expected_entry_count=2
        ),
        "zz": replace(
            protocol.samples["zz"], sha256=sha256_file(zz), expected_entry_count=2
        ),
    }
    return replace(protocol, samples=samples)


def test_micro_root_pipeline_is_chunk_independent_and_mc_only(tmp_path: Path) -> None:
    higgs, zz = _write_inputs(tmp_path)
    protocol = load_preprocess_protocol(PROJECT / "config/preprocess_protocol_v1.yaml")
    paths = {"higgs": higgs, "zz": zz}

    one, cutflows, summaries, _ = prepare_table(
        protocol, PreprocessRunConfig(paths, 1, b"test"), verify_hashes=False
    )
    many, _, _, _ = prepare_table(
        protocol, PreprocessRunConfig(paths, 100, b"test"), verify_hashes=False
    )

    pd.testing.assert_frame_equal(one, many)
    assert tuple(one.columns) == protocol.output_columns
    assert one["source_sample"].tolist() == ["higgs_345060"] * 2 + ["zz_363490"] * 2
    assert one.groupby("source_sample")["source_entry"].apply(list).tolist() == [[0, 1], [0, 1]]
    assert set(cutflows) == {"higgs_345060", "zz_363490"}
    assert all(value["selected_count"] == 2 for value in summaries.values())
    assert one.groupby("source_sample")["train_weight"].mean().to_dict() == pytest.approx(
        {"higgs_345060": 1.0, "zz_363490": 1.0}
    )
    assert int((one["physical_weight"] < 0).sum()) == 2
    assert set(one["source_sample"]) == {"higgs_345060", "zz_363490"}
    assert set(one["label"]) == {0, 1}
    assert not {"mcWeight", "xsec", "kfac", "filteff", "sum_of_weights"} & set(
        one.columns
    )


def test_success_publication_is_deterministic_and_manifest_complete(
    tmp_path: Path, monkeypatch
) -> None:
    higgs, zz = _write_inputs(tmp_path)
    protocol = _bound_synthetic_protocol(higgs, zz)
    monkeypatch.setattr(pipeline_module, "load_preprocess_protocol", lambda _: protocol)
    run_config = tmp_path / "run.yaml"
    run_config.write_text(
        "schema_version: '1.0'\nsamples:\n"
        f"  higgs: {{path: '{higgs.as_posix()}'}}\n"
        f"  zz: {{path: '{zz.as_posix()}'}}\n"
        "resources: {chunk_size_events: 1}\n",
        encoding="utf-8",
    )
    runs = tmp_path / "runs"
    for name in ("first", "second"):
        execute_preprocess(
            protocol_path=PROJECT / "config/preprocess_protocol_v1.yaml",
            run_config_path=run_config,
            run_dir=runs / name,
            allowed_root=runs,
        )

    first, second = runs / "first", runs / "second"
    assert (first / "processed/mc_events.csv.gz").read_bytes() == (
        second / "processed/mc_events.csv.gz"
    ).read_bytes()
    summary = json.loads((first / "artifacts/mc_summary.json").read_text(encoding="utf-8"))
    assert summary["identity"]["legacy_duplicate_groups"] == 0
    assert summary["identity"]["legacy_duplicate_rows"] == 0
    manifest = json.loads((first / "artifacts/manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["schema"]["dtypes"]) == set(protocol.output_columns)
    assert set(manifest["counts"]["per_sample"]) == {"higgs_345060", "zz_363490"}
    assert manifest["software"]["packages"]["numpy"]
    assert manifest["performance"]["peak_memory_bytes"] > 0
    assert {item["path"] for item in manifest["outputs"]} == {
        "config.yaml", "processed/mc_events.csv.gz", "artifacts/cutflow.json",
        "artifacts/mc_summary.json",
    }


@pytest.mark.parametrize("mutation", ["missing", "source_entry"])
def test_root_schema_rejections_are_fail_closed(
    tmp_path: Path, mutation: str
) -> None:
    protocol = load_preprocess_protocol(PROJECT / "config/preprocess_protocol_v1.yaml")
    sample = protocol.samples["higgs"]
    events = _canonical_events(345060, mev=False)
    events.update(
        xsec=[28.3, 28.3], kfac=[1.717, 1.717], filteff=[0.000124, 0.000124],
        sum_of_weights=[45231011.19517517, 45231011.19517517],
    )
    events["lep_ptvarcone30"] = events.pop("lep_track_iso")
    events["lep_topoetcone20"] = events.pop("lep_calo_iso")
    if mutation == "missing":
        events.pop("lep_phi")
    else:
        events["source_entry"] = [0, 1]
    path = tmp_path / f"{mutation}.root"
    with uproot.recreate(path) as root:
        root["analysis"] = events

    with pytest.raises(InputBindingError):
        list(iter_events(path, sample, 1, verify_entry_count=False))


def test_root_reader_ignores_unmapped_branches(tmp_path: Path) -> None:
    protocol = load_preprocess_protocol(PROJECT / "config/preprocess_protocol_v1.yaml")
    sample = protocol.samples["higgs"]
    events = _canonical_events(345060, mev=False)
    events.update(
        xsec=[28.3, 28.3], kfac=[1.717, 1.717], filteff=[0.000124, 0.000124],
        sum_of_weights=[45231011.19517517, 45231011.19517517],
    )
    events["lep_ptvarcone30"] = events.pop("lep_track_iso")
    events["lep_topoetcone20"] = events.pop("lep_calo_iso")
    events["unexpected"] = [1, 1]
    path = tmp_path / "extra.root"
    with uproot.recreate(path) as root:
        root["analysis"] = events

    loaded = list(iter_events(path, sample, 1, verify_entry_count=False))

    assert len(loaded) == 2
    assert "unexpected" not in loaded[0]
    assert set(loaded[0]) == set(sample.branches) | {"source_entry"}


def test_root_reader_releases_file_handle(tmp_path: Path) -> None:
    higgs, _ = _write_inputs(tmp_path)
    protocol = load_preprocess_protocol(PROJECT / "config/preprocess_protocol_v1.yaml")
    assert len(list(iter_events(
        higgs, protocol.samples["higgs"], 1, verify_entry_count=False
    ))) == 2
    higgs.unlink()
    assert not higgs.exists()


def test_hash_mismatch_publishes_input_binding_failure_receipt(tmp_path: Path) -> None:
    higgs, zz = _write_inputs(tmp_path)
    run_config = tmp_path / "run.yaml"
    run_config.write_text(
        "schema_version: '1.0'\nsamples:\n"
        f"  higgs: {{path: '{higgs.as_posix()}'}}\n"
        f"  zz: {{path: '{zz.as_posix()}'}}\n"
        "resources: {chunk_size_events: 1}\n",
        encoding="utf-8",
    )
    runs = tmp_path / "runs"
    target = runs / "failed"

    try:
        execute_preprocess(
            protocol_path=PROJECT / "config/preprocess_protocol_v1.yaml",
            run_config_path=run_config,
            run_dir=target,
            allowed_root=runs,
        )
    except InputBindingError:
        pass
    else:
        raise AssertionError("synthetic input must not satisfy production hashes")

    receipt = json.loads((target / "failure.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["exit_code"] == 3
    assert receipt["failed_at_utc"].endswith("+00:00")
