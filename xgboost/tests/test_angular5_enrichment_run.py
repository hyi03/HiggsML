from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import hashlib
import os
from pathlib import Path

import pandas as pd
import pytest
import uproot
import yaml

from src import angular5_enrichment_run as angular5_run
from src.angular5_enrichment_run import (
    Angular5EnrichmentConfig,
    Angular5Sources,
    assert_angular5_sources_unchanged,
    claim_angular5_output,
    load_angular5_enrichment_config,
    resolve_angular5_sources,
)


PROJECT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT / "config/angular5_mc_dsid363490.yaml"
SOURCE_PATHS = {
    "enrichment_config": "config/angular5_mc_dsid363490.yaml",
    "frozen_config": "config/dsid363490.yaml",
    "task4a_manifest": (
        "runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json"
    ),
    "task4a_mc": (
        "runs/full-baseline-363490-2026-08-11-r2/processed/mc_events.csv.gz"
    ),
    "higgs_root": "data/raw/higgs.root",
    "zz_root": "data/raw/zz_363490.root",
}
FROZEN_HASHES = {
    "frozen_config": "0282cfa965228e036f4ada3c010bd7d40b1b14e56c2aa33551784683237cd320",
    "task4a_manifest": "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8",
    "task4a_mc": "1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e",
    "higgs_root": "5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0",
    "zz_root": "76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07",
}
EXPECTED_SELECTION = {
    "require_exactly_four_leptons": True,
    "allowed_lepton_types": [11, 13],
    "lepton_pt_thresholds_gev": [20.0, 15.0, 10.0, 7.0],
    "electron_max_abs_eta": 2.47,
    "muon_max_abs_eta": 2.7,
    "require_zero_charge": True,
    "min_all_sfos_mass_gev": 5.0,
    "z1_mass_window_gev": [50.0, 106.0],
    "z2_mass": {
        "min_mode": "fixed",
        "fixed_min_gev": 12.0,
        "max_gev": 115.0,
        "sliding": {
            "low_m4l_gev": 140.0,
            "high_m4l_gev": 190.0,
            "low_min_gev": 12.0,
            "high_min_gev": 50.0,
        },
    },
    "m4l_window_gev": [105.0, 160.0],
    "lepton_quality": {
        "enabled": True,
        "require_event_trigger": True,
        "require_trigger_match": True,
        "require_tight_id": True,
        "track_isolation_max": 0.3,
        "calo_isolation_max": 0.3,
        "electron_d0sig_max": 5.0,
        "muon_d0sig_max": 3.0,
        "z0_sintheta_max_mm": 0.5,
    },
}
APPROVED_ARTIFACTS = [
    "config.yaml",
    "processed/mc_events_angular5.csv.gz",
    "artifacts/identity_validation.json",
    "artifacts/angular5_summary.json",
    "artifacts/run_manifest.json",
]


def _raw_config() -> dict:
    raw = yaml.safe_load(CONFIG_PATH.read_bytes())
    assert isinstance(raw, dict)
    return raw


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _thaw(value):
    if isinstance(value, dict) or hasattr(value, "items"):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _fake_project(tmp_path: Path, *, special: tuple[str, str] | None = None) -> Path:
    root = tmp_path / "project"
    for name, relative in SOURCE_PATHS.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        kind = special[1] if special is not None and special[0] == name else "hardlink"
        if kind == "directory":
            destination.mkdir()
        elif kind == "symlink":
            destination.symlink_to(PROJECT / relative)
        elif kind == "changed":
            destination.write_bytes(b"changed frozen input\n")
        elif kind == "copy":
            destination.write_bytes((PROJECT / relative).read_bytes())
        else:
            os.link(PROJECT / relative, destination)
    return root


