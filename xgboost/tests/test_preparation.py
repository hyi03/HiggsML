import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pandas as pd
import pytest

from src import preparation
from src.preparation import (
    OutputLayout,
    ReadPolicy,
    resolve_output_layout,
    resolve_read_policy,
    write_preparation_outputs,
)


def test_head_policy_uses_positive_configured_limit_and_default_chunk_size():
    policy = resolve_read_policy({"entry_stop": 5000}, full_override=False)

    assert policy == ReadPolicy("head", 5000, 50_000)
    assert policy.as_dict() == {
        "mode": "head",
        "entry_stop": 5000,
        "chunk_size_events": 50_000,
    }


def test_full_override_ignores_configured_entry_stop():
    policy = resolve_read_policy(
        {"entry_stop": 5000, "chunk_size_events": 17}, full_override=True
    )

    assert policy == ReadPolicy("full", None, 17)


def test_null_entry_stop_is_full_mode_without_override():
    assert resolve_read_policy(
        {"entry_stop": None, "chunk_size_events": 9}, full_override=False
    ) == ReadPolicy("full", None, 9)


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, "5000"])
def test_invalid_entry_stop_fails(value):
    with pytest.raises(ValueError, match="entry_stop must be null or a positive integer"):
        resolve_read_policy({"entry_stop": value}, full_override=False)


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, "50000", None])
def test_invalid_chunk_size_fails(value):
    with pytest.raises(ValueError, match="chunk_size_events must be a positive integer"):
        resolve_read_policy(
            {"entry_stop": 5000, "chunk_size_events": value},
            full_override=False,
        )


def test_full_mode_requires_run_directory(tmp_path):
    with pytest.raises(ValueError, match="full read mode requires --run-dir"):
        resolve_output_layout(
            project_root=tmp_path,
            working_directory=tmp_path,
            read_policy=ReadPolicy("full", None, 50_000),
            run_dir=None,
            output_dir=None,
        )


def test_fresh_run_directory_gets_isolated_paths(tmp_path):
    layout = resolve_output_layout(
        project_root=tmp_path,
        working_directory=tmp_path,
        read_policy=ReadPolicy("full", None, 50_000),
        run_dir=Path("runs/full-baseline-2026-08-10"),
        output_dir=None,
    )

    assert layout == OutputLayout(
        run_dir=Path("runs/full-baseline-2026-08-10"),
        processed_dir=Path("runs/full-baseline-2026-08-10/processed"),
        artifacts_dir=Path("runs/full-baseline-2026-08-10/artifacts"),
        config_snapshot=Path("runs/full-baseline-2026-08-10/config.yaml"),
    )
    assert not (tmp_path / "runs/full-baseline-2026-08-10").exists()


def test_run_directory_and_explicit_output_directory_are_mutually_exclusive(tmp_path):
    with pytest.raises(ValueError, match="cannot be used together"):
        resolve_output_layout(
            project_root=tmp_path,
            working_directory=tmp_path,
            read_policy=ReadPolicy("head", 5000, 50_000),
            run_dir="runs/smoke",
            output_dir="artifacts",
        )


def test_existing_run_directory_fails(tmp_path):
    (tmp_path / "runs/existing").mkdir(parents=True)

    with pytest.raises(FileExistsError, match="already exists"):
        resolve_output_layout(
            project_root=tmp_path,
            working_directory=tmp_path,
            read_policy=ReadPolicy("full", None, 50_000),
            run_dir="runs/existing",
            output_dir=None,
        )


def test_dangling_symlink_run_directory_fails(tmp_path):
    dangling = tmp_path / "runs/existing"
    dangling.parent.mkdir(parents=True)
    dangling.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    assert dangling.is_symlink()
    assert not dangling.exists()

    with pytest.raises(FileExistsError, match="run directory already exists"):
        resolve_output_layout(
            project_root=tmp_path,
            working_directory=tmp_path,
            read_policy=ReadPolicy("full", None, 50_000),
            run_dir="runs/existing",
            output_dir=None,
        )


@pytest.mark.parametrize(
    "protected",
    [
        ".",
        "data/raw/new-run",
        "data/processed/new-run",
        "outputs/new-run",
        "config/new-run",
        "docs/new-run",
        "src/new-run",
        "scripts/new-run",
        "tests/new-run",
        ".git/new-run",
        ".venv/new-run",
    ],
)
def test_run_directory_rejects_protected_project_paths(tmp_path, protected):
    with pytest.raises(ValueError, match="protected project path"):
        resolve_output_layout(
            project_root=tmp_path,
            working_directory=tmp_path,
            read_policy=ReadPolicy("full", None, 50_000),
            run_dir=protected,
            output_dir=None,
        )


