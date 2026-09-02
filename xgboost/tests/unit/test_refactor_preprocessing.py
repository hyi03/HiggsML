from __future__ import annotations

import ast
import importlib.util
import math
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest
import yaml

from src.config import load_preprocessing_protocol
from src.domain.selection import SelectionConfig
from src.preprocessing import application, pipeline
from src.domain.weights import MCNormalization
from src.preprocessing.pipeline import (
    METADATA_COLUMNS,
    MODEL_FEATURES,
    OUTPUT_COLUMNS,
    PreparedMCSample,
    PreprocessedDataset,
    build_preprocessed_dataset,
    prepare_mc_sample,
)
from src.preprocessing.reader import InputReceipt, inspect_mc_input, verify_mc_input


PROJECT = Path(__file__).resolve().parents[2]


def _event(event_number: int = 60) -> dict[str, object]:
    return {
        "lep_n": 4,
        "lep_pt": [45.0, 45.0, 15.0, 15.0],
        "lep_eta": [0.0, 0.0, 0.0, 0.0],
        "lep_phi": [0.0, math.pi, math.pi / 2, -math.pi / 2],
        "lep_e": [45.0, 45.0, 15.0, 15.0],
        "lep_charge": [1, -1, 1, -1],
        "lep_type": [11, 11, 13, 13],
        "trigE": True,
        "trigM": False,
        "lep_isTrigMatched": [True] * 4,
        "lep_isTightID": [True] * 4,
        "lep_track_iso": [0.1] * 4,
        "lep_calo_iso": [0.1] * 4,
        "lep_d0sig": [0.1] * 4,
        "lep_z0": [0.1] * 4,
        "eventNumber": event_number,
        "runNumber": 1,
        "channelNumber": 345060,
        "mcWeight": 1.0,
        "xsec": 0.5,
        "kfac": 1.0,
        "filteff": 1.0,
        "sum_of_weights": 100.0,
    }


def test_prepare_mc_sample_publishes_exact_schema_and_angular19(monkeypatch) -> None:
    protocol = load_preprocessing_protocol(PROJECT / "config/preprocessing_protocol_v1.yaml")
    selection = SelectionConfig.from_mapping(protocol.raw["selection"])
    monkeypatch.setattr(pipeline, "iter_mc_events", lambda *args, **kwargs: iter([_event()]))

    prepared = prepare_mc_sample(
        "unused.root",
        name="higgs",
        sample=protocol.raw["samples"]["higgs"],
        selection=selection,
        chunk_size_events=7,
    )

    assert tuple(prepared.frame.columns) == OUTPUT_COLUMNS
    assert tuple(prepared.frame.columns[:19]) == MODEL_FEATURES
    assert prepared.frame.loc[0, "split"] == "test"
    assert prepared.frame.loc[0, "label"] == 1
    assert prepared.frame.loc[0, "physical_weight"] == pytest.approx(50.0)
    assert prepared.frame.loc[0, "train_weight"] == pytest.approx(1.0)
    assert np.isfinite(prepared.frame[list(MODEL_FEATURES)].to_numpy()).all()


def test_output_schema_is_unique_and_separates_model_metadata() -> None:
    protocol = load_preprocessing_protocol(PROJECT / "config/preprocessing_protocol_v1.yaml")

    assert len(MODEL_FEATURES) == 19
    assert len(METADATA_COLUMNS) == 13
    assert len(OUTPUT_COLUMNS) == 32
    assert len(set(OUTPUT_COLUMNS)) == 32
    assert set(MODEL_FEATURES).isdisjoint(METADATA_COLUMNS)
    assert set(MODEL_FEATURES).isdisjoint(protocol.raw["forbidden_features"])


def test_selected_event_angular5_failure_aborts_sample(monkeypatch) -> None:
    protocol = load_preprocessing_protocol(PROJECT / "config/preprocessing_protocol_v1.yaml")
    selection = SelectionConfig.from_mapping(protocol.raw["selection"])
    monkeypatch.setattr(pipeline, "iter_mc_events", lambda *args, **kwargs: iter([_event()]))

    def fail_angular5(candidate):
        raise ValueError("degenerate Angular5 geometry")

    monkeypatch.setattr(pipeline, "build_angular5", fail_angular5)

    with pytest.raises(ValueError, match="degenerate Angular5 geometry"):
        prepare_mc_sample(
            "unused.root",
            name="higgs",
            sample=protocol.raw["samples"]["higgs"],
            selection=selection,
            chunk_size_events=7,
        )