def test_config_is_exact_mc_only_copy_of_frozen_policy() -> None:
    config = load_angular5_enrichment_config(CONFIG_PATH)

    assert isinstance(config, Angular5EnrichmentConfig)
    assert config.schema_version == "1.0"
    assert config.output_run == "runs/angular5-mc-363490-2026-08-26"
    assert config.tree_name == "analysis"
    assert config.momentum_unit == "GeV"
    assert config.entry_stop is None
    assert config.chunk_size_events == 50000
    assert config.luminosity_pb == 10000.0
    assert set(config.samples) == {"higgs", "zz"}
    assert dict(config.samples["higgs"]) == {
        "path": "data/raw/higgs.root",
        "sha256": FROZEN_HASHES["higgs_root"],
        "channel_numbers": (345060,),
        "label": 1,
        "input_profile": "release22",
    }
    assert dict(config.samples["zz"]) == {
        "path": "data/raw/zz_363490.root",
        "sha256": FROZEN_HASHES["zz_root"],
        "channel_numbers": (363490,),
        "label": 0,
        "input_profile": "open_data_2020",
        "normalization": {
            "source": "official_metadata",
            "xsec_pb": 1.2564,
            "k_factor": 1.0,
            "filter_efficiency": 1.0,
            "sum_of_weights": 7538705.808,
        },
    }
    assert _thaw(config.selection) == EXPECTED_SELECTION
    assert list(config.artifacts) == APPROVED_ARTIFACTS


def test_config_has_exact_frozen_source_paths_and_hashes_and_no_real_data() -> None:
    raw = _raw_config()
    assert raw["frozen_reference"] == {
        "path": "config/dsid363490.yaml",
        "sha256": FROZEN_HASHES["frozen_config"],
    }
    assert raw["authoritative_mc"] == {
        "manifest_path": SOURCE_PATHS["task4a_manifest"],
        "manifest_sha256": FROZEN_HASHES["task4a_manifest"],
        "table_path": SOURCE_PATHS["task4a_mc"],
        "table_sha256": FROZEN_HASHES["task4a_mc"],
    }
    serialized = yaml.safe_dump(raw).lower()
    assert "data16" not in serialized
    assert "perioda" not in serialized
    assert "label: -1" not in serialized
    assert set(raw["samples"]) == {"higgs", "zz"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw.__setitem__("extension", True),
        lambda raw: raw["samples"].__setitem__("data", {}),
        lambda raw: raw["samples"]["higgs"].__setitem__("input_profile", "other"),
        lambda raw: raw.__setitem__("entry_stop", 5000),
        lambda raw: raw["selection"].__setitem__("require_zero_charge", False),
        lambda raw: raw["authoritative_mc"].__setitem__("table_sha256", "0" * 64),
    ],
)
def test_config_rejects_every_schema_or_frozen_policy_change(tmp_path, mutate) -> None:
    raw = _raw_config()
    mutate(raw)
    path = tmp_path / "changed.yaml"
    _write_yaml(path, raw)

    with pytest.raises(ValueError, match="exact sealed schema"):
        load_angular5_enrichment_config(path)


@pytest.mark.parametrize(
    "payload",
    [
        (
            b"samples:\n"
            b"  data:\n"
            b"    path: data/raw/data16_periodA.root\n"
            + CONFIG_PATH.read_bytes()
        ),
        CONFIG_PATH.read_bytes().replace(
            b"  higgs:\n    path: data/raw/higgs.root\n",
            b"  higgs:\n"
            b"    path: data/raw/data16_periodA.root\n"
            b"    path: data/raw/higgs.root\n",
        ),
    ],
    ids=["top-level", "nested"],
)
def test_config_rejects_duplicate_mapping_keys_that_hide_real_data(tmp_path, payload) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_bytes(payload)

    with pytest.raises(ValueError, match="duplicate"):
        load_angular5_enrichment_config(path)


def test_config_selection_is_deeply_immutable() -> None:
    config = load_angular5_enrichment_config(CONFIG_PATH)

    with pytest.raises(TypeError):
        config.selection["lepton_quality"]["require_tight_id"] = False
    with pytest.raises(AttributeError):
        config.selection["lepton_pt_thresholds_gev"].append(5.0)


