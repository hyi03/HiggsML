from __future__ import annotations

from collections.abc import Callable
import errno
import gzip
import hashlib
import io
import json
import os
import secrets
import stat
import time
from dataclasses import dataclass, replace
from numbers import Integral
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .provenance import sha256_file


@dataclass(frozen=True)
class TrainingInput:
    input_run: Path
    config_path: Path
    mc_path: Path
    summary_path: Path
    manifest_path: Path
    hashes: Mapping[str, str]
    expected_rows: int


@dataclass(frozen=True)
class TrainingOutputLayout:
    run_dir: Path
    config_snapshot: Path
    model_dir: Path
    artifacts_dir: Path
    predictions_dir: Path
    plots_dir: Path
    directory_identities: Mapping[str, tuple[int, int]] | None = None


_RECEIPT_TOKEN = object()


@dataclass(frozen=True, init=False)
class TrainingArtifactReceipt:
    _run_identity: tuple[int, int]

    def __new__(cls, token: object = None, run_identity: tuple[int, int] | None = None):
        if token is not _RECEIPT_TOKEN or run_identity is None:
            raise TypeError("TrainingArtifactReceipt is returned by write_training_artifacts")
        return super().__new__(cls)

    def __init__(self, token: object, run_identity: tuple[int, int]) -> None:
        object.__setattr__(self, "_run_identity", run_identity)


MODEL_NAME = "xgboost_model.json"
JSON_ARTIFACT_NAMES = (
    "weight_summary.json",
    "metrics.json",
    "working_points.json",
)
ARTIFACT_TABLE_NAMES = ("cv_results.csv",)
PREDICTION_NAMES = (
    "oof_scores.csv.gz",
    "test_scores.csv.gz",
)
PLOT_NAMES = (
    "roc_curve.png",
    "score_distributions.png",
    "cv_stability.png",
    "feature_importance.png",
    "mc_mass_sculpting.png",
    "mc_mass_signal_background.png",
    "mc_mass_working_points.png",
)


def _path_entry_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _has_dangling_symlink_component(path: Path) -> bool:
    absolute = path if path.is_absolute() else Path.cwd() / path
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink() and not current.exists():
            return True
    return False


def _require_file(path: Path) -> Path:
    try:
        path.resolve(strict=True)
    except (FileNotFoundError, RuntimeError) as error:
        if _has_dangling_symlink_component(path):
            raise FileNotFoundError(f"Task 4A input has a dangling symlink: {path}") from error
        raise FileNotFoundError(f"Task 4A input is missing: {path}") from error
    if not path.is_file():
        raise ValueError(f"Task 4A input is not a file: {path}")
    return path


