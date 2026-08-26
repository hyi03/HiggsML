from __future__ import annotations

import gzip
import hashlib
import io
from dataclasses import replace
from pathlib import Path

import awkward as ak
import math
import numpy as np
import pandas as pd
import pytest
import uproot

from src.angular5_enrichment_r3_arm64_run import (
    Angular5R3Arm64Sources,
    load_angular5_r3_arm64_config,
)
from src.angular5_enrichment_run import Angular5SourceReceipt


PROJECT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT / "config/angular5_mc_dsid363490_r3_arm64.yaml"


def _event(event_number: int, channel: int, unit_scale: float) -> dict:
    pt = np.asarray([45.0, 42.0, 20.0, 18.0]) * unit_scale
    return {
        "runNumber": 284500, "eventNumber": event_number, "channelNumber": channel,
        "lep_n": 4, "lep_pt": pt.tolist(), "lep_eta": [0.3, -0.2, 0.4, -0.3],
        "lep_phi": [0.0, math.pi, 1.2, -1.9],
        "lep_e": (pt * 1.1).tolist(), "lep_charge": [-1, 1, -1, 1],
        "lep_type": [11, 11, 13, 13], "trigE": True, "trigM": False,
        "lep_isTrigMatched": [True] * 4, "lep_isTightID": [True] * 4,
        "lep_track_iso": (pt * 0.01).tolist(), "lep_calo_iso": (pt * 0.01).tolist(),
        "lep_d0sig": [0.1] * 4, "lep_z0": [0.1] * 4,
    }


def _write_root(path: Path, event: dict, *, profile: str, copies: int = 1) -> None:
    scalar = ("runNumber", "eventNumber", "channelNumber", "lep_n", "trigE", "trigM")
    branches = {name: np.asarray([event[name]] * copies) for name in scalar}
    mappings = {
        "lep_pt": "lep_pt", "lep_eta": "lep_eta", "lep_phi": "lep_phi",
        "lep_e": "lep_e" if profile == "release22" else "lep_E",
        "lep_charge": "lep_charge", "lep_type": "lep_type",
        "lep_isTrigMatched": "lep_isTrigMatched" if profile == "release22" else "lep_trigMatched",
        "lep_isTightID": "lep_isTightID",
        "lep_track_iso": "lep_ptvarcone30" if profile == "release22" else "lep_ptcone30",
        "lep_calo_iso": "lep_topoetcone20" if profile == "release22" else "lep_etcone20",
        "lep_d0sig": "lep_d0sig" if profile == "release22" else "lep_tracksigd0pvunbiased",
        "lep_z0": "lep_z0",
    }
    branches.update({name: ak.Array([event[key]] * copies) for key, name in mappings.items()})
    if profile == "release22":
        branches.update({name: np.asarray([value] * copies) for name, value in {"mcWeight": 2.0, "xsec": 0.5, "kfac": 1.0, "filteff": 1.0, "sum_of_weights": 100.0}.items()})
    else:
        branches["mcWeight"] = np.asarray([2.0] * copies)
    with uproot.recreate(path) as root:
        root["analysis" if profile == "release22" else "mini"] = branches


def _receipt(name: str, path: Path) -> Angular5SourceReceipt:
    stat = path.stat()
    return Angular5SourceReceipt(name, path.resolve(), stat.st_dev, stat.st_ino, stat.st_size, hashlib.sha256(path.read_bytes()).hexdigest())


def _sources(tmp_path: Path) -> Angular5R3Arm64Sources:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    higgs = inputs / "higgs.root"
    zz = inputs / "zz.root"
    _write_root(higgs, _event(102001, 345060, 1.0), profile="release22", copies=2)
    _write_root(zz, _event(202, 363490, 1000.0), profile="open")
    identity = inputs / "identity.csv.gz"
    raw = (
        b"runNumber,eventNumber,channelNumber,note,source_sample,source_entry\n"
        b"284500,102001,345060,second,higgs_345060,1\n"
        b"284500,202,363490,zz,zz_363490,0\n"
        b"284500,102001,345060,first,higgs_345060,0\n"
    )
    identity.write_bytes(gzip.compress(raw, mtime=0))
    paths = {"enrichment_config": CONFIG, "frozen_config": CONFIG, "identity_manifest": CONFIG, "identity_table": identity, "higgs_root": higgs, "zz_root": zz}
    return Angular5R3Arm64Sources(load_angular5_r3_arm64_config(CONFIG), CONFIG.read_bytes(), tmp_path.resolve(), {name: _receipt(name, path) for name, path in paths.items()})