def test_input_receipt_detects_replacement(tmp_path: Path) -> None:
    source = tmp_path / "events.root"
    source.write_bytes(b"first")
    receipt = inspect_mc_input(source)
    verify_mc_input(receipt)
    source.write_bytes(b"second")
    with pytest.raises(RuntimeError, match="changed while being read"):
        verify_mc_input(receipt)


def test_input_receipt_rejects_suffix_and_non_regular_path(tmp_path: Path) -> None:
    wrong = tmp_path / "events.csv"
    wrong.write_bytes(b"not root")
    with pytest.raises(ValueError, match=".root suffix"):
        inspect_mc_input(wrong)
    directory = tmp_path / "directory.root"
    directory.mkdir()
    with pytest.raises(ValueError, match="regular file"):
        inspect_mc_input(directory)


def test_input_receipt_rejects_symlink_when_platform_allows_it(tmp_path: Path) -> None:
    target = tmp_path / "target.root"
    target.write_bytes(b"root")
    link = tmp_path / "link.root"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("platform does not permit creating symlinks")
    with pytest.raises(ValueError, match="symlink"):
        inspect_mc_input(link)


def test_protocol_and_run_config_inputs_must_be_regular_non_symlinks(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "directory.yaml"
    directory.mkdir()
    with pytest.raises(ValueError, match="regular file"):
        application._read_regular_input(directory, "preprocessing protocol")

    target = tmp_path / "target.yaml"
    target.write_text("schema_version: '1.0'\n", encoding="utf-8")
    link = tmp_path / "link.yaml"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("platform does not permit creating symlinks")
    with pytest.raises(ValueError, match="symlink"):
        application._read_regular_input(link, "preprocessing run config")


def test_code_hash_includes_package_initializers(tmp_path: Path) -> None:
    required = (
        "src/__init__.py",
        "src/config.py",
        "src/artifacts/__init__.py",
        "src/artifacts/manifest.py",
        "src/artifacts/transaction.py",
        "src/cli/__init__.py",
        "src/cli/preprocess.py",
        "src/domain/__init__.py",
        "src/preprocessing/__init__.py",
    )
    for relative in required:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(f"# {relative}\n", encoding="utf-8")

    before = application._code_sha256(tmp_path)
    (tmp_path / "src/__init__.py").write_text("# changed initializer\n", encoding="utf-8")

    assert application._code_sha256(tmp_path) != before


def test_git_identity_marks_untracked_files_dirty(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=HiggsML Test",
            "-c",
            "user.email=higgsml-test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "baseline",
        ],
        cwd=repository,
        check=True,
    )
    (repository / "untracked.py").write_text("# untracked\n", encoding="utf-8")

    identity = application._git_identity(repository)

    assert identity["worktree_dirty"] is True


def test_prepare_mc_sample_rejects_wrong_dsid_and_invalid_unit(monkeypatch) -> None:
    protocol = load_preprocessing_protocol(PROJECT / "config/preprocessing_protocol_v1.yaml")
    selection = SelectionConfig.from_mapping(protocol.raw["selection"])
    wrong_channel = _event()
    wrong_channel["channelNumber"] = 363490
    monkeypatch.setattr(
        pipeline, "iter_mc_events", lambda *args, **kwargs: iter([wrong_channel])
    )
    with pytest.raises(ValueError, match="unconfigured channelNumber"):
        prepare_mc_sample(
            "unused.root",
            name="higgs",
            sample=protocol.raw["samples"]["higgs"],
            selection=selection,
            chunk_size_events=7,
        )

    invalid = dict(protocol.raw["samples"]["higgs"])
    invalid["momentum_unit"] = "TeV"
    monkeypatch.setattr(
        pipeline, "iter_mc_events", lambda *args, **kwargs: iter([_event()])
    )
    with pytest.raises(ValueError, match="momentum unit"):
        prepare_mc_sample(
            "unused.root",
            name="higgs",
            sample=invalid,
            selection=selection,
            chunk_size_events=7,
        )


def test_dataset_rejects_duplicate_canonical_identity(monkeypatch) -> None:
    protocol = load_preprocessing_protocol(PROJECT / "config/preprocessing_protocol_v1.yaml")
    row = {name: 0.0 for name in OUTPUT_COLUMNS}
    row.update(
        label=1,
        split="train",
        channelNumber=345060,
        eventNumber=1,
        runNumber=1,
    )
    frame = pipeline.pd.DataFrame([row, row], columns=OUTPUT_COLUMNS)
    normalization = MCNormalization(1.0, 1.0, 1.0, 1.0)
    outcomes = iter(
        [
            PreparedMCSample("higgs", frame, {}, normalization),
            PreparedMCSample("zz", frame.iloc[0:0].copy(), {}, normalization),
        ]
    )
    monkeypatch.setattr(pipeline, "prepare_mc_sample", lambda *args, **kwargs: next(outcomes))
    with pytest.raises(ValueError, match="duplicate canonical event identity"):
        build_preprocessed_dataset(
            protocol=protocol.raw,
            higgs_root="higgs.root",
            zz_root="zz.root",
            chunk_size_events=1,
        )