def _read_json_object(path: Path, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Task 4A {name} is not valid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Task 4A {name} must contain a JSON object")
    return payload


def _parse_json_object(payload_bytes: bytes, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Task 4A {name} is not valid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Task 4A {name} must contain a JSON object")
    return payload


def _summary_label_counts(summary: Mapping[str, Any]) -> dict[int, int]:
    if summary.get("schema_version") != "1.0":
        raise ValueError("Task 4A summary schema_version must be 1.0")
    mc = summary.get("mc")
    if not isinstance(mc, Mapping) or not mc:
        raise ValueError("Task 4A summary must contain MC sample entries")
    counts = {0: 0, 1: 0}
    observed_labels: set[int] = set()
    for sample_name, raw_entry in mc.items():
        if not isinstance(raw_entry, Mapping):
            raise ValueError(f"Task 4A summary MC entry {sample_name!r} must be an object")
        label = raw_entry.get("label")
        selected = raw_entry.get("selected_events")
        if isinstance(label, bool) or not isinstance(label, Integral) or int(label) not in counts:
            raise ValueError("Task 4A summary MC label must be 0 or 1")
        if isinstance(selected, bool) or not isinstance(selected, Integral) or selected < 0:
            raise ValueError("Task 4A summary selected event count must be non-negative")
        normalized_label = int(label)
        observed_labels.add(normalized_label)
        counts[normalized_label] += int(selected)
    if observed_labels != {0, 1}:
        raise ValueError("Task 4A summary label count must contain labels 0 and 1")
    return counts


def _validate_manifest(manifest: Mapping[str, Any], config_hash: str) -> None:
    if manifest.get("schema_version") != "1.1":
        raise ValueError("Task 4A manifest schema_version must be 1.1")
    if "status" in manifest and manifest["status"] != "complete":
        raise ValueError("Task 4A manifest status must be the string complete when present")
    processing = manifest.get("processing")
    policy = processing.get("read_policy") if isinstance(processing, Mapping) else None
    if not isinstance(policy, Mapping) or policy.get("mode") != "full" or policy.get("entry_stop") is not None:
        raise ValueError("Task 4A read policy must be full with entry_stop null")
    config = manifest.get("config")
    if not isinstance(config, Mapping) or config.get("sha256") != config_hash:
        raise ValueError("Task 4A manifest config hash does not match config snapshot")


def _validate_mc_table(payload: bytes, expected_by_label: Mapping[int, int]) -> int:
    try:
        frame = pd.read_csv(io.BytesIO(payload), compression="gzip")
    except Exception as error:
        raise ValueError("Task 4A MC CSV could not be read") from error
    expected_rows = int(sum(expected_by_label.values()))
    if len(frame) != expected_rows:
        raise ValueError("Task 4A summary selected event count does not match MC rows")
    if "label" not in frame:
        raise ValueError("Task 4A MC CSV is missing label")
    try:
        labels = frame["label"].to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("Task 4A MC labels must be finite integers") from error
    if not np.isfinite(labels).all() or not np.equal(labels, np.floor(labels)).all():
        raise ValueError("Task 4A MC labels must be finite integers")
    actual_by_label = {
        label: int(np.count_nonzero(labels == label)) for label in expected_by_label
    }
    if set(labels.astype(int)) != {0, 1} or actual_by_label != dict(expected_by_label):
        raise ValueError("Task 4A summary label count does not match MC rows")
    numeric = frame.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("Task 4A MC data must be finite")
    return expected_rows


def _after_input_validation() -> None:
    """Test seam immediately after parsing and semantic validation."""


def _hash_input_paths(paths: Mapping[str, Path]) -> Mapping[str, str]:
    return MappingProxyType({name: sha256_file(path) for name, path in paths.items()})


def _snapshot_input_bytes(
    paths: Mapping[str, Path],
) -> tuple[Mapping[str, bytes], Mapping[str, str]]:
    snapshots = {name: _require_file(path).read_bytes() for name, path in paths.items()}
    hashes = {
        name: hashlib.sha256(payload).hexdigest()
        for name, payload in snapshots.items()
    }
    return MappingProxyType(snapshots), MappingProxyType(hashes)


def resolve_training_input(input_run: str | Path) -> TrainingInput:
    run = Path(input_run)
    try:
        run.resolve(strict=True)
    except (FileNotFoundError, RuntimeError) as error:
        if _has_dangling_symlink_component(run):
            raise FileNotFoundError(f"Task 4A input has a dangling symlink: {run}") from error
        raise FileNotFoundError(f"Task 4A input run is missing: {run}") from error
    if not run.is_dir():
        raise ValueError(f"Task 4A input run is not a directory: {run}")

    config_path = _require_file(run / "config.yaml")
    mc_path = _require_file(run / "processed/mc_events.csv.gz")
    summary_path = _require_file(run / "artifacts/data_summary.json")
    manifest_path = _require_file(run / "artifacts/run_manifest.json")
    paths = {
        "config": config_path,
        "mc": mc_path,
        "summary": summary_path,
        "manifest": manifest_path,
    }
    snapshots, hashes = _snapshot_input_bytes(paths)
    summary = _parse_json_object(snapshots["summary"], "summary")
    manifest = _parse_json_object(snapshots["manifest"], "manifest")
    _validate_manifest(manifest, hashes["config"])
    expected_rows = _validate_mc_table(
        snapshots["mc"], _summary_label_counts(summary)
    )
    _after_input_validation()
    if dict(_hash_input_paths(paths)) != dict(hashes):
        raise RuntimeError("Task 4A input changed during training")
    return TrainingInput(
        input_run=run,
        config_path=config_path,
        mc_path=mc_path,
        summary_path=summary_path,
        manifest_path=manifest_path,
        hashes=hashes,
        expected_rows=expected_rows,
    )


def load_training_mc_frame(training_input: TrainingInput) -> pd.DataFrame:
    """Load the exact hashed Task 4A MC bytes once, then parse the snapshot."""
    if not isinstance(training_input, TrainingInput):
        raise TypeError("training_input must be a TrainingInput")
    try:
        payload = training_input.mc_path.read_bytes()
    except (OSError, RuntimeError) as error:
        raise RuntimeError("Task 4A input changed during training") from error
    expected_hash = training_input.hashes.get("mc")
    if hashlib.sha256(payload).hexdigest() != expected_hash:
        raise RuntimeError("Task 4A input changed during training")
    try:
        return pd.read_csv(io.BytesIO(payload), compression="gzip")
    except Exception as error:
        raise ValueError("Task 4A MC CSV could not be read") from error


def snapshot_input_hashes(training_input: TrainingInput) -> Mapping[str, str]:
    paths = {
        "config": training_input.config_path,
        "mc": training_input.mc_path,
        "summary": training_input.summary_path,
        "manifest": training_input.manifest_path,
    }
    try:
        hashes = {name: sha256_file(_require_file(path)) for name, path in paths.items()}
    except (FileNotFoundError, ValueError, OSError) as error:
        raise RuntimeError("Task 4A input changed during training") from error
    return MappingProxyType(hashes)


def assert_input_hashes_unchanged(training_input: TrainingInput) -> None:
    if dict(snapshot_input_hashes(training_input)) != dict(training_input.hashes):
        raise RuntimeError("Task 4A input changed during training")


def _is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _absolute_without_symlinks(path: Path, *, allow_final_symlink: bool = False) -> Path:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    components = absolute.parts[1:]
    for index, part in enumerate(components):
        current /= part
        try:
            if current.is_symlink():
                if allow_final_symlink and index == len(components) - 1:
                    continue
                raise ValueError(f"training path contains a symlink component: {current}")
        except OSError as error:
            raise ValueError(f"training path cannot be inspected safely: {current}") from error
    return absolute


def resolve_training_output(
    *,
    project_root: Path,
    working_directory: Path,
    input_run: str | Path,
    run_dir: str | Path,
) -> TrainingOutputLayout:
    logical_run_dir = Path(run_dir)
    unresolved_run = (
        logical_run_dir
        if logical_run_dir.is_absolute()
        else working_directory.resolve() / logical_run_dir
    )
    resolved_run = _absolute_without_symlinks(
        unresolved_run, allow_final_symlink=True
    )
    resolved_project = project_root.resolve()
    resolved_input = Path(input_run).resolve()
    protected_project_paths = [
        resolved_project / "data",
        resolved_project / "outputs",
        resolved_project / "config",
        resolved_project / "docs",
        resolved_project / "src",
        resolved_project / "scripts",
        resolved_project / "tests",
        resolved_project / ".git",
        resolved_project / ".venv",
    ]
    if resolved_run == resolved_project or any(
        _is_within(resolved_run, protected.resolve())
        for protected in protected_project_paths
    ):
        raise ValueError("training --run-dir resolves inside a protected project path")
    if _is_within(resolved_run, resolved_input):
        raise ValueError("training --run-dir resolves inside the Task 4A input run")
    if _path_entry_exists(unresolved_run):
        raise FileExistsError(
            f"training run directory already exists: {logical_run_dir}"
        )
    return TrainingOutputLayout(
        run_dir=resolved_run,
        config_snapshot=resolved_run / "config.yaml",
        model_dir=resolved_run / "model",
        artifacts_dir=resolved_run / "artifacts",
        predictions_dir=resolved_run / "predictions",
        plots_dir=resolved_run / "plots",
    )


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)


def _open_claim_parent(run_dir: Path) -> int:
    descriptor = os.open(run_dir.anchor, _directory_flags())
    try:
        for part in run_dir.parent.parts[1:]:
            try:
                child = os.open(part, _directory_flags(), dir_fd=descriptor)
            except FileNotFoundError:
                os.mkdir(part, dir_fd=descriptor)
                child = os.open(part, _directory_flags(), dir_fd=descriptor)
            except OSError as error:
                if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise ValueError(
                        f"training path contains a symlink component: {part}"
                    ) from error
                raise
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _identity(descriptor: int) -> tuple[int, int]:
    stat = os.fstat(descriptor)
    return (stat.st_dev, stat.st_ino)


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        view = view[written:]


def _mark_claim_failure(root_descriptor: int, error: BaseException) -> None:
    try:
        os.mkdir(".terminal.failed", dir_fd=root_descriptor)
    except FileExistsError:
        pass
    try:
        descriptor = os.open(
            "failure.json",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=root_descriptor,
        )
    except OSError:
        return
    try:
        _write_all(
            descriptor,
            _json_bytes(
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "message": str(error),
                }
            ),
        )
    finally:
        os.close(descriptor)


