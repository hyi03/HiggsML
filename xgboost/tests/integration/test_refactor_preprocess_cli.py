from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import awkward as ak
import numpy as np
import pandas as pd
import uproot
import yaml

from src.domain.split import event_split
from src.preprocessing.pipeline import MODEL_FEATURES, OUTPUT_COLUMNS
from src.preprocessing.profiles import resolve_input_profile
from src.preprocessing.reader import iter_mc_events


PROJECT = Path(__file__).resolve().parents[2]


def _event_numbers(channel: int) -> list[int]:
    found: dict[str, list[int]] = {"train": [], "validation": [], "test": []}
    value = 1
    while any(len(items) < 2 for items in found.values()):
        split = event_split(value, channel)
        if len(found[split]) < 2:
            found[split].append(value)
        value += 1
    return [*found["train"], *found["validation"], *found["test"]]


def _canonical_events(channel: int, unit_scale: float) -> dict[str, object]:
    event_numbers = _event_numbers(channel)
    count = len(event_numbers)
    pt = [45.0 * unit_scale, 45.0 * unit_scale, 15.0 * unit_scale, 15.0 * unit_scale]
    return {
        "runNumber": np.asarray([1] * count, dtype=np.int64),
        "eventNumber": np.asarray(event_numbers, dtype=np.int64),
        "channelNumber": np.asarray([channel] * count, dtype=np.int64),
        "lep_n": np.asarray([4] * count, dtype=np.int32),
        "lep_pt": ak.Array([pt] * count),
        "lep_eta": ak.Array([[0.0, 0.0, 0.0, 0.0]] * count),
        "lep_phi": ak.Array(
            [[0.0, math.pi, math.pi / 2, -math.pi / 2]] * count
        ),
        "lep_e": ak.Array([pt] * count),
        "lep_charge": ak.Array([[1, -1, 1, -1]] * count),
        "lep_type": ak.Array([[11, 11, 13, 13]] * count),
        "trigE": np.asarray([True] * count),
        "trigM": np.asarray([False] * count),
        "lep_isTrigMatched": ak.Array([[True] * 4] * count),
        "lep_isTightID": ak.Array([[True] * 4] * count),
        "lep_track_iso": ak.Array([[value * 0.01 for value in pt]] * count),
        "lep_calo_iso": ak.Array([[value * 0.01 for value in pt]] * count),
        "lep_d0sig": ak.Array([[0.1] * 4] * count),
        "lep_z0": ak.Array([[0.1] * 4] * count),
        "mcWeight": np.asarray([1.0] * count),
    }


def _write_root(path: Path, *, profile_name: str, channel: int) -> None:
    profile = resolve_input_profile(profile_name)
    scale = 1.0 if profile.momentum_unit == "GeV" else 1000.0
    canonical = _canonical_events(channel, scale)
    if profile.normalization_in_events:
        count = len(canonical["eventNumber"])
        canonical.update(
            xsec=np.asarray([0.5] * count),
            kfac=np.asarray([1.0] * count),
            filteff=np.asarray([1.0] * count),
            sum_of_weights=np.asarray([100.0] * count),
        )
    branches = {
        profile.branches[name]: values
        for name, values in canonical.items()
        if name in profile.branches
    }
    with uproot.recreate(path) as root:
        root[profile.tree_name] = branches


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    higgs = tmp_path / "higgs.root"
    zz = tmp_path / "zz.root"
    _write_root(higgs, profile_name="release22", channel=345060)
    _write_root(zz, profile_name="open_data_2020", channel=363490)
    run_config = tmp_path / "run.yaml"
    run_config.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "higgs_root": str(higgs),
                "zz_root": str(zz),
                "chunk_size_events": 2,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return higgs, zz, run_config


def _console() -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return Path(sys.executable).with_name(f"higgsml-preprocess{suffix}")