def test_append_preserves_every_identity_csv_token_and_only_appends_angles() -> None:
    from src.angular5 import ANGULAR5_FEATURES
    from src.angular5_enrichment_r3_arm64 import (
        _append_angular5_preserving_identity_csv,
    )

    raw = (
        b'runNumber,eventNumber,channelNumber,source_sample,source_entry,note\r\n'
        b'1,102001,345060,higgs_345060,173348,"quoted, token"\r\n'
        b'1,102001,345060,higgs_345060,345900,"line one\nline two"\r\n'
    )
    source_payload = gzip.compress(raw, mtime=0)
    source = pd.read_csv(io.BytesIO(source_payload), compression="gzip")
    angles = pd.DataFrame(
        [[0.0, 0.5, -0.5, 0.25, -0.25], [0.1, 0.6, -0.6, 0.5, -0.5]],
        columns=ANGULAR5_FEATURES,
    )

    final_payload = _append_angular5_preserving_identity_csv(
        source_payload, source, angles
    )

    final_raw = gzip.decompress(final_payload)
    assert final_raw.split(b"\r\n", 1)[1].split(b",", 1)[0] == b"1"
    assert b'"quoted, token"' in final_raw
    assert b'"line one\nline two"' in final_raw
    final = pd.read_csv(io.BytesIO(final_payload), compression="gzip")
    pd.testing.assert_frame_equal(
        final[source.columns], source, check_exact=True, check_dtype=False
    )
    assert final.columns.tolist() == source.columns.tolist() + list(ANGULAR5_FEATURES)


def test_identity_validation_reports_legacy_duplicates_without_joining_on_them() -> None:
    from src.angular5_enrichment_r3_arm64 import _legacy_duplicate_evidence

    frame = pd.DataFrame(
        {
            "runNumber": [1, 1, 2, 2],
            "eventNumber": [102001, 102001, 1136001, 1136001],
            "channelNumber": [345060] * 4,
            "source_sample": ["higgs_345060"] * 4,
            "source_entry": [173348, 345900, 340911, 342358],
        }
    )

    groups, rows, details = _legacy_duplicate_evidence(frame)

    assert (groups, rows) == (2, 4)
    assert [entry["source_entry"] for entry in details[0]["canonical_identities"]] == [
        173348,
        345900,
    ]


def test_enrichment_joins_out_of_order_duplicate_legacy_rows_on_source_identity(tmp_path) -> None:
    from src.angular5 import ANGULAR5_FEATURES
    from src.angular5_enrichment_r3_arm64 import enrich_angular5_r3_arm64_mc

    outcome = enrich_angular5_r3_arm64_mc(_sources(tmp_path))

    assert outcome.frame[["source_sample", "source_entry"]].values.tolist() == [
        ["higgs_345060", 1], ["zz_363490", 0], ["higgs_345060", 0]
    ]
    assert outcome.frame.columns[-5:].tolist() == list(ANGULAR5_FEATURES)
    assert outcome.identity_validation["legacy_duplicate_groups"] == 1
    assert outcome.identity_validation["legacy_duplicate_rows"] == 2


@pytest.mark.parametrize("mutation, message", [
    (lambda frame: frame.iloc[:-1], "coverage"),
    (lambda frame: pd.concat([frame, frame.iloc[[0]]]), "duplicate"),
    (lambda frame: frame.assign(source_entry=[99, 0, 1]), "coverage"),
])
def test_enrichment_rejects_missing_extra_or_duplicate_identity(tmp_path, mutation, message) -> None:
    from src.angular5_enrichment_r3_arm64 import enrich_angular5_r3_arm64_mc

    sources = _sources(tmp_path)
    path = sources.receipts["identity_table"].path
    changed = mutation(pd.read_csv(path, compression="gzip"))
    changed.to_csv(path, index=False, compression="gzip")
    sources = replace(sources, receipts={**sources.receipts, "identity_table": _receipt("identity_table", path)})

    with pytest.raises(ValueError, match=message):
        enrich_angular5_r3_arm64_mc(sources)


def test_identity_snapshot_cannot_be_redirected_by_swap_and_restore(tmp_path, monkeypatch) -> None:
    from src import angular5_enrichment_r3_arm64 as module

    sources = _sources(tmp_path)
    path = sources.receipts["identity_table"].path
    original = path.read_bytes()
    alternate = tmp_path / "alternate.csv.gz"
    alternate.write_bytes(gzip.compress(b"not,the,original\n", mtime=0))
    swapped = False

    def swap(name, opened):
        nonlocal swapped
        if name == "identity_table" and not swapped:
            swapped = True
            backup = tmp_path / "backup.csv.gz"
            os.replace(opened, backup)
            os.replace(alternate, opened)
            os.replace(opened, alternate)
            os.replace(backup, opened)

    import os
    monkeypatch.setattr(module, "_after_receipt_descriptor_opened", swap)
    assert len(module.enrich_angular5_r3_arm64_mc(sources).frame) == 3
    assert swapped is True
    assert path.read_bytes() == original
