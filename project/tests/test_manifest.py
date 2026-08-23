import hashlib
import json
import re
from types import SimpleNamespace

import pytest

from src import provenance
from src.provenance import (
    MCNormalizationInput,
    build_run_manifest,
    discover_git_commit,
    sha256_file,
    software_versions,
)
from src.weights import MCNormalization


def test_sha256_file_matches_exact_bytes(tmp_path):
    path = tmp_path / "input.root"
    content = (b"root-bytes\x00" * 100_000) + b"tail"
    path.write_bytes(content)

    assert sha256_file(path) == hashlib.sha256(content).hexdigest()


def test_sha256_file_rejects_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        sha256_file(tmp_path / "missing.root")


def test_manifest_records_read_policy_normalization_snapshot_and_outputs(tmp_path):
    config_path = tmp_path / "demo.yaml"
    config_path.write_bytes(b"entry_stop: 5000\nchunk_size_events: 50000\n")
    paths = {}
    for name, content in (
        ("zz_700600", b"zz"),
        ("data16_periodA", b"data"),
        ("higgs_345060", b"higgs"),
    ):
        path = tmp_path / f"{name}.root"
        path.write_bytes(content)
        paths[name] = path
    processing = {
        "read_policy": {
            "mode": "full",
            "entry_stop": None,
            "chunk_size_events": 50_000,
        },
        "random_seed": 42,
        "tree_name": "analysis",
        "momentum_unit": "GeV",
        "selection": {"z2_min_mode": "fixed"},
    }
    versions = {
        "python": "3.12.1",
        "numpy": "2.0.0",
        "pandas": "2.2.0",
        "pyyaml": "6.0.2",
        "uproot": "5.0.0",
        "xgboost": "3.0.0",
        "scikit-learn": "1.7.0",
    }

    payload = build_run_manifest(
        config_path=config_path,
        config_snapshot_path="runs/full-baseline-2026-08-10/config.yaml",
        input_paths=paths,
        processing=processing,
        mc_normalizations=[
            MCNormalizationInput(
                "higgs_345060",
                MCNormalization(2.0, 1.2, 0.5, 100.0),
                (345060,),
                10_000.0,
            ),
            MCNormalizationInput(
                "zz_700600",
                MCNormalization(3.0, 1.0, 0.25, 200.0),
                (700600,),
                10_000.0,
            ),
        ],
        output_locations={
            "run_dir": "runs/full-baseline-2026-08-10",
            "processed_dir": "runs/full-baseline-2026-08-10/processed",
            "artifacts_dir": "runs/full-baseline-2026-08-10/artifacts",
        },
        created_at_utc="2026-08-10T17:30:00Z",
        versions=versions,
        git_commit="0123456789abcdef0123456789abcdef01234567",
        cutflow_schema_version="1.0",
    )

    assert payload["schema_version"] == "1.1"
    assert payload["created_at_utc"] == "2026-08-10T17:30:00Z"
    assert payload["software"] == versions
    assert payload["config"] == {
        "path": str(config_path),
        "snapshot_path": "runs/full-baseline-2026-08-10/config.yaml",
        "sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
    }
    assert list(payload["inputs"]) == [
        "data16_periodA",
        "higgs_345060",
        "zz_700600",
    ]
    for name, path in paths.items():
        assert payload["inputs"][name] == {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    assert payload["processing"] == processing
    assert payload["processing"]["read_policy"]["mode"] == "full"
    assert payload["mc_normalization"]["higgs_345060"] == {
        "dsids": [345060],
        "luminosity_pb": 10_000.0,
        "xsec_pb": 2.0,
        "k_factor": 1.2,
        "filter_efficiency": 0.5,
        "sum_of_weights": 100.0,
        "effective_cross_section_pb": 1.2,
    }
    assert payload["git"] == {
        "commit": "0123456789abcdef0123456789abcdef01234567"
    }
    assert payload["outputs"] == {
        "locations": {
            "run_dir": "runs/full-baseline-2026-08-10",
            "processed_dir": "runs/full-baseline-2026-08-10/processed",
            "artifacts_dir": "runs/full-baseline-2026-08-10/artifacts",
        },
        "cutflow_schema_version": "1.0",
        "data_summary_schema_version": "1.0",
        "run_manifest_schema_version": "1.1",
    }


def test_manifest_records_per_sample_input_provenance_and_full_selection(tmp_path):
    config_path = tmp_path / "dsid363490.yaml"
    input_path = tmp_path / "zz_363490.root"
    config_path.write_bytes(b"config")
    input_path.write_bytes(b"root")
    selection = {
        "require_exactly_four_leptons": True,
        "allowed_lepton_types": [11, 13],
        "lepton_quality": {"enabled": True, "track_isolation_max": 0.3},
    }

    payload = build_run_manifest(
        config_path=config_path,
        config_snapshot_path=None,
        input_paths={"zz_363490": input_path},
        processing={
            "read_policy": {"mode": "head", "entry_stop": 5000},
            "selection": selection,
        },
        sample_processing={
            "zz_363490": {
                "input_profile": "open_data_2020",
                "tree_name": "mini",
                "momentum_unit": "MeV",
                "normalization_source": "official_metadata",
            }
        },
        mc_normalizations=[],
        output_locations={},
        created_at_utc="2026-08-11T00:00:00Z",
        versions={},
        git_commit="unavailable",
    )

    assert payload["processing"]["selection"] == selection
    assert payload["processing"]["samples"]["zz_363490"] == {
        "input_profile": "open_data_2020",
        "tree_name": "mini",
        "momentum_unit": "MeV",
        "normalization_source": "official_metadata",
    }
    assert "1.3" not in json.dumps(payload, sort_keys=True)


def test_manifest_rejects_duplicate_mc_normalization_names(tmp_path):
    config_path = tmp_path / "demo.yaml"
    input_path = tmp_path / "higgs.root"
    config_path.write_bytes(b"config")
    input_path.write_bytes(b"root")
    item = MCNormalizationInput(
        "higgs_345060",
        MCNormalization(2.0, 1.0, 1.0, 100.0),
        (345060,),
        10_000.0,
    )

    with pytest.raises(ValueError, match="duplicate MC normalization sample_name"):
        build_run_manifest(
            config_path=config_path,
            config_snapshot_path=None,
            input_paths={"higgs_345060": input_path},
            processing={},
            mc_normalizations=[item, item],
            output_locations={
                "run_dir": None,
                "processed_dir": "data/processed",
                "artifacts_dir": "outputs",
            },
            versions={},
            git_commit="unavailable",
        )


def test_manifest_rejects_empty_normalization_dsids(tmp_path):
    config_path = tmp_path / "demo.yaml"
    input_path = tmp_path / "higgs.root"
    config_path.write_bytes(b"config")
    input_path.write_bytes(b"root")

    with pytest.raises(ValueError, match="dsids must not be empty"):
        build_run_manifest(
            config_path=config_path,
            config_snapshot_path=None,
            input_paths={"higgs_345060": input_path},
            processing={},
            mc_normalizations=[
                MCNormalizationInput(
                    "higgs_345060",
                    MCNormalization(2.0, 1.0, 1.0, 100.0),
                    (),
                    10_000.0,
                )
            ],
            output_locations={
                "run_dir": None,
                "processed_dir": "data/processed",
                "artifacts_dir": "outputs",
            },
            versions={},
            git_commit="unavailable",
        )


@pytest.mark.parametrize("dsids", [(345060.5,), (True,)])
def test_manifest_rejects_non_integer_normalization_dsids(tmp_path, dsids):
    config_path = tmp_path / "demo.yaml"
    input_path = tmp_path / "higgs.root"
    config_path.write_bytes(b"config")
    input_path.write_bytes(b"root")

    with pytest.raises(ValueError, match="channelNumber must contain integers"):
        build_run_manifest(
            config_path=config_path,
            config_snapshot_path=None,
            input_paths={"higgs_345060": input_path},
            processing={},
            mc_normalizations=[
                MCNormalizationInput(
                    "higgs_345060",
                    MCNormalization(2.0, 1.0, 1.0, 100.0),
                    dsids,
                    10_000.0,
                )
            ],
            output_locations={},
            versions={},
            git_commit="unavailable",
        )


@pytest.mark.parametrize("luminosity_pb", [0.0, -1.0, float("nan"), float("inf")])
def test_manifest_rejects_nonpositive_or_nonfinite_luminosity(tmp_path, luminosity_pb):
    config_path = tmp_path / "demo.yaml"
    input_path = tmp_path / "higgs.root"
    config_path.write_bytes(b"config")
    input_path.write_bytes(b"root")

    with pytest.raises(ValueError, match="luminosity_pb must be finite and positive"):
        build_run_manifest(
            config_path=config_path,
            config_snapshot_path=None,
            input_paths={"higgs_345060": input_path},
            processing={},
            mc_normalizations=[
                MCNormalizationInput(
                    "higgs_345060",
                    MCNormalization(2.0, 1.0, 1.0, 100.0),
                    (345060,),
                    luminosity_pb,
                )
            ],
            output_locations={},
            versions={},
            git_commit="unavailable",
        )


def test_manifest_preserves_unlimited_entry_stop(tmp_path):
    config_path = tmp_path / "demo.yaml"
    input_path = tmp_path / "data.root"
    config_path.write_text("entry_stop: null\n", encoding="utf-8")
    input_path.write_bytes(b"data")
    processing = {
        "tree_name": None,
        "momentum_unit": "MeV",
        "entry_stop": None,
        "random_seed": 42,
        "selection": {"z2_min_mode": "sliding"},
    }

    payload = build_run_manifest(
        config_path=config_path,
        config_snapshot_path=None,
        input_paths={"data": input_path},
        processing=processing,
        mc_normalizations=[],
        output_locations={
            "run_dir": None,
            "processed_dir": "data/processed",
            "artifacts_dir": "outputs",
        },
        created_at_utc="2026-08-05T17:30:00Z",
        versions={},
        git_commit="unavailable",
    )

    assert payload["processing"]["entry_stop"] is None


def test_manifest_generates_utc_timestamp_when_not_injected(tmp_path, monkeypatch):
    config_path = tmp_path / "demo.yaml"
    input_path = tmp_path / "data.root"
    config_path.write_bytes(b"config")
    input_path.write_bytes(b"data")
    monkeypatch.setattr(provenance, "software_versions", lambda: {})
    monkeypatch.setattr(provenance, "discover_git_commit", lambda cwd: "unavailable")

    payload = build_run_manifest(
        config_path=config_path,
        config_snapshot_path=None,
        input_paths={"data": input_path},
        processing={
            "tree_name": "analysis",
            "momentum_unit": "GeV",
            "entry_stop": 1,
            "random_seed": 42,
            "selection": {"z2_min_mode": "fixed"},
        },
        mc_normalizations=[],
        output_locations={
            "run_dir": None,
            "processed_dir": "data/processed",
            "artifacts_dir": "outputs",
        },
    )

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", payload["created_at_utc"])


def test_manifest_rejects_non_utc_timestamp(tmp_path):
    config_path = tmp_path / "demo.yaml"
    input_path = tmp_path / "data.root"
    config_path.write_bytes(b"config")
    input_path.write_bytes(b"data")

    with pytest.raises(ValueError, match="UTC"):
        build_run_manifest(
            config_path=config_path,
            config_snapshot_path=None,
            input_paths={"data": input_path},
            processing={},
            mc_normalizations=[],
            output_locations={
                "run_dir": None,
                "processed_dir": "data/processed",
                "artifacts_dir": "outputs",
            },
            created_at_utc="2026-08-05T17:30:00",
            versions={},
            git_commit="unavailable",
        )


def test_software_versions_uses_distribution_metadata(monkeypatch):
    requested = []

    def fake_version(distribution):
        requested.append(distribution)
        if distribution == "xgboost":
            raise provenance.metadata.PackageNotFoundError(distribution)
        return f"version-of-{distribution}"

    monkeypatch.setattr(provenance.platform, "python_version", lambda: "3.12.9")
    monkeypatch.setattr(provenance.metadata, "version", fake_version)

    assert software_versions() == {
        "python": "3.12.9",
        "numpy": "version-of-numpy",
        "pandas": "version-of-pandas",
        "pyyaml": "version-of-PyYAML",
        "uproot": "version-of-uproot",
        "xgboost": "unavailable",
        "scikit-learn": "version-of-scikit-learn",
    }
    assert requested == [
        "numpy",
        "pandas",
        "PyYAML",
        "uproot",
        "xgboost",
        "scikit-learn",
    ]


@pytest.mark.parametrize(
    ("completed", "expected"),
    [
        (
            SimpleNamespace(
                returncode=0,
                stdout="0123456789abcdef0123456789abcdef01234567\n",
            ),
            "0123456789abcdef0123456789abcdef01234567",
        ),
        (SimpleNamespace(returncode=128, stdout=""), "unavailable"),
        (SimpleNamespace(returncode=0, stdout="not-a-sha\n"), "unavailable"),
    ],
)
def test_discover_git_commit_handles_success_and_unavailable(
    tmp_path, monkeypatch, completed, expected
):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return completed

    monkeypatch.setattr(provenance.subprocess, "run", fake_run)

    assert discover_git_commit(tmp_path) == expected
    assert calls[0][0] == ["git", "rev-parse", "HEAD"]
    assert calls[0][1]["cwd"] == tmp_path


def test_discover_git_commit_handles_missing_git(tmp_path, monkeypatch):
    def missing_git(*args, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(provenance.subprocess, "run", missing_git)

    assert discover_git_commit(tmp_path) == "unavailable"