def test_source_resolution_binds_all_six_regular_files_without_parsing_tables_or_root(
    monkeypatch,
) -> None:
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: pytest.fail("CSV was parsed"))
    monkeypatch.setattr(uproot, "open", lambda *a, **k: pytest.fail("ROOT was parsed"))

    sources = resolve_angular5_sources(
        project_root=PROJECT,
        config_path=CONFIG_PATH,
    )

    assert isinstance(sources, Angular5Sources)
    assert set(sources.receipts) == set(SOURCE_PATHS)
    for name, receipt in sources.receipts.items():
        metadata = os.stat(PROJECT / SOURCE_PATHS[name], follow_symlinks=False)
        assert receipt.path == (PROJECT / SOURCE_PATHS[name]).resolve()
        assert receipt.device == metadata.st_dev
        assert receipt.inode == metadata.st_ino
        assert receipt.size_bytes == metadata.st_size
        assert len(receipt.sha256) == 64
    assert {
        name: sources.receipts[name].sha256 for name in FROZEN_HASHES
    } == FROZEN_HASHES
    with pytest.raises(TypeError):
        sources.receipts["extra"] = sources.receipts["higgs_root"]
    with pytest.raises(FrozenInstanceError):
        sources.receipts["higgs_root"].size_bytes = 0


@pytest.mark.parametrize("kind", ["symlink", "directory"])
def test_source_resolution_rejects_symlink_and_non_regular_input(tmp_path, kind) -> None:
    root = _fake_project(tmp_path, special=("frozen_config", kind))

    with pytest.raises(ValueError, match="symlink|regular file"):
        resolve_angular5_sources(
            project_root=root,
            config_path=root / SOURCE_PATHS["enrichment_config"],
        )


def test_source_resolution_rejects_fixed_hash_mismatch(tmp_path) -> None:
    root = _fake_project(tmp_path, special=("task4a_manifest", "changed"))

    with pytest.raises(ValueError, match="SHA-256 mismatch.*task4a_manifest"):
        resolve_angular5_sources(
            project_root=root,
            config_path=root / SOURCE_PATHS["enrichment_config"],
        )


def test_source_resolution_rejects_config_outside_exact_project_path(tmp_path) -> None:
    copied = tmp_path / "angular5.yaml"
    copied.write_bytes(CONFIG_PATH.read_bytes())

    with pytest.raises(ValueError, match="exact frozen path"):
        resolve_angular5_sources(project_root=PROJECT, config_path=copied)


def test_source_resolution_refuses_ancestor_symlink_swap_during_open(
    tmp_path, monkeypatch
) -> None:
    root = _fake_project(tmp_path)
    raw = root / "data/raw"
    original = root / "data/raw-original"
    attacker = root / "attacker"
    attacker.mkdir()
    os.link(PROJECT / SOURCE_PATHS["higgs_root"], attacker / "higgs.root")
    os.link(PROJECT / SOURCE_PATHS["zz_root"], attacker / "zz_363490.root")
    real_open = os.open
    swapped = False

    def swap_before_zz_open(path, flags, *args, **kwargs):
        nonlocal swapped
        path_text = os.fspath(path)
        is_absolute_target = os.path.isabs(path_text) and path_text.endswith(
            "/data/raw/zz_363490.root"
        )
        is_descriptor_target = (
            path_text == "zz_363490.root" and kwargs.get("dir_fd") is not None
        )
        if not swapped and (is_absolute_target or is_descriptor_target):
            raw.rename(original)
            raw.symlink_to(attacker, target_is_directory=True)
            swapped = True
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(angular5_run.os, "open", swap_before_zz_open)

    with pytest.raises(ValueError, match="symlink|changed"):
        resolve_angular5_sources(
            project_root=root,
            config_path=root / SOURCE_PATHS["enrichment_config"],
        )
    assert swapped


