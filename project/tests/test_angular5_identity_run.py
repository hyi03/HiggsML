from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

import awkward as ak
import gzip
import numpy as np
import pandas as pd
import pytest
import uproot
import yaml

from src import angular5_enrichment as enrichment_safety
from src import angular5_identity_run as identity_run
from src.angular5_enrichment_run import Angular5SourceReceipt
from src.angular5_identity import build_source_identity_baseline
from src.angular5_identity_run import (
    IdentityConfig,
    IdentitySources,
    assert_identity_sources_unchanged,
    build_identity_mc,
    claim_identity_output,
    load_identity_config,
    publish_identity_manifest,
    resolve_identity_sources,
    write_identity_artifacts,
)
from src.pipeline import prepare_sample
from src.selection import SelectionConfig
from src.weights import MCNormalization
from test_angular5_enrichment import _event, _write_open_data


PROJECT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT / "config/angular5_identity_mc_dsid363490_r2.yaml"
OUTPUT_RUN = "runs/angular5-identity-mc-363490-2026-08-26-r2"
R3_CONFIG_PATH = (
    PROJECT / "config/angular5_identity_mc_dsid363490_r3_arm64.yaml"
)
R3_OUTPUT_RUN = "runs/angular5-identity-mc-363490-2026-08-26-r3-arm64"
SOURCE_PATHS = {
    "identity_config": "config/angular5_identity_mc_dsid363490_r2.yaml",
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
SUCCESS_FILES = {
    "config.yaml",
    "processed/mc_events_source_identity.csv.gz",
    "artifacts/identity_validation.json",
    "artifacts/run_manifest.json",
}


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


def _write_release22_events(path: Path, events: list[dict]) -> None:
    scalars = (
        "runNumber",
        "eventNumber",
        "channelNumber",
        "lep_n",
        "trigE",
        "trigM",
        "mcWeight",
    )
    branches = {name: np.asarray([event[name] for event in events]) for name in scalars}
    branches.update(
        {
            physical: ak.Array([event[canonical] for event in events])
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
    for name, value in {
        "xsec": 0.5,
        "kfac": 1.0,
        "filteff": 1.0,
        "sum_of_weights": 100.0,
    }.items():
        branches[name] = np.asarray([value] * len(events))
    with uproot.recreate(path) as root:
        root["analysis"] = branches


def _fixture_sources(tmp_path: Path) -> IdentitySources:
    root = tmp_path / "project"
    inputs = root / "inputs"
    inputs.mkdir(parents=True)
    config_path = inputs / "identity.yaml"
    config_path.write_bytes(CONFIG_PATH.read_bytes())
    frozen_path = inputs / "frozen.yaml"
    frozen_path.write_bytes(b"frozen: true\n")
    manifest_path = inputs / "task4a_manifest.json"
    manifest_path.write_text('{"status":"complete"}\n', encoding="utf-8")
    higgs_path = inputs / "higgs.root"
    first = _event(event_number=102001, channel=345060, unit_scale=1.0)
    second = _event(event_number=102001, channel=345060, unit_scale=1.0)
    second["lep_eta"] = [0.35, -0.25, 0.45, -0.35]
    second["lep_phi"] = [0.05, math.pi - 0.05, 1.25, -1.85]
    _write_release22_events(higgs_path, [first, second])
    zz_path = inputs / "zz.root"
    _write_open_data(
        zz_path, _event(event_number=202, channel=363490, unit_scale=1000.0)
    )

    config = load_identity_config(CONFIG_PATH)
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
    table_path = inputs / "mc_events.csv.gz"
    pd.concat([higgs, zz], ignore_index=True).to_csv(table_path, index=False)
    paths = {
        "identity_config": config_path,
        "frozen_config": frozen_path,
        "task4a_manifest": manifest_path,
        "task4a_mc": table_path,
        "higgs_root": higgs_path,
        "zz_root": zz_path,
    }
    return IdentitySources(
        config=config,
        config_bytes=config_path.read_bytes(),
        project_root=root.resolve(),
        receipts={name: _receipt(name, path) for name, path in paths.items()},
    )


def _r3_fixture_sources(tmp_path: Path) -> IdentitySources:
    sources = _fixture_sources(tmp_path)
    config_path = sources.receipts["identity_config"].path
    config_path.write_bytes(R3_CONFIG_PATH.read_bytes())
    return IdentitySources(
        config=load_identity_config(R3_CONFIG_PATH),
        config_bytes=config_path.read_bytes(),
        project_root=sources.project_root,
        receipts={
            **sources.receipts,
            "identity_config": _receipt("identity_config", config_path),
        },
    )


def _fake_project(tmp_path: Path, *, changed: str | None = None) -> Path:
    root = tmp_path / "project"
    for name, relative in SOURCE_PATHS.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if name == changed:
            destination.write_bytes(b"changed\n")
        else:
            os.link(PROJECT / relative, destination)
    return root


def test_identity_config_is_exact_deeply_immutable_and_mc_only():
    config = load_identity_config(CONFIG_PATH)

    assert isinstance(config, IdentityConfig)
    assert config.schema_version == "1.0"
    assert config.output_run == OUTPUT_RUN
    assert config.entry_stop is None
    assert config.chunk_size_events == 50000
    assert set(config.samples) == {"higgs", "zz"}
    assert config.samples["higgs"]["source_sample"] == "higgs_345060"
    assert config.samples["zz"]["source_sample"] == "zz_363490"
    assert config.artifacts == (
        "config.yaml",
        "processed/mc_events_source_identity.csv.gz",
        "artifacts/identity_validation.json",
        "artifacts/run_manifest.json",
    )
    serialized = CONFIG_PATH.read_text(encoding="utf-8").lower()
    assert "data16" not in serialized
    assert "perioda" not in serialized
    with pytest.raises(TypeError):
        config.selection["lepton_quality"]["require_tight_id"] = False
    with pytest.raises(FrozenInstanceError):
        config.output_run = "runs/changed"


def test_r3_arm64_identity_config_is_exact_and_has_no_tolerance_surface():
    config = load_identity_config(R3_CONFIG_PATH)

    assert config.schema_version == "1.0"
    assert config.output_run == R3_OUTPUT_RUN
    assert config.native_arm64_required is True
    serialized = R3_CONFIG_PATH.read_text(encoding="utf-8").lower()
    assert "tolerance" not in serialized
    assert "rtol" not in serialized
    assert "atol" not in serialized

    changed = yaml.safe_load(R3_CONFIG_PATH.read_bytes())
    changed["old_column_tolerance"] = 5e-12
    with pytest.raises(ValueError, match="exact sealed schema"):
        identity_run._load_config_bytes(
            yaml.safe_dump(changed, sort_keys=False).encode("utf-8")
        )


@pytest.mark.parametrize(
    ("machine", "translated", "message"),
    [
        ("x86_64", "0\n", "native arm64"),
        ("arm64", "1\n", "Rosetta"),
    ],
)
def test_r3_arm64_claim_rejects_wrong_architecture_before_output_claim(
    tmp_path, monkeypatch, machine, translated, message
):
    sources = _r3_fixture_sources(tmp_path)
    monkeypatch.setattr(identity_run.platform, "machine", lambda: machine)
    monkeypatch.setattr(
        identity_run.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=translated, stderr=""
        ),
    )

    with pytest.raises(RuntimeError, match=message):
        claim_identity_output(
            sources=sources,
            project_root=sources.project_root,
            working_directory=sources.project_root,
            run_dir=R3_OUTPUT_RUN,
        )

    assert not (sources.project_root / R3_OUTPUT_RUN).exists()


def test_r3_arm64_claim_accepts_missing_translation_sysctl_key(tmp_path, monkeypatch):
    sources = _r3_fixture_sources(tmp_path)
    monkeypatch.setattr(identity_run.platform, "machine", lambda: "arm64")
    calls = []

    def missing_sysctl(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            args=command, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(identity_run.subprocess, "run", missing_sysctl)

    layout = claim_identity_output(
        sources=sources,
        project_root=sources.project_root,
        working_directory=sources.project_root,
        run_dir=R3_OUTPUT_RUN,
    )

    assert layout.run_dir == sources.project_root / R3_OUTPUT_RUN
    assert calls[0][0] == [
        "/usr/sbin/sysctl",
        "-in",
        "sysctl.proc_translated",
    ]


def test_r3_arm64_claim_rejects_failed_translation_sysctl_before_output_claim(
    tmp_path, monkeypatch
):
    sources = _r3_fixture_sources(tmp_path)
    monkeypatch.setattr(identity_run.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(
        identity_run.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            args=command, returncode=1, stdout="", stderr="permission denied"
        ),
    )

    with pytest.raises(RuntimeError, match="could not verify Rosetta state"):
        claim_identity_output(
            sources=sources,
            project_root=sources.project_root,
            working_directory=sources.project_root,
            run_dir=R3_OUTPUT_RUN,
        )

    assert not (sources.project_root / R3_OUTPUT_RUN).exists()


def test_r3_arm64_claim_rejects_unknown_translation_state_before_output_claim(
    tmp_path, monkeypatch
):
    sources = _r3_fixture_sources(tmp_path)
    monkeypatch.setattr(identity_run.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(
        identity_run.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            args=command, returncode=0, stdout="unexpected\n", stderr=""
        ),
    )

    with pytest.raises(RuntimeError, match="could not verify Rosetta state"):
        claim_identity_output(
            sources=sources,
            project_root=sources.project_root,
            working_directory=sources.project_root,
            run_dir=R3_OUTPUT_RUN,
        )

    assert not (sources.project_root / R3_OUTPUT_RUN).exists()


def test_r3_arm64_claim_rejects_missing_sysctl_binary_before_output_claim(
    tmp_path, monkeypatch
):
    sources = _r3_fixture_sources(tmp_path)
    monkeypatch.setattr(identity_run.platform, "machine", lambda: "arm64")

    def missing_sysctl_binary(command, **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(identity_run.subprocess, "run", missing_sysctl_binary)

    with pytest.raises(RuntimeError, match="could not verify Rosetta state"):
        claim_identity_output(
            sources=sources,
            project_root=sources.project_root,
            working_directory=sources.project_root,
            run_dir=R3_OUTPUT_RUN,
        )

    assert not (sources.project_root / R3_OUTPUT_RUN).exists()


def test_r3_claim_rejects_the_failed_r2_output_path(tmp_path, monkeypatch):
    sources = _r3_fixture_sources(tmp_path)
    monkeypatch.setattr(identity_run.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(
        identity_run.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="0\n", stderr=""
        ),
    )

    with pytest.raises(ValueError, match="frozen output path"):
        claim_identity_output(
            sources=sources,
            project_root=sources.project_root,
            working_directory=sources.project_root,
            run_dir=OUTPUT_RUN,
        )

    assert not (sources.project_root / OUTPUT_RUN).exists()


def test_r2_identity_profile_remains_historically_compatible_on_non_arm64(
    tmp_path, monkeypatch
):
    sources = _fixture_sources(tmp_path)
    monkeypatch.setattr(identity_run.platform, "machine", lambda: "x86_64")

    layout = claim_identity_output(
        sources=sources,
        project_root=sources.project_root,
        working_directory=sources.project_root,
        run_dir=OUTPUT_RUN,
    )

    assert layout.run_dir == sources.project_root / OUTPUT_RUN


def test_r3_identity_old_column_comparison_remains_exact(tmp_path):
    sources = _r3_fixture_sources(tmp_path)
    table = sources.receipts["task4a_mc"].path
    frame = pd.read_csv(table)
    frame.loc[0, "mZ1"] = float(frame.loc[0, "mZ1"]) + 1e-12
    frame.to_csv(table, index=False)
    sources = IdentitySources(
        config=sources.config,
        config_bytes=sources.config_bytes,
        project_root=sources.project_root,
        receipts={
            **sources.receipts,
            "task4a_mc": _receipt("task4a_mc", table),
        },
    )

    with pytest.raises(ValueError, match="old-column mismatch: mZ1"):
        build_identity_mc(sources)


def test_r3_identity_evidence_contains_no_tolerance_policy(tmp_path, monkeypatch):
    sources = _r3_fixture_sources(tmp_path)
    monkeypatch.setattr(identity_run.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(
        identity_run.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="0\n", stderr=""
        ),
    )
    layout = claim_identity_output(
        sources=sources,
        project_root=sources.project_root,
        working_directory=sources.project_root,
        run_dir=R3_OUTPUT_RUN,
    )
    outcome = build_identity_mc(sources)
    receipt = write_identity_artifacts(layout, sources=sources, outcome=outcome)
    publish_identity_manifest(
        layout,
        sources=sources,
        receipt=receipt,
        software={"python": "test"},
    )

    evidence = (
        (layout.artifacts_dir / "identity_validation.json").read_text()
        + (layout.artifacts_dir / "run_manifest.json").read_text()
    ).lower()
    assert "tolerance" not in evidence
    assert "rtol" not in evidence
    assert "atol" not in evidence


@pytest.mark.parametrize(
    "mutation",
    [
        lambda raw: raw.__setitem__("extension", True),
        lambda raw: raw.__setitem__("entry_stop", 1),
        lambda raw: raw["samples"].__setitem__("data", {}),
        lambda raw: raw["samples"]["higgs"].__setitem__(
            "source_sample", "higgs.root"
        ),
        lambda raw: raw["selection"].__setitem__("require_zero_charge", False),
    ],
)
def test_identity_config_rejects_any_schema_or_policy_change(tmp_path, mutation):
    raw = yaml.safe_load(CONFIG_PATH.read_bytes())
    mutation(raw)
    path = tmp_path / "changed.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="exact sealed schema"):
        load_identity_config(path)


def test_identity_config_rejects_duplicate_keys_hiding_real_data(tmp_path):
    path = tmp_path / "duplicate.yaml"
    path.write_bytes(
        b"samples:\n  data:\n    path: data/raw/data16_periodA.root\n"
        + CONFIG_PATH.read_bytes()
    )

    with pytest.raises(ValueError, match="duplicate"):
        load_identity_config(path)


def test_identity_source_resolution_binds_six_files_without_parsing(monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: pytest.fail("parsed CSV"))
    monkeypatch.setattr(uproot, "open", lambda *a, **k: pytest.fail("parsed ROOT"))

    sources = resolve_identity_sources(project_root=PROJECT, config_path=CONFIG_PATH)

    assert isinstance(sources, IdentitySources)
    assert set(sources.receipts) == set(SOURCE_PATHS)
    assert {
        name: sources.receipts[name].sha256 for name in FROZEN_HASHES
    } == FROZEN_HASHES
    with pytest.raises(TypeError):
        sources.receipts["extra"] = sources.receipts["higgs_root"]


def test_r3_identity_source_resolution_requires_exact_r3_config_path(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: pytest.fail("parsed CSV"))
    monkeypatch.setattr(uproot, "open", lambda *a, **k: pytest.fail("parsed ROOT"))

    sources = resolve_identity_sources(
        project_root=PROJECT,
        config_path=R3_CONFIG_PATH,
    )

    assert sources.config.output_run == R3_OUTPUT_RUN
    assert sources.config.native_arm64_required is True
    assert sources.receipts["identity_config"].path == R3_CONFIG_PATH.resolve()

    copied = tmp_path / R3_CONFIG_PATH.name
    copied.write_bytes(R3_CONFIG_PATH.read_bytes())
    with pytest.raises(ValueError, match="exact frozen path"):
        resolve_identity_sources(project_root=PROJECT, config_path=copied)


def test_identity_source_resolution_rejects_hash_mismatch_and_wrong_config_path(
    tmp_path,
):
    root = _fake_project(tmp_path, changed="task4a_manifest")
    with pytest.raises(ValueError, match="SHA-256 mismatch.*task4a_manifest"):
        resolve_identity_sources(
            project_root=root,
            config_path=root / SOURCE_PATHS["identity_config"],
        )
    copied = tmp_path / "identity.yaml"
    copied.write_bytes(CONFIG_PATH.read_bytes())
    with pytest.raises(ValueError, match="exact frozen path"):
        resolve_identity_sources(project_root=PROJECT, config_path=copied)


def test_identity_source_resolution_rejects_symlink(tmp_path):
    root = _fake_project(tmp_path)
    target = root / SOURCE_PATHS["frozen_config"]
    target.unlink()
    target.symlink_to(PROJECT / SOURCE_PATHS["frozen_config"])

    with pytest.raises(ValueError, match="symlink"):
        resolve_identity_sources(
            project_root=root,
            config_path=root / SOURCE_PATHS["identity_config"],
        )


def test_identity_claim_is_atomic_fresh_and_fixed(tmp_path):
    sources = _fixture_sources(tmp_path)
    kwargs = {
        "sources": sources,
        "project_root": sources.project_root,
        "working_directory": sources.project_root,
        "run_dir": OUTPUT_RUN,
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: _claim_result(kwargs), range(2)))

    winners = [result for result in results if not isinstance(result, BaseException)]
    losers = [result for result in results if isinstance(result, BaseException)]
    assert len(winners) == 1
    assert len(losers) == 1
    assert isinstance(losers[0], FileExistsError)
    assert {path.name for path in winners[0].run_dir.iterdir()} == {
        "processed",
        "artifacts",
    }


def _claim_result(kwargs):
    try:
        return claim_identity_output(**kwargs)
    except BaseException as error:
        return error


def test_identity_claim_rejects_non_frozen_or_protected_path(tmp_path):
    sources = _fixture_sources(tmp_path)
    for run_dir in ("runs/other", "config/new"):
        with pytest.raises(ValueError, match="frozen output path|protected"):
            claim_identity_output(
                sources=sources,
                project_root=sources.project_root,
                working_directory=sources.project_root,
                run_dir=run_dir,
            )


@pytest.mark.parametrize("failed_child", ["processed", "artifacts"])
def test_identity_claim_records_terminal_when_child_creation_is_interrupted(
    tmp_path, monkeypatch, failed_child
):
    sources = _fixture_sources(tmp_path)
    real_mkdir = identity_run.os.mkdir

    def interrupt_child(path, *args, **kwargs):
        if os.fspath(path) == failed_child:
            raise KeyboardInterrupt()
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(identity_run.os, "mkdir", interrupt_child)

    with pytest.raises(KeyboardInterrupt):
        claim_identity_output(
            sources=sources,
            project_root=sources.project_root,
            working_directory=sources.project_root,
            run_dir=OUTPUT_RUN,
        )

    run_dir = sources.project_root / OUTPUT_RUN
    assert (run_dir / ".terminal.failed").is_dir()
    assert json.loads((run_dir / "failure.json").read_text())["status"] == "failed"
    assert not (run_dir / "artifacts/run_manifest.json").exists()


def test_build_identity_keeps_distinct_entries_for_duplicate_legacy_keys(tmp_path):
    sources = _fixture_sources(tmp_path)

    outcome = build_identity_mc(sources)
    frame = outcome.frame

    duplicates = frame.loc[
        frame.duplicated(
            ["runNumber", "eventNumber", "channelNumber"], keep=False
        )
    ]
    assert duplicates[["source_sample", "source_entry"]].values.tolist() == [
        ["higgs_345060", 0],
        ["higgs_345060", 1],
    ]
    assert outcome.evidence["legacy_duplicate_groups"] == 1
    assert outcome.evidence["legacy_duplicate_rows"] == 2


@pytest.mark.skipif(
    not (PROJECT / SOURCE_PATHS["task4a_mc"]).exists()
    or not (PROJECT / SOURCE_PATHS["higgs_root"]).exists(),
    reason="frozen MC inputs are transferred outside Git",
)
def test_real_frozen_table_reports_exact_duplicate_source_entries_and_tokens():
    payload = (PROJECT / SOURCE_PATHS["task4a_mc"]).read_bytes()
    authoritative = pd.read_csv(
        PROJECT / SOURCE_PATHS["task4a_mc"], compression="gzip"
    )
    assert len(authoritative) == 199_104
    duplicate_rows = authoritative.loc[
        authoritative.duplicated(
            ["runNumber", "eventNumber", "channelNumber"], keep=False
        )
    ]
    assert duplicate_rows[
        ["runNumber", "eventNumber", "channelNumber"]
    ].drop_duplicates().values.tolist() == [
        [284500, 102001, 345060],
        [284500, 1136001, 345060],
    ]

    expected_entries = {
        102001: [173348, 345900],
        1136001: [340911, 342358],
    }
    with uproot.open(PROJECT / SOURCE_PATHS["higgs_root"]) as root:
        tree = root["analysis"]
        for event_number, entries in expected_entries.items():
            for entry in entries:
                values = tree.arrays(
                    ["runNumber", "eventNumber", "channelNumber"],
                    entry_start=entry,
                    entry_stop=entry + 1,
                    library="np",
                )
                assert [
                    int(values["runNumber"][0]),
                    int(values["eventNumber"][0]),
                    int(values["channelNumber"][0]),
                ] == [284500, event_number, 345060]

    reconstructed = {}
    for sample_name, channel, offset in (
        ("higgs_345060", 345060, 1_000_000),
        ("zz_363490", 363490, 2_000_000),
    ):
        sample = authoritative.loc[authoritative["channelNumber"] == channel].copy()
        sample["source_sample"] = sample_name
        sample["source_entry"] = np.arange(len(sample), dtype=np.int64) + offset
        if channel == 345060:
            for event_number, entries in expected_entries.items():
                positions = sample.index[sample["eventNumber"] == event_number]
                assert len(positions) == 2
                sample.loc[positions, "source_entry"] = entries
        reconstructed[sample_name] = sample.reset_index(drop=True)

    outcome = build_source_identity_baseline(payload, reconstructed)

    assert outcome.evidence["legacy_duplicate_groups"] == 2
    assert outcome.evidence["legacy_duplicate_rows"] == 4
    details = outcome.evidence["legacy_duplicate_details"]
    assert [detail["legacy_key"]["eventNumber"] for detail in details] == [
        102001,
        1136001,
    ]
    assert [
        [identity["source_entry"] for identity in detail["canonical_identities"]]
        for detail in details
    ] == [[173348, 345900], [340911, 342358]]
    old_records = gzip.decompress(payload).splitlines()
    final_records = gzip.decompress(outcome.table_payload).splitlines()
    assert len(old_records) == len(final_records)
    assert all(
        final.startswith(old + b",")
        for old, final in zip(old_records[1:], final_records[1:], strict=True)
    )


def test_build_identity_rejects_authoritative_row_order_swap(tmp_path):
    sources = _fixture_sources(tmp_path)
    table = sources.receipts["task4a_mc"].path
    frame = pd.read_csv(table)
    frame.iloc[[1, 0, 2]].to_csv(table, index=False)
    sources = IdentitySources(
        config=sources.config,
        config_bytes=sources.config_bytes,
        project_root=sources.project_root,
        receipts={
            **sources.receipts,
            "task4a_mc": _receipt("task4a_mc", table),
        },
    )

    with pytest.raises(ValueError, match="old-column mismatch"):
        build_identity_mc(sources)


def test_build_identity_refuses_root_swap_even_if_original_path_is_restored(
    tmp_path, monkeypatch
):
    sources = _fixture_sources(tmp_path)
    target = sources.receipts["higgs_root"].path
    backup = target.with_name("higgs-original.root")
    replacement = target.with_name("higgs-replacement.root")
    replacement.write_bytes(target.read_bytes())
    swapped = False

    def swap_after_open(name, path):
        nonlocal swapped
        if name == "higgs_root" and not swapped:
            target.rename(backup)
            replacement.rename(target)
            swapped = True

    monkeypatch.setattr(
        enrichment_safety, "_after_receipt_descriptor_opened", swap_after_open
    )

    with pytest.raises(RuntimeError, match="changed"):
        build_identity_mc(sources)
    assert swapped


def test_identity_publication_is_manifest_last_and_exact(tmp_path):
    sources = _fixture_sources(tmp_path)
    layout = claim_identity_output(
        sources=sources,
        project_root=sources.project_root,
        working_directory=sources.project_root,
        run_dir=OUTPUT_RUN,
    )
    outcome = build_identity_mc(sources)

    receipt = write_identity_artifacts(layout, sources=sources, outcome=outcome)
    assert not (layout.artifacts_dir / "run_manifest.json").exists()
    manifest = publish_identity_manifest(
        layout, sources=sources, receipt=receipt, software={"python": "test"}
    )

    files = {
        path.relative_to(layout.run_dir).as_posix()
        for path in layout.run_dir.rglob("*")
        if path.is_file()
    }
    assert files == SUCCESS_FILES
    assert manifest["status"] == "complete"
    assert manifest["join_key"] == ["source_sample", "source_entry"]
    assert set(manifest["inputs"]) == set(SOURCE_PATHS)
    assert manifest["outputs"][
        "processed/mc_events_source_identity.csv.gz"
    ]["row_count"] == 3


def test_identity_source_freshness_detects_replacement(tmp_path):
    sources = _fixture_sources(tmp_path)
    target = sources.receipts["task4a_manifest"].path
    replacement = target.with_name("replacement.json")
    replacement.write_bytes(target.read_bytes())
    replacement.replace(target)

    with pytest.raises(RuntimeError, match="changed.*task4a_manifest"):
        assert_identity_sources_unchanged(sources)