def _run(run_config: Path, run_dir: Path, protocol: Path | None = None):
    return subprocess.run(
        [
            str(_console()),
            "--protocol",
            str(protocol or PROJECT / "config/preprocessing_protocol_v1.yaml"),
            "--run-config",
            str(run_config),
            "--run-dir",
            str(run_dir),
        ],
        cwd=PROJECT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_higgsml_preprocess_micro_root_smoke(tmp_path: Path) -> None:
    _, _, run_config = _write_inputs(tmp_path)
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    first = runs_dir / "preprocess-1"
    second = runs_dir / "preprocess-2"

    first_result = _run(run_config, first)
    second_result = _run(run_config, second)

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    expected = {
        "config.yaml",
        "processed/development.csv.gz",
        "processed/test.csv.gz",
        "artifacts/cutflow.json",
        "artifacts/mc_summary.json",
        "artifacts/manifest.json",
    }
    assert {
        path.relative_to(first).as_posix() for path in first.rglob("*") if path.is_file()
    } == expected
    manifest = json.loads((first / "artifacts/manifest.json").read_text(encoding="utf-8"))
    repeated = json.loads((second / "artifacts/manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "succeeded"
    assert manifest["luminosity_pb"] == 10_000.0
    assert "test_opened" not in manifest
    assert isinstance(manifest["code"]["worktree_dirty"], bool)
    assert {"awkward", "numpy", "pandas", "pyyaml", "uproot", "vector"}.issubset(
        manifest["software"]
    )
    assert manifest["schema"]["model_features"] == list(MODEL_FEATURES)
    assert manifest["schema"]["columns"] == list(OUTPUT_COLUMNS)
    assert set(manifest["inputs"]) == {"higgs", "zz"}
    for partition in ("development", "test"):
        assert (
            manifest["outputs"][partition]["sha256_canonical_csv"]
            == repeated["outputs"][partition]["sha256_canonical_csv"]
        )
        payload = gzip.decompress(
            (first / manifest["outputs"][partition]["path"]).read_bytes()
        )
        assert (
            hashlib.sha256(payload).hexdigest()
            == manifest["outputs"][partition]["sha256_canonical_csv"]
        )
        frame = pd.read_csv(first / manifest["outputs"][partition]["path"])
        assert tuple(frame.columns) == OUTPUT_COLUMNS
    development = pd.read_csv(first / "processed/development.csv.gz")
    test = pd.read_csv(first / "processed/test.csv.gz")
    assert set(development["split"]) == {"train", "validation"}
    assert set(test["split"]) == {"test"}
    assert len(gzip.decompress((first / "processed/test.csv.gz").read_bytes())) > 0
    cutflow = json.loads((first / "artifacts/cutflow.json").read_text(encoding="utf-8"))
    summary = json.loads((first / "artifacts/mc_summary.json").read_text(encoding="utf-8"))
    assert set(cutflow["samples"]) == {"higgs_345060", "zz_363490"}
    assert set(summary["samples"]) == {"higgs_345060", "zz_363490"}


def test_mc_reader_rejects_missing_required_branch(tmp_path: Path) -> None:
    source = tmp_path / "missing.root"
    with uproot.recreate(source) as root:
        root["analysis"] = {"eventNumber": np.asarray([1], dtype=np.int64)}
    try:
        list(
            iter_mc_events(
                source,
                tree_name="analysis",
                chunk_size_events=1,
                profile="release22",
            )
        )
    except KeyError as exc:
        assert "missing required branches" in str(exc)
    else:
        raise AssertionError("missing branch input was accepted")


def test_cli_rejects_real_data_protocol_before_root_read(tmp_path: Path) -> None:
    _, _, run_config = _write_inputs(tmp_path)
    raw = yaml.safe_load(
        (PROJECT / "config/preprocessing_protocol_v1.yaml").read_text(encoding="utf-8")
    )
    raw["samples"]["data"] = {
        "path": "periodA.root",
        "label": -1,
    }
    invalid_protocol = tmp_path / "with-real-data.yaml"
    invalid_protocol.write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    run_dir = runs_dir / "rejected"

    result = _run(run_config, run_dir, invalid_protocol)

    assert result.returncode == 1
    assert "ValueError: unknown samples keys: ['data']" in result.stderr
    assert not run_dir.exists()


def test_cli_rejects_wrong_dsid_root_with_failure_receipt(tmp_path: Path) -> None:
    _, zz, run_config = _write_inputs(tmp_path)
    wrong_higgs = tmp_path / "wrong-higgs-dsid.root"
    _write_root(wrong_higgs, profile_name="release22", channel=363490)
    run_config.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "higgs_root": str(wrong_higgs),
                "zz_root": str(zz),
                "chunk_size_events": 2,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    run_dir = runs_dir / "wrong-dsid"

    result = _run(run_config, run_dir)

    assert result.returncode == 1
    assert "ValueError: higgs: ROOT contains unconfigured channelNumber" in result.stderr
    assert (run_dir / "failure.json").is_file()
    assert not (run_dir / "artifacts/manifest.json").exists()