def test_source_resolution_rejects_mutation_at_end_of_hashing(tmp_path, monkeypatch) -> None:
    root = _fake_project(tmp_path, special=("enrichment_config", "copy"))
    target = root / SOURCE_PATHS["enrichment_config"]
    target_inode = target.stat().st_ino
    real_read = os.read
    mutated = False

    def mutate_on_eof(descriptor, count):
        nonlocal mutated
        chunk = real_read(descriptor, count)
        if not chunk and not mutated and os.fstat(descriptor).st_ino == target_inode:
            with target.open("ab") as stream:
                stream.write(b"# mutation during hash\n")
            mutated = True
        return chunk

    monkeypatch.setattr(angular5_run.os, "read", mutate_on_eof)

    with pytest.raises(RuntimeError, match="changed during hashing"):
        resolve_angular5_sources(
            project_root=root,
            config_path=root / SOURCE_PATHS["enrichment_config"],
        )
    assert mutated


def test_claim_is_fixed_fresh_atomic_and_creates_only_approved_directories(tmp_path) -> None:
    root = _fake_project(tmp_path)
    sources = resolve_angular5_sources(
        project_root=root,
        config_path=root / SOURCE_PATHS["enrichment_config"],
    )
    kwargs = {
        "sources": sources,
        "project_root": root,
        "working_directory": root,
        "run_dir": Path("runs/angular5-mc-363490-2026-08-26"),
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: _claim_result(kwargs), range(2)))

    winners = [value for value in results if not isinstance(value, BaseException)]
    losers = [value for value in results if isinstance(value, BaseException)]
    assert len(winners) == 1
    assert len(losers) == 1
    assert isinstance(losers[0], FileExistsError)
    layout = winners[0]
    assert layout.run_dir == root / "runs/angular5-mc-363490-2026-08-26"
    assert layout.directory_identities is not None
    assert {entry.name for entry in layout.run_dir.iterdir()} == {
        "processed",
        "artifacts",
    }


def _claim_result(kwargs: dict):
    try:
        return claim_angular5_output(**kwargs)
    except BaseException as error:
        return error


@pytest.mark.parametrize(
    "run_dir",
    [
        Path("config/new"),
        Path("data/new"),
        Path("runs/full-baseline-363490-2026-08-11-r2/new"),
    ],
)
def test_claim_refuses_protected_path_even_when_it_is_fresh(tmp_path, run_dir) -> None:
    root = _fake_project(tmp_path)
    sources = resolve_angular5_sources(
        project_root=root,
        config_path=root / SOURCE_PATHS["enrichment_config"],
    )

    with pytest.raises(ValueError, match="protected"):
        claim_angular5_output(
            sources=sources,
            project_root=root,
            working_directory=root,
            run_dir=run_dir,
        )


def test_claim_rejects_non_frozen_output_path(tmp_path) -> None:
    root = _fake_project(tmp_path)
    sources = resolve_angular5_sources(
        project_root=root,
        config_path=root / SOURCE_PATHS["enrichment_config"],
    )

    with pytest.raises(ValueError, match="frozen output path"):
        claim_angular5_output(
            sources=sources,
            project_root=root,
            working_directory=root,
            run_dir="runs/other",
        )


def test_source_freshness_detects_same_size_inode_replacement_before_publication(
    tmp_path,
) -> None:
    root = _fake_project(tmp_path)
    sources = resolve_angular5_sources(
        project_root=root,
        config_path=root / SOURCE_PATHS["enrichment_config"],
    )
    target = root / SOURCE_PATHS["task4a_manifest"]
    old = target.read_bytes()
    replacement = target.with_name("replacement.json")
    replacement.write_bytes(old)
    replacement.replace(target)

    with pytest.raises(RuntimeError, match="changed.*task4a_manifest"):
        assert_angular5_sources_unchanged(sources)


def test_source_freshness_accepts_unchanged_bound_sources(tmp_path) -> None:
    root = _fake_project(tmp_path)
    sources = resolve_angular5_sources(
        project_root=root,
        config_path=root / SOURCE_PATHS["enrichment_config"],
    )

    assert_angular5_sources_unchanged(sources)
    config_receipt = sources.receipts["enrichment_config"]
    assert config_receipt.sha256 == hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