def claim_training_output(layout: TrainingOutputLayout) -> TrainingOutputLayout:
    if layout.directory_identities is not None:
        raise RuntimeError("training output is already claimed")
    parent_descriptor = _open_claim_parent(layout.run_dir)
    root_descriptor: int | None = None
    try:
        try:
            os.mkdir(layout.run_dir.name, dir_fd=parent_descriptor)
        except FileExistsError as error:
            raise FileExistsError(
                f"training run directory already exists: {layout.run_dir}"
            ) from error
        root_descriptor = os.open(
            layout.run_dir.name, _directory_flags(), dir_fd=parent_descriptor
        )
        identities: dict[str, tuple[int, int]] = {".": _identity(root_descriptor)}
        try:
            for name in ("model", "artifacts", "predictions", "plots"):
                os.mkdir(name, dir_fd=root_descriptor)
                child = os.open(name, _directory_flags(), dir_fd=root_descriptor)
                try:
                    identities[name] = _identity(child)
                finally:
                    os.close(child)
        except Exception as error:
            _mark_claim_failure(root_descriptor, error)
            raise
        return replace(
            layout, directory_identities=MappingProxyType(dict(identities))
        )
    finally:
        if root_descriptor is not None:
            os.close(root_descriptor)
        os.close(parent_descriptor)


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _before_no_clobber_promote(destination: Path) -> None:
    """Test seam immediately before an atomic no-clobber promotion."""