def test_run_writer_copies_exact_config_and_writes_manifest_last(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = Path("config/demo.yaml")
    config_path.parent.mkdir()
    config_bytes = b"entry_stop: 5000\n# exact comment\n"
    config_path.write_bytes(config_bytes)
    layout = OutputLayout(
        run_dir=Path("runs/full"),
        processed_dir=Path("runs/full/processed"),
        artifacts_dir=Path("runs/full/artifacts"),
        config_snapshot=Path("runs/full/config.yaml"),
    )

    write_preparation_outputs(
        layout,
        config_source=config_path,
        config_bytes=config_bytes,
        mc_frame=pd.DataFrame({"eventNumber": [1]}),
        data_frame=pd.DataFrame({"eventNumber": [2]}),
        cutflow_payload={"schema_version": "1.0"},
        summary_payload={"schema_version": "1.0"},
        manifest_payload={"schema_version": "1.1"},
    )

    assert layout.config_snapshot.read_bytes() == config_bytes
    assert json.loads((layout.artifacts_dir / "run_manifest.json").read_text()) == {
        "schema_version": "1.1"
    }


def test_writer_rejects_changed_source_config_before_output_creation(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    config_path = Path("demo.yaml")
    config_path.write_bytes(b"first")
    layout = OutputLayout(
        run_dir=Path("runs/full"),
        processed_dir=Path("runs/full/processed"),
        artifacts_dir=Path("runs/full/artifacts"),
        config_snapshot=Path("runs/full/config.yaml"),
    )
    config_path.write_bytes(b"changed")

    with pytest.raises(RuntimeError, match="config changed during preparation"):
        write_preparation_outputs(
            layout,
            config_source=config_path,
            config_bytes=b"first",
            mc_frame=pd.DataFrame({"eventNumber": [1]}),
            data_frame=pd.DataFrame({"eventNumber": [2]}),
            cutflow_payload={"schema_version": "1.0"},
            summary_payload={"schema_version": "1.0"},
            manifest_payload={"schema_version": "1.1"},
        )

    assert not layout.run_dir.exists()


def test_writer_rejects_dangling_symlink_run_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = Path("demo.yaml")
    config_path.write_bytes(b"config")
    Path("runs").mkdir()
    Path("runs/full").symlink_to("missing-target", target_is_directory=True)
    layout = OutputLayout(
        run_dir=Path("runs/full"),
        processed_dir=Path("runs/full/processed"),
        artifacts_dir=Path("runs/full/artifacts"),
        config_snapshot=Path("runs/full/config.yaml"),
    )

    with pytest.raises(
        FileExistsError, match="run directory already exists: runs/full"
    ):
        write_preparation_outputs(
            layout,
            config_source=config_path,
            config_bytes=b"config",
            mc_frame=pd.DataFrame({"eventNumber": [1]}),
            data_frame=pd.DataFrame({"eventNumber": [2]}),
            cutflow_payload={"schema_version": "1.0"},
            summary_payload={"schema_version": "1.0"},
            manifest_payload={"schema_version": "1.1"},
        )


def test_two_same_target_run_writers_atomically_claim_directory(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    config_path = Path("demo.yaml")
    config_path.write_bytes(b"config")
    layout = OutputLayout(
        run_dir=Path("runs/full"),
        processed_dir=Path("runs/full/processed"),
        artifacts_dir=Path("runs/full/artifacts"),
        config_snapshot=Path("runs/full/config.yaml"),
    )
    original_path_entry_exists = preparation._path_entry_exists
    preflight_barrier = Barrier(2)

    def synchronize_same_target_preflight(path):
        exists = original_path_entry_exists(path)
        if path == layout.run_dir:
            preflight_barrier.wait(timeout=5)
        return exists

    monkeypatch.setattr(
        preparation, "_path_entry_exists", synchronize_same_target_preflight
    )

    def write_same_target():
        write_preparation_outputs(
            layout,
            config_source=config_path,
            config_bytes=b"config",
            mc_frame=pd.DataFrame({"eventNumber": [1]}),
            data_frame=pd.DataFrame({"eventNumber": [2]}),
            cutflow_payload={"schema_version": "1.0"},
            summary_payload={"schema_version": "1.0"},
            manifest_payload={"schema_version": "1.1"},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(write_same_target) for _ in range(2)]

    outcomes = []
    for future in futures:
        try:
            future.result()
        except Exception as exc:  # capture both writer outcomes for comparison
            outcomes.append(exc)
        else:
            outcomes.append(None)

    assert outcomes.count(None) == 1
    failures = [outcome for outcome in outcomes if outcome is not None]
    assert len(failures) == 1
    assert isinstance(failures[0], FileExistsError)
    assert "run directory already exists: runs/full" in str(failures[0])


def test_write_failure_leaves_incomplete_run_without_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = Path("demo.yaml")
    config_path.write_bytes(b"config")
    layout = OutputLayout(
        run_dir=Path("runs/full"),
        processed_dir=Path("runs/full/processed"),
        artifacts_dir=Path("runs/full/artifacts"),
        config_snapshot=Path("runs/full/config.yaml"),
    )

    def fail_to_csv(self, path, **kwargs):
        raise OSError("disk write failed")

    monkeypatch.setattr(pd.DataFrame, "to_csv", fail_to_csv)

    with pytest.raises(OSError, match="disk write failed"):
        write_preparation_outputs(
            layout,
            config_source=config_path,
            config_bytes=b"config",
            mc_frame=pd.DataFrame({"eventNumber": [1]}),
            data_frame=pd.DataFrame({"eventNumber": [2]}),
            cutflow_payload={"schema_version": "1.0"},
            summary_payload={"schema_version": "1.0"},
            manifest_payload={"schema_version": "1.1"},
        )

    assert layout.run_dir.exists()
    assert not (layout.artifacts_dir / "run_manifest.json").exists()


def test_earlier_artifact_failure_does_not_stage_or_publish_manifest(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    config_path = Path("demo.yaml")
    config_path.write_bytes(b"config")
    layout = OutputLayout(
        run_dir=Path("runs/full"),
        processed_dir=Path("runs/full/processed"),
        artifacts_dir=Path("runs/full/artifacts"),
        config_snapshot=Path("runs/full/config.yaml"),
    )
    original_write_text = Path.write_text

    def fail_summary_write(path, data, *args, **kwargs):
        if path.name == "data_summary.json":
            raise OSError("summary write failed")
        return original_write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_summary_write)

    with pytest.raises(OSError, match="summary write failed"):
        write_preparation_outputs(
            layout,
            config_source=config_path,
            config_bytes=b"config",
            mc_frame=pd.DataFrame({"eventNumber": [1]}),
            data_frame=pd.DataFrame({"eventNumber": [2]}),
            cutflow_payload={"schema_version": "1.0"},
            summary_payload={"schema_version": "1.0"},
            manifest_payload={"schema_version": "1.1"},
        )

    assert (layout.artifacts_dir / "cutflow.json").exists()
    assert not (layout.artifacts_dir / "run_manifest.json.tmp").exists()
    assert not (layout.artifacts_dir / "run_manifest.json").exists()


def test_manifest_temp_write_failure_never_publishes_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = Path("demo.yaml")
    config_path.write_bytes(b"config")
    layout = OutputLayout(
        run_dir=Path("runs/full"),
        processed_dir=Path("runs/full/processed"),
        artifacts_dir=Path("runs/full/artifacts"),
        config_snapshot=Path("runs/full/config.yaml"),
    )
    original_write_text = Path.write_text

    def interrupt_manifest_temp_write(path, data, *args, **kwargs):
        if path.name == "run_manifest.json.tmp":
            original_write_text(path, data[:8], *args, **kwargs)
            raise OSError("manifest temp write interrupted")
        return original_write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", interrupt_manifest_temp_write)

    with pytest.raises(OSError, match="manifest temp write interrupted"):
        write_preparation_outputs(
            layout,
            config_source=config_path,
            config_bytes=b"config",
            mc_frame=pd.DataFrame({"eventNumber": [1]}),
            data_frame=pd.DataFrame({"eventNumber": [2]}),
            cutflow_payload={"schema_version": "1.0"},
            summary_payload={"schema_version": "1.0"},
            manifest_payload={"schema_version": "1.1"},
        )

    assert (layout.artifacts_dir / "data_summary.json").exists()
    assert (layout.artifacts_dir / "run_manifest.json.tmp").exists()
    assert not (layout.artifacts_dir / "run_manifest.json").exists()


def test_manifest_publish_failure_leaves_final_path_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = Path("demo.yaml")
    config_path.write_bytes(b"config")
    layout = OutputLayout(
        run_dir=Path("runs/full"),
        processed_dir=Path("runs/full/processed"),
        artifacts_dir=Path("runs/full/artifacts"),
        config_snapshot=Path("runs/full/config.yaml"),
    )
    original_replace = Path.replace

    def interrupt_manifest_publish(path, target):
        if path.name == "run_manifest.json.tmp":
            raise OSError("manifest publish interrupted")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", interrupt_manifest_publish)

    with pytest.raises(OSError, match="manifest publish interrupted"):
        write_preparation_outputs(
            layout,
            config_source=config_path,
            config_bytes=b"config",
            mc_frame=pd.DataFrame({"eventNumber": [1]}),
            data_frame=pd.DataFrame({"eventNumber": [2]}),
            cutflow_payload={"schema_version": "1.0"},
            summary_payload={"schema_version": "1.0"},
            manifest_payload={"schema_version": "1.1"},
        )

    assert (layout.artifacts_dir / "run_manifest.json.tmp").exists()
    assert not (layout.artifacts_dir / "run_manifest.json").exists()