def test_mid_run_input_change_writes_failure_without_success_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    run_config = tmp_path / "run.yaml"
    run_config.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "higgs_root": "higgs.root",
                "zz_root": "zz.root",
                "chunk_size_events": 5,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    receipt = InputReceipt("fake.root", 1, 2, 3, 4, "0" * 64)
    monkeypatch.setattr(application, "inspect_mc_input", lambda path: receipt)
    empty = pipeline.pd.DataFrame(columns=OUTPUT_COLUMNS)
    monkeypatch.setattr(
        application,
        "build_preprocessed_dataset",
        lambda **kwargs: PreprocessedDataset(empty, empty, {}, {}),
    )
    monkeypatch.setattr(
        application,
        "verify_mc_input",
        lambda value: (_ for _ in ()).throw(RuntimeError("changed while being read")),
    )
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    run_dir = runs_dir / "failed"
    with pytest.raises(RuntimeError, match="changed while being read"):
        application.run_preprocessing(
            protocol_path=PROJECT / "config/preprocessing_protocol_v1.yaml",
            run_config_path=run_config,
            run_dir=run_dir,
        )
    assert (run_dir / "failure.json").is_file()
    assert not (run_dir / "artifacts/manifest.json").exists()


def test_new_preprocess_imports_do_not_reach_legacy_execution_modules() -> None:
    source_root = PROJECT / "src"
    targets = [
        source_root / "config.py",
        source_root / "cli/preprocess.py",
        *(source_root / "preprocessing").glob("*.py"),
        *(source_root / "artifacts").glob("*.py"),
    ]
    forbidden_prefixes = (
        "src.pipeline",
        "src.preparation",
        "src.provenance",
        "src.io",
        "src.plots",
        "src.angular5_enrichment",
        "src.angular5_identity",
        "src.decorrelation_training",
        "src.experiment_config",
        "src.experiment_runner",
        "src.external_zz",
        "src.full_training",
        "src.mass_bin_reweighting",
        "src.mass_sculpting_ablation",
        "src.progress",
        "src.train",
        "src.validation",
        "matplotlib",
        "mplhep",
        "xgboost",
    )

    def module_name(path: Path) -> str:
        return ".".join(path.relative_to(PROJECT).with_suffix("").parts)

    imported: set[str] = set()
    for path in targets:
        module = module_name(path)
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    relative = "." * node.level + (node.module or "")
                    base = importlib.util.resolve_name(relative, package)
                else:
                    base = node.module or ""
                if base:
                    imported.add(base)
                imported.update(
                    f"{base}.{alias.name}" if base else alias.name
                    for alias in node.names
                    if alias.name != "*"
                )

    violations = sorted(
        target
        for target in imported
        if any(
            target == prefix or target.startswith(f"{prefix}.")
            for prefix in forbidden_prefixes
        )
    )
    assert violations == []


def test_occupied_run_fails_before_root_inspection(tmp_path: Path, monkeypatch) -> None:
    run_config = tmp_path / "run.yaml"
    run_config.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "higgs_root": str(tmp_path / "missing-higgs.root"),
                "zz_root": str(tmp_path / "missing-zz.root"),
                "chunk_size_events": 5,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    occupied = runs_dir / "occupied"
    occupied.mkdir()
    monkeypatch.setattr(
        application,
        "inspect_mc_input",
        lambda path: pytest.fail("occupied run inspected a ROOT input"),
    )
    with pytest.raises(FileExistsError):
        application.run_preprocessing(
            protocol_path=PROJECT / "config/preprocessing_protocol_v1.yaml",
            run_config_path=run_config,
            run_dir=occupied,
        )


def test_run_directory_must_be_directly_below_named_runs_root(
    tmp_path: Path, monkeypatch
) -> None:
    run_config = tmp_path / "run.yaml"
    run_config.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "higgs_root": "higgs.root",
                "zz_root": "zz.root",
                "chunk_size_events": 5,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        application,
        "inspect_mc_input",
        lambda path: pytest.fail("invalid run directory inspected a ROOT input"),
    )

    with pytest.raises(ValueError, match="named runs root"):
        application.run_preprocessing(
            protocol_path=PROJECT / "config/preprocessing_protocol_v1.yaml",
            run_config_path=run_config,
            run_dir=tmp_path / "not-runs" / "rejected",
        )