def _before_final_input_recheck() -> None:
    """Test seam after manifest staging and before the final input recheck."""


def _entry_exists(descriptor: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _stage_bytes(descriptor: int, final_name: str, payload: bytes) -> str:
    for _ in range(128):
        temporary_name = f".{final_name}.{secrets.token_hex(16)}.tmp"
        try:
            temporary = os.open(
                temporary_name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=descriptor,
            )
        except FileExistsError:
            continue
        try:
            _write_all(temporary, payload)
        except Exception:
            os.close(temporary)
            _cleanup_staged(descriptor, temporary_name)
            raise
        else:
            os.close(temporary)
            return temporary_name
    raise FileExistsError(f"could not create a unique temporary for {final_name}")


def _cleanup_staged(descriptor: int, temporary_name: str | None) -> None:
    if temporary_name is None:
        return
    try:
        os.unlink(temporary_name, dir_fd=descriptor)
    except FileNotFoundError:
        pass


def _promote_staged_no_clobber(
    descriptor: int,
    parent: Path,
    temporary_name: str,
    final_name: str,
    *,
    immediate_check: Callable[[], None] | None = None,
) -> None:
    destination = parent / final_name
    _before_no_clobber_promote(destination)
    if immediate_check is not None:
        immediate_check()
    try:
        os.link(
            temporary_name,
            final_name,
            src_dir_fd=descriptor,
            dst_dir_fd=descriptor,
            follow_symlinks=False,
        )
    except FileExistsError as error:
        raise FileExistsError(f"output entry already exists: {destination}") from error
    finally:
        _cleanup_staged(descriptor, temporary_name)


def _atomic_publish_bytes(
    descriptor: int, parent: Path, final_name: str, payload: bytes
) -> None:
    temporary_name = _stage_bytes(descriptor, final_name, payload)
    _promote_staged_no_clobber(descriptor, parent, temporary_name, final_name)


def _open_absolute_directory_no_follow(path: Path) -> int:
    if not path.is_absolute():
        raise ValueError("directory path must be absolute")
    descriptor = os.open(path.anchor, _directory_flags())
    try:
        for part in path.parts[1:]:
            try:
                child = os.open(part, _directory_flags(), dir_fd=descriptor)
            except OSError as error:
                raise ValueError(
                    f"absolute path component is not a safe directory: {part}"
                ) from error
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _open_claimed_directories(layout: TrainingOutputLayout) -> dict[str, int]:
    expected = layout.directory_identities
    if expected is None:
        raise RuntimeError("training output directory has not been claimed")
    descriptors: dict[str, int] = {}
    try:
        try:
            root = _open_absolute_directory_no_follow(layout.run_dir)
        except OSError as error:
            raise ValueError("training run ownership or symlink safety check failed") from error
        descriptors["."] = root
        if _identity(root) != expected.get("."):
            raise ValueError("training run ownership changed")
        for name in ("model", "artifacts", "predictions", "plots"):
            try:
                child = os.open(name, _directory_flags(), dir_fd=root)
            except OSError as error:
                raise ValueError(
                    f"training child ownership or symlink safety check failed: {name}"
                ) from error
            descriptors[name] = child
            if _identity(child) != expected.get(name):
                raise ValueError(f"training child ownership changed: {name}")
        return descriptors
    except Exception:
        for descriptor in descriptors.values():
            os.close(descriptor)
        raise


def _close_descriptors(descriptors: Mapping[str, int] | None) -> None:
    if descriptors is None:
        return
    for descriptor in reversed(tuple(descriptors.values())):
        os.close(descriptor)


def _open_verified_root(layout: TrainingOutputLayout) -> int:
    if layout.directory_identities is None:
        raise RuntimeError("training output directory has not been claimed")
    try:
        descriptor = _open_absolute_directory_no_follow(layout.run_dir)
    except (OSError, ValueError) as error:
        raise ValueError("training run ownership or symlink safety check failed") from error
    if _identity(descriptor) != layout.directory_identities.get("."):
        os.close(descriptor)
        raise ValueError("training run ownership changed")
    return descriptor


def _entries(descriptor: int) -> set[str]:
    return set(os.listdir(descriptor))


def _assert_empty_claimed_layout(descriptors: Mapping[str, int]) -> None:
    root_entries = _entries(descriptors["."])
    expected_root = {"model", "artifacts", "predictions", "plots"}
    if root_entries != expected_root:
        extras = sorted(root_entries - expected_root)
        raise FileExistsError(f"output entry already exists: {extras}")
    for name in ("model", "artifacts", "predictions", "plots"):
        entries = _entries(descriptors[name])
        if entries:
            raise FileExistsError(f"output entry already exists: {sorted(entries)}")


def _assert_approved_contract(
    descriptors: Mapping[str, int],
    *,
    manifest_present: bool,
    terminal_lock_present: bool,
) -> None:
    root_expected = {
        "config.yaml",
        "model",
        "artifacts",
        "predictions",
        "plots",
    }
    if terminal_lock_present:
        root_expected.add(".terminal.lock")
    root_actual = _entries(descriptors["."])
    if root_actual != root_expected:
        if root_expected - root_actual:
            raise FileNotFoundError("required training output is missing in run root")
        raise ValueError("unexpected training output entry in run root")
    expected_by_directory = {
        "model": {MODEL_NAME},
        "artifacts": set(JSON_ARTIFACT_NAMES)
        | set(ARTIFACT_TABLE_NAMES)
        | ({"training_manifest.json"} if manifest_present else set()),
        "predictions": set(PREDICTION_NAMES),
        "plots": set(PLOT_NAMES),
    }
    for name, expected in expected_by_directory.items():
        actual = _entries(descriptors[name])
        if actual != expected:
            if expected - actual:
                raise FileNotFoundError(
                    f"required training output is missing in {name}"
                )
            raise ValueError(f"unexpected training output entry in {name}")


def _validate_artifact_contract(
    json_artifacts: Mapping[str, Mapping[str, Any]],
    artifact_tables: Mapping[str, pd.DataFrame],
    prediction_frames: Mapping[str, pd.DataFrame],
    plot_artifacts: Mapping[str, bytes],
) -> None:
    if set(json_artifacts) != set(JSON_ARTIFACT_NAMES):
        raise ValueError("JSON outputs do not match the approved artifact contract")
    if set(artifact_tables) != set(ARTIFACT_TABLE_NAMES):
        raise ValueError("artifact tables do not match the approved artifact contract")
    if set(prediction_frames) != set(PREDICTION_NAMES):
        raise ValueError("prediction outputs do not match the approved artifact contract")
    if set(plot_artifacts) != set(PLOT_NAMES):
        raise ValueError("plot outputs do not match the approved artifact contract")


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return gzip.compress(frame.to_csv(index=False).encode("utf-8"), mtime=0)


def _model_bytes(model: Any) -> bytes:
    payload = model.save_raw(raw_format="json")
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("model save_raw must return bytes")
    return bytes(payload)


def _terminal_lock_acquire(root: int, *, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            os.mkdir(".terminal.lock", dir_fd=root)
            return
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError("training terminal transition is locked")
            time.sleep(0.001)


def _terminal_lock_release(root: int) -> None:
    try:
        os.rmdir(".terminal.lock", dir_fd=root)
    except FileNotFoundError:
        pass


def _manifest_exists_from_root(root: int) -> bool:
    try:
        artifacts = os.open("artifacts", _directory_flags(), dir_fd=root)
    except OSError:
        return False
    try:
        return _entry_exists(artifacts, "training_manifest.json")
    finally:
        os.close(artifacts)


def _install_failure_locked(
    root: int, run_dir: Path, error: BaseException
) -> None:
    if _manifest_exists_from_root(root):
        return
    try:
        os.mkdir(".terminal.failed", dir_fd=root)
    except FileExistsError:
        pass
    if _entry_exists(root, "failure.json"):
        return
    try:
        _atomic_publish_bytes(
            root,
            run_dir,
            "failure.json",
            _json_bytes(
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "message": str(error),
                }
            ),
        )
    except Exception:
        # The root-owned failed sentinel is the authoritative fail-closed state.
        pass


def _best_effort_failure(layout: TrainingOutputLayout, error: BaseException) -> None:
    try:
        root = _open_verified_root(layout)
    except Exception:
        return
    locked = False
    try:
        _terminal_lock_acquire(root)
        locked = True
        _install_failure_locked(root, layout.run_dir, error)
    except Exception:
        pass
    finally:
        if locked:
            _terminal_lock_release(root)
        os.close(root)


def record_training_failure(
    layout: TrainingOutputLayout, error: BaseException
) -> None:
    """Best-effort public transition of a claimed run to terminal failure."""
    _best_effort_failure(layout, error)


def write_training_artifacts(
    layout: TrainingOutputLayout,
    *,
    config_source: Path,
    config_bytes: bytes,
    model: Any,
    json_artifacts: Mapping[str, Mapping[str, Any]],
    artifact_tables: Mapping[str, pd.DataFrame],
    prediction_frames: Mapping[str, pd.DataFrame],
    plot_artifacts: Mapping[str, bytes],
) -> TrainingArtifactReceipt:
    """Write the exact approved non-manifest contract with no-clobber promotion."""
    descriptors: dict[str, int] | None = None
    try:
        descriptors = _open_claimed_directories(layout)
        root = descriptors["."]
        if _entry_exists(root, ".terminal.failed") or _entry_exists(root, "failure.json"):
            raise RuntimeError("cannot write a failed training run")
        _validate_artifact_contract(
            json_artifacts, artifact_tables, prediction_frames, plot_artifacts
        )
        _assert_empty_claimed_layout(descriptors)

        serialized_json = {
            name: _json_bytes(json_artifacts[name]) for name in JSON_ARTIFACT_NAMES
        }
        serialized_tables: dict[str, bytes] = {}
        for name in ARTIFACT_TABLE_NAMES:
            frame = artifact_tables[name]
            if not isinstance(frame, pd.DataFrame):
                raise TypeError(f"artifact table {name!r} must be a DataFrame")
            serialized_tables[name] = frame.to_csv(index=False).encode("utf-8")
        serialized_predictions: dict[str, bytes] = {}
        for name in PREDICTION_NAMES:
            frame = prediction_frames[name]
            if not isinstance(frame, pd.DataFrame):
                raise TypeError(f"prediction output {name!r} must be a DataFrame")
            serialized_predictions[name] = _csv_bytes(frame)
        for name in PLOT_NAMES:
            if not isinstance(plot_artifacts[name], bytes):
                raise TypeError(f"plot output {name!r} must contain bytes")
        if not isinstance(config_bytes, bytes):
            raise TypeError("config_bytes must contain bytes")
        serialized_model = _model_bytes(model)

        if config_source.read_bytes() != config_bytes:
            raise RuntimeError("training config changed before snapshot write")
        _atomic_publish_bytes(root, layout.run_dir, "config.yaml", config_bytes)
        _atomic_publish_bytes(
            descriptors["model"], layout.model_dir, MODEL_NAME, serialized_model
        )
        for name in JSON_ARTIFACT_NAMES:
            _atomic_publish_bytes(
                descriptors["artifacts"],
                layout.artifacts_dir,
                name,
                serialized_json[name],
            )
        for name in ARTIFACT_TABLE_NAMES:
            _atomic_publish_bytes(
                descriptors["artifacts"],
                layout.artifacts_dir,
                name,
                serialized_tables[name],
            )
        for name in PREDICTION_NAMES:
            _atomic_publish_bytes(
                descriptors["predictions"],
                layout.predictions_dir,
                name,
                serialized_predictions[name],
            )
        for name in PLOT_NAMES:
            _atomic_publish_bytes(
                descriptors["plots"],
                layout.plots_dir,
                name,
                plot_artifacts[name],
            )
        _assert_approved_contract(
            descriptors, manifest_present=False, terminal_lock_present=False
        )
        return TrainingArtifactReceipt(
            _RECEIPT_TOKEN, layout.directory_identities["."]
        )
    except Exception as error:
        _best_effort_failure(layout, error)
        raise
    finally:
        _close_descriptors(descriptors)


def _read_entry_bytes(descriptor: int, name: str) -> tuple[bytes, tuple[int, int]]:
    try:
        source = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=descriptor,
        )
    except FileNotFoundError as error:
        raise FileNotFoundError(f"required training output is missing: {name}") from error
    except OSError as error:
        raise ValueError(f"required training output is unsafe: {name}") from error
    try:
        file_stat = os.fstat(source)
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError(f"required training output is not a regular file: {name}")
        chunks: list[bytes] = []
        while chunk := os.read(source, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks), (file_stat.st_dev, file_stat.st_ino)
    finally:
        os.close(source)


def _output_record_from_descriptor(
    descriptor: int,
    path: Path,
    *,
    csv_rows: bool,
    compression: str | None = None,
) -> tuple[dict[str, Any], tuple[int, int]]:
    payload, identity = _read_entry_bytes(descriptor, path.name)
    record: dict[str, Any] = {
        "path": str(path),
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    if csv_rows:
        try:
            frame = pd.read_csv(io.BytesIO(payload), compression=compression)
        except Exception as error:
            raise ValueError(f"training CSV is invalid: {path.name}") from error
        record["row_count"] = len(frame)
    return record, identity


def _build_output_records(
    layout: TrainingOutputLayout, descriptors: Mapping[str, int]
) -> dict[str, dict[str, Any]]:
    outputs: dict[str, dict[str, Any]] = {}

    def add(
        directory: str,
        path: Path,
        *,
        csv_rows: bool = False,
        compression: str | None = None,
    ) -> None:
        relative = str(path.relative_to(layout.run_dir))
        outputs[relative], _ = _output_record_from_descriptor(
            descriptors[directory],
            path,
            csv_rows=csv_rows,
            compression=compression,
        )

    add(".", layout.config_snapshot)
    add("model", layout.model_dir / MODEL_NAME)
    for name in JSON_ARTIFACT_NAMES:
        add("artifacts", layout.artifacts_dir / name)
    for name in ARTIFACT_TABLE_NAMES:
        add("artifacts", layout.artifacts_dir / name, csv_rows=True)
    for name in PREDICTION_NAMES:
        add(
            "predictions",
            layout.predictions_dir / name,
            csv_rows=True,
            compression="gzip",
        )
    for name in PLOT_NAMES:
        add("plots", layout.plots_dir / name)
    return outputs


def _after_output_directories_open(layout: TrainingOutputLayout) -> None:
    """Test seam after publication holds the claimed root/child descriptors."""


def _before_named_layout_revalidation() -> None:
    """Test seam immediately before final named-path ownership validation."""


def _revalidate_named_layout(layout: TrainingOutputLayout) -> None:
    descriptors = _open_claimed_directories(layout)
    _close_descriptors(descriptors)


def publish_training_manifest(
    layout: TrainingOutputLayout,
    training_input: TrainingInput,
    *,
    receipt: TrainingArtifactReceipt,
    software: Mapping[str, Any],
    effective_parameters: Mapping[str, Any],
    features: list[str] | tuple[str, ...],
    sampling_fractions: Mapping[str, float],
    weight_policy: Mapping[str, Any],
    fold_policy: Mapping[str, Any],
    selected_model: Mapping[str, Any],
    working_points: Mapping[str, Any],
    warnings: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish one complete terminal manifest after an immediate final input check."""
    if not isinstance(receipt, TrainingArtifactReceipt):
        raise TypeError("publisher requires a TrainingArtifactReceipt")
    if (
        layout.directory_identities is None
        or receipt._run_identity != layout.directory_identities.get(".")
    ):
        raise ValueError("artifact receipt does not belong to this claimed run")

    descriptors: dict[str, int] | None = None
    locked = False
    staged_manifest: str | None = None
    try:
        descriptors = _open_claimed_directories(layout)
        root = descriptors["."]
        _after_output_directories_open(layout)
        _terminal_lock_acquire(root)
        locked = True
        if _entry_exists(root, ".terminal.failed") or _entry_exists(root, "failure.json"):
            raise RuntimeError("cannot publish a failed training run")
        if _entry_exists(descriptors["artifacts"], "training_manifest.json"):
            raise FileExistsError(
                f"output entry already exists: {layout.artifacts_dir / 'training_manifest.json'}"
            )
        _assert_approved_contract(
            descriptors, manifest_present=False, terminal_lock_present=True
        )
        outputs = _build_output_records(layout, descriptors)
        selected = dict(selected_model)
        selected["effective_parameters"] = dict(effective_parameters)
        manifest: dict[str, Any] = {
            "schema_version": "1.0",
            "status": "complete",
            "input_task4a": {
                "run_dir": str(training_input.input_run),
                "config_path": str(training_input.config_path),
                "mc_path": str(training_input.mc_path),
                "summary_path": str(training_input.summary_path),
                "manifest_path": str(training_input.manifest_path),
                "expected_rows": training_input.expected_rows,
                "hashes": dict(training_input.hashes),
            },
            "sampling_fractions": dict(sampling_fractions),
            "features": list(features),
            "weight_policy": dict(weight_policy),
            "cross_validation": dict(fold_policy),
            "selected_model": selected,
            "working_points": dict(working_points),
            "software": dict(software),
            "warnings": dict(warnings),
            "outputs": outputs,
        }
        serialized_manifest = _json_bytes(manifest)
        staged_manifest = _stage_bytes(
            descriptors["artifacts"], "training_manifest.json", serialized_manifest
        )
        _before_final_input_recheck()

        def completion_safety_check() -> None:
            assert_input_hashes_unchanged(training_input)
            _before_named_layout_revalidation()
            _revalidate_named_layout(layout)

        _promote_staged_no_clobber(
            descriptors["artifacts"],
            layout.artifacts_dir,
            staged_manifest,
            "training_manifest.json",
            immediate_check=completion_safety_check,
        )
        staged_manifest = None
        _assert_approved_contract(
            descriptors, manifest_present=True, terminal_lock_present=True
        )
        return manifest
    except Exception as error:
        if descriptors is not None:
            _cleanup_staged(descriptors.get("artifacts", descriptors["."]), staged_manifest)
            if locked:
                _install_failure_locked(descriptors["."], layout.run_dir, error)
            else:
                _best_effort_failure(layout, error)
        else:
            _best_effort_failure(layout, error)
        raise
    finally:
        if descriptors is not None and locked:
            _terminal_lock_release(descriptors["."])
        _close_descriptors(descriptors)
