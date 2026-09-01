"""Immutable input resolution and manifest-last publication for Task 5."""

from __future__ import annotations

import ctypes
import errno
import gzip
import hashlib
import io
import json
import os
import stat
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd

from .features import FEATURES
from . import full_training_run as _safety


EXTERNAL_PLOT_NAMES = (
    "external_score_comparison.png",
    "external_kinematics_comparison.png",
    "external_mass_comparison.png",
)
EXTERNAL_OUTPUT_NAMES = frozenset(
    {
        "config.yaml",
        "artifacts/metrics.json",
        "predictions/external_zz_scores.csv.gz",
        *(f"plots/{name}" for name in EXTERNAL_PLOT_NAMES),
    }
)
_TRAINING_OUTPUT_NAMES = frozenset(
    {
        "config.yaml",
        f"model/{_safety.MODEL_NAME}",
        *(f"artifacts/{name}" for name in _safety.JSON_ARTIFACT_NAMES),
        *(f"artifacts/{name}" for name in _safety.ARTIFACT_TABLE_NAMES),
        *(f"predictions/{name}" for name in _safety.PREDICTION_NAMES),
        *(f"plots/{name}" for name in _safety.PLOT_NAMES),
    }
)


@dataclass(frozen=True)
class ExternalZZInputs:
    training_run: Path
    training_manifest_path: Path
    model_path: Path
    working_points_path: Path
    test_scores_path: Path
    external_root_path: Path
    config_path: Path
    hashes: Mapping[str, str]
    sizes: Mapping[str, int]
    snapshots: Mapping[str, bytes]
    working_points: Mapping[str, Any]
    training_test: pd.DataFrame


@dataclass(frozen=True)
class ExternalZZOutputLayout:
    run_dir: Path
    config_snapshot: Path
    artifacts_dir: Path
    predictions_dir: Path
    plots_dir: Path
    directory_identities: Mapping[str, tuple[int, int]] | None = None


_RECEIPT_TOKEN = object()


@dataclass(frozen=True, init=False)
class ExternalZZArtifactReceipt:
    _run_identity: tuple[int, int]

    def __new__(
        cls, token: object = None, run_identity: tuple[int, int] | None = None
    ):
        if token is not _RECEIPT_TOKEN or run_identity is None:
            raise TypeError(
                "ExternalZZArtifactReceipt is returned by write_external_zz_artifacts"
            )
        return super().__new__(cls)

    def __init__(self, token: object, run_identity: tuple[int, int]) -> None:
        object.__setattr__(self, "_run_identity", run_identity)


def resolve_external_zz_inputs(
    *,
    training_run: str | Path,
    config_path: str | Path,
    external_root: str | Path,
) -> ExternalZZInputs:
    """Validate and snapshot every small frozen input before execution."""
    run = _require_safe_directory(Path(training_run), "training run")
    config = Path(config_path)
    external = Path(external_root)
    paths = {
        "training_manifest": run / "artifacts/training_manifest.json",
        "model": run / f"model/{_safety.MODEL_NAME}",
        "working_points": run / "artifacts/working_points.json",
        "test_scores": run / "predictions/test_scores.csv.gz",
        "external_root": external,
        "config": config,
    }

    snapshots = {
        name: _read_safe_regular(path, name)
        for name, path in paths.items()
        if name != "external_root"
    }
    external_hash, external_size = _hash_safe_regular(external, "external ROOT")
    hashes = {
        name: hashlib.sha256(payload).hexdigest()
        for name, payload in snapshots.items()
    }
    sizes = {name: len(payload) for name, payload in snapshots.items()}
    hashes["external_root"] = external_hash
    sizes["external_root"] = external_size

    manifest = _parse_json(snapshots["training_manifest"], "training manifest")
    _validate_training_manifest(
        run,
        manifest,
        input_hashes=hashes,
        input_sizes=sizes,
    )
    points = _parse_json(snapshots["working_points"], "working points")
    if points != manifest.get("working_points"):
        raise ValueError("training working points do not match the complete manifest")
    try:
        test_scores = pd.read_csv(
            io.BytesIO(snapshots["test_scores"]), compression="gzip"
        )
    except Exception as error:
        raise ValueError("training test scores are not a valid gzip CSV") from error

    if snapshot_external_input_hashes_from_paths(paths) != hashes:
        raise RuntimeError("external validation input changed during resolution")
    return ExternalZZInputs(
        training_run=run,
        training_manifest_path=paths["training_manifest"],
        model_path=paths["model"],
        working_points_path=paths["working_points"],
        test_scores_path=paths["test_scores"],
        external_root_path=paths["external_root"],
        config_path=paths["config"],
        hashes=MappingProxyType(dict(hashes)),
        sizes=MappingProxyType(dict(sizes)),
        snapshots=MappingProxyType(dict(snapshots)),
        working_points=MappingProxyType(dict(points)),
        training_test=test_scores,
    )


def _validate_training_manifest(
    run: Path,
    manifest: Mapping[str, Any],
    *,
    input_hashes: Mapping[str, str],
    input_sizes: Mapping[str, int],
) -> None:
    if manifest.get("schema_version") != "1.0" or manifest.get("status") != "complete":
        raise ValueError("training manifest must be schema 1.0 and complete")
    if manifest.get("features") != FEATURES:
        raise ValueError("training manifest does not use the frozen FEATURES contract")
    expected_root = {"config.yaml", "model", "artifacts", "predictions", "plots"}
    if {entry.name for entry in run.iterdir()} != expected_root:
        raise ValueError("training run root contract is incomplete or contradictory")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, Mapping) or set(outputs) != _TRAINING_OUTPUT_NAMES:
        raise ValueError("training output contract is incomplete or contains extras")

    actual = set()
    for directory in ("model", "artifacts", "predictions", "plots"):
        child = _require_safe_directory(run / directory, f"training {directory}")
        for entry in child.iterdir():
            if entry.is_symlink():
                raise ValueError("training output contract contains a symlink")
            if entry.is_file():
                relative = entry.relative_to(run).as_posix()
                if relative != "artifacts/training_manifest.json":
                    actual.add(relative)
            else:
                raise ValueError("training output contract contains a non-file entry")
    if (run / "config.yaml").is_file():
        actual.add("config.yaml")
    if actual != _TRAINING_OUTPUT_NAMES:
        raise ValueError("training output contract does not match the complete run")

    externally_consumed = {
        f"model/{_safety.MODEL_NAME}": "model",
        "artifacts/working_points.json": "working_points",
        "predictions/test_scores.csv.gz": "test_scores",
    }
    for relative in sorted(_TRAINING_OUTPUT_NAMES):
        record = outputs[relative]
        if not isinstance(record, Mapping):
            raise ValueError("training output manifest record must be an object")
        actual_size = _safe_regular_size(
            run / relative, f"training output {relative}"
        )
        if record.get("size_bytes") != actual_size:
            raise ValueError(f"training output size does not match: {relative}")
        input_name = externally_consumed.get(relative)
        if input_name is not None and (
            record.get("sha256") != input_hashes[input_name]
            or record.get("size_bytes") != input_sizes[input_name]
        ):
            raise ValueError(f"training output hash does not match: {relative}")


def resolve_external_zz_output(
    *,
    project_root: Path,
    working_directory: Path,
    training_run: str | Path,
    run_dir: str | Path,
) -> ExternalZZOutputLayout:
    logical = Path(run_dir)
    unresolved = logical if logical.is_absolute() else working_directory.resolve() / logical
    resolved = _safety._absolute_without_symlinks(
        unresolved, allow_final_symlink=True
    )
    project = project_root.resolve()
    training = Path(training_run).absolute()
    protected = [
        project / name
        for name in (
            "data",
            "outputs",
            "config",
            "docs",
            "src",
            "scripts",
            "tests",
            ".git",
            ".venv",
        )
    ]
    if resolved == project or any(_safety._is_within(resolved, path) for path in protected):
        raise ValueError("external validation --run-dir is inside a protected path")
    if _safety._is_within(resolved, training):
        raise ValueError("external validation --run-dir is inside the training run")
    if resolved.exists() or resolved.is_symlink():
        raise FileExistsError(
            f"external validation run directory already exists: {logical}"
        )
    return ExternalZZOutputLayout(
        run_dir=resolved,
        config_snapshot=resolved / "config.yaml",
        artifacts_dir=resolved / "artifacts",
        predictions_dir=resolved / "predictions",
        plots_dir=resolved / "plots",
    )


def claim_external_zz_output(
    layout: ExternalZZOutputLayout,
) -> ExternalZZOutputLayout:
    if layout.directory_identities is not None:
        raise RuntimeError("external validation output is already claimed")
    parent = _safety._open_claim_parent(layout.run_dir)
    root: int | None = None
    try:
        try:
            os.mkdir(layout.run_dir.name, dir_fd=parent)
        except FileExistsError as error:
            raise FileExistsError(
                f"external validation run directory already exists: {layout.run_dir}"
            ) from error
        root = os.open(layout.run_dir.name, _safety._directory_flags(), dir_fd=parent)
        identities = {".": _safety._identity(root)}
        try:
            for name in ("artifacts", "predictions", "plots"):
                os.mkdir(name, dir_fd=root)
                child = os.open(name, _safety._directory_flags(), dir_fd=root)
                try:
                    identities[name] = _safety._identity(child)
                finally:
                    os.close(child)
        except Exception as error:
            _install_external_failure_locked(root, layout.run_dir, error)
            raise
        return replace(
            layout, directory_identities=MappingProxyType(dict(identities))
        )
    finally:
        if root is not None:
            os.close(root)
        os.close(parent)


def write_external_zz_artifacts(
    layout: ExternalZZOutputLayout,
    *,
    config_source: Path,
    config_bytes: bytes,
    metrics: Mapping[str, Any],
    scores: pd.DataFrame,
    plots: Mapping[str, bytes],
) -> ExternalZZArtifactReceipt:
    descriptors: dict[str, int] | None = None
    try:
        descriptors = _open_claimed(layout)
        if _safety._entry_exists(descriptors["."], ".terminal.failed"):
            raise RuntimeError("cannot write a failed external validation run")
        _assert_layout(descriptors, manifest_present=False, empty=True)
        if set(plots) != set(EXTERNAL_PLOT_NAMES):
            raise ValueError("external plot outputs do not match the approved contract")
        if not isinstance(scores, pd.DataFrame):
            raise TypeError("external scores must be a DataFrame")
        if not isinstance(config_bytes, bytes):
            raise TypeError("external config snapshot must be bytes")
        serialized_metrics = _safety._json_bytes(metrics)
        serialized_scores = gzip.compress(
            scores.to_csv(index=False).encode("utf-8"), mtime=0
        )
        for name in EXTERNAL_PLOT_NAMES:
            if not isinstance(plots[name], bytes):
                raise TypeError(f"external plot {name} must contain bytes")
        if config_source.read_bytes() != config_bytes:
            raise RuntimeError("external validation config changed before snapshot write")

        _safety._atomic_publish_bytes(
            descriptors["."], layout.run_dir, "config.yaml", config_bytes
        )
        _safety._atomic_publish_bytes(
            descriptors["artifacts"],
            layout.artifacts_dir,
            "metrics.json",
            serialized_metrics,
        )
        _safety._atomic_publish_bytes(
            descriptors["predictions"],
            layout.predictions_dir,
            "external_zz_scores.csv.gz",
            serialized_scores,
        )
        for name in EXTERNAL_PLOT_NAMES:
            _safety._atomic_publish_bytes(
                descriptors["plots"], layout.plots_dir, name, plots[name]
            )
        _assert_layout(descriptors, manifest_present=False, empty=False)
        return ExternalZZArtifactReceipt(
            _RECEIPT_TOKEN, layout.directory_identities["."]
        )
    except Exception as error:
        _best_effort_external_failure(layout, error)
        raise
    finally:
        if descriptors is not None:
            _close_descriptors(descriptors)


def publish_external_zz_manifest(
    layout: ExternalZZOutputLayout,
    inputs: ExternalZZInputs,
    *,
    receipt: ExternalZZArtifactReceipt,
    software: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(receipt, ExternalZZArtifactReceipt):
        raise TypeError("external manifest publisher requires an artifact receipt")
    if (
        layout.directory_identities is None
        or receipt._run_identity != layout.directory_identities.get(".")
    ):
        raise ValueError("external artifact receipt does not belong to this run")
    descriptors: dict[str, int] | None = None
    locked = False
    staged: str | None = None
    staged_descriptor: int | None = None
    try:
        descriptors = _open_claimed(layout)
        root = descriptors["."]
        _safety._terminal_lock_acquire(root)
        locked = True
        if _safety._entry_exists(root, ".terminal.failed") or _safety._entry_exists(
            root, "failure.json"
        ):
            raise RuntimeError("cannot publish a failed external validation run")
        if _safety._entry_exists(root, "manifest.json"):
            raise FileExistsError(
                f"external validation manifest already exists: {layout.run_dir / 'manifest.json'}"
            )
        _assert_layout(
            descriptors,
            manifest_present=False,
            empty=False,
            terminal_lock_present=True,
        )
        outputs = _output_records(layout, descriptors)
        paths = _input_paths(inputs)
        manifest = {
            "schema_version": "1.0",
            "status": "complete",
            "role": "frozen external ZZ generator/release validation",
            "training_dsid": 363490,
            "external_dsid": 700600,
            "features": list(FEATURES),
            "software": dict(software),
            "inputs": {
                name: {
                    "path": str(paths[name]),
                    "size_bytes": int(inputs.sizes[name]),
                    "sha256": inputs.hashes[name],
                }
                for name in paths
            },
            "outputs": outputs,
        }
        serialized = _safety._json_bytes(manifest)
        staged = _safety._stage_bytes(
            descriptors["."], "manifest.json", serialized
        )
        staged_descriptor, staged_identity = _open_verified_staged_manifest(
            descriptors["."], staged, serialized
        )

        def final_check() -> None:
            assert_external_input_hashes_unchanged(inputs)
            _assert_staged_manifest_unchanged(
                descriptors["."],
                staged,
                staged_descriptor,
                staged_identity,
                serialized,
            )
            _assert_layout(
                descriptors,
                manifest_present=False,
                empty=False,
                terminal_lock_present=True,
                ignored_root_entries={staged},
            )
            if _output_records(layout, descriptors) != outputs:
                raise RuntimeError("external validation output changed before manifest")
            current = _open_claimed(layout)
            _close_descriptors(current)

        _promote_bound_manifest_no_clobber(
            descriptors["."],
            layout.run_dir,
            staged,
            staged_descriptor,
            staged_identity,
            serialized,
            "manifest.json",
            immediate_check=final_check,
        )
        staged = None
        os.close(staged_descriptor)
        staged_descriptor = None
        _assert_layout(
            descriptors,
            manifest_present=True,
            empty=False,
            terminal_lock_present=True,
        )
        return manifest
    except Exception as error:
        if descriptors is not None:
            _safety._cleanup_staged(descriptors["."], staged)
            staged = None
            if locked:
                _install_external_failure_locked(
                    descriptors["."], layout.run_dir, error
                )
            else:
                _best_effort_external_failure(layout, error)
        else:
            _best_effort_external_failure(layout, error)
        raise
    finally:
        if descriptors is not None:
            _safety._cleanup_staged(descriptors["."], staged)
            if staged_descriptor is not None:
                os.close(staged_descriptor)
            if locked:
                _safety._terminal_lock_release(descriptors["."])
            _close_descriptors(descriptors)


def _before_bound_external_manifest_publish(destination: Path) -> None:
    """Test seam after final checks and before descriptor-bound publication."""


def _open_verified_staged_manifest(
    root: int, staged: str, expected: bytes
) -> tuple[int, tuple[int, int]]:
    try:
        descriptor = os.open(
            staged,
            os.O_RDONLY
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root,
        )
    except (OSError, FileNotFoundError) as error:
        raise ValueError("external staged manifest is unsafe") from error
    try:
        metadata = os.fstat(descriptor)
        identity = (metadata.st_dev, metadata.st_ino)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError("external staged manifest is not an owned regular file")
        if _read_descriptor_bytes(descriptor) != expected:
            raise ValueError("external staged manifest content changed")
        return descriptor, identity
    except Exception:
        os.close(descriptor)
        raise


def _read_descriptor_bytes(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while chunk := os.read(descriptor, 1024 * 1024):
        chunks.append(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return b"".join(chunks)


def _assert_staged_manifest_unchanged(
    root: int,
    staged: str,
    descriptor: int,
    expected_identity: tuple[int, int],
    expected: bytes,
) -> None:
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (metadata.st_dev, metadata.st_ino) != expected_identity
        or _read_descriptor_bytes(descriptor) != expected
    ):
        raise ValueError("external staged manifest identity or content changed")
    try:
        current, current_identity = _safety._read_entry_bytes(root, staged)
    except (OSError, ValueError, FileNotFoundError) as error:
        raise ValueError("external staged manifest is unsafe") from error
    if current_identity != expected_identity or current != expected:
        raise ValueError("external staged manifest identity or content changed")


def _promote_bound_manifest_no_clobber(
    root: int,
    parent: Path,
    staged: str,
    staged_descriptor: int,
    staged_identity: tuple[int, int],
    expected: bytes,
    final_name: str,
    *,
    immediate_check,
) -> None:
    destination = parent / final_name
    _safety._before_no_clobber_promote(destination)
    immediate_check()
    _before_bound_external_manifest_publish(destination)
    _assert_staged_manifest_unchanged(
        root, staged, staged_descriptor, staged_identity, expected
    )
    try:
        _publish_descriptor_no_clobber(
            staged_descriptor, root, final_name, destination
        )
    finally:
        _safety._cleanup_staged(root, staged)


def _publish_descriptor_no_clobber(
    source: int, destination_directory: int, name: str, destination: Path
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    encoded_name = os.fsencode(name)
    if sys.platform == "darwin":
        publish = libc.fclonefileat
        publish.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint32,
        ]
        publish.restype = ctypes.c_int
        result = publish(source, destination_directory, encoded_name, 0)
    elif sys.platform.startswith("linux"):
        publish = libc.linkat
        publish.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
        ]
        publish.restype = ctypes.c_int
        result = publish(
            -100,
            os.fsencode(f"/proc/self/fd/{source}"),
            destination_directory,
            encoded_name,
            0x400,
        )
    else:
        raise RuntimeError("descriptor-bound manifest publication is unsupported")
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(f"output entry already exists: {destination}")
    raise OSError(
        error_number,
        f"descriptor-bound manifest publication failed: {destination}",
    )


def snapshot_external_input_hashes(
    inputs: ExternalZZInputs,
) -> Mapping[str, str]:
    return MappingProxyType(snapshot_external_input_hashes_from_paths(_input_paths(inputs)))


def snapshot_external_input_hashes_from_paths(
    paths: Mapping[str, Path],
) -> dict[str, str]:
    output = {}
    for name, path in paths.items():
        digest, _ = _hash_safe_regular(path, name)
        output[name] = digest
    return output


def assert_external_input_hashes_unchanged(inputs: ExternalZZInputs) -> None:
    try:
        current = snapshot_external_input_hashes(inputs)
    except (OSError, ValueError, FileNotFoundError) as error:
        raise RuntimeError("external validation input changed") from error
    if dict(current) != dict(inputs.hashes):
        raise RuntimeError("external validation input changed")


def record_external_zz_failure(
    layout: ExternalZZOutputLayout, error: BaseException
) -> None:
    """Best-effort failure record for an already-claimed incomplete run."""
    _best_effort_external_failure(layout, error)


def _best_effort_external_failure(
    layout: ExternalZZOutputLayout, error: BaseException
) -> None:
    try:
        root = _open_verified_root(layout)
    except Exception:
        return
    locked = False
    try:
        _safety._terminal_lock_acquire(root)
        locked = True
        _install_external_failure_locked(root, layout.run_dir, error)
    except Exception:
        pass
    finally:
        if locked:
            _safety._terminal_lock_release(root)
        os.close(root)


def _install_external_failure_locked(
    root: int, run_dir: Path, error: BaseException
) -> None:
    if _safety._entry_exists(root, "manifest.json"):
        return
    try:
        os.mkdir(".terminal.failed", dir_fd=root)
    except FileExistsError:
        pass
    if _safety._entry_exists(root, "failure.json"):
        return
    try:
        _safety._atomic_publish_bytes(
            root,
            run_dir,
            "failure.json",
            _safety._json_bytes(
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "message": str(error),
                }
            ),
        )
    except Exception:
        # The owned directory sentinel is the authoritative fail-closed state.
        pass


def _open_verified_root(layout: ExternalZZOutputLayout) -> int:
    if layout.directory_identities is None:
        raise RuntimeError("external validation output has not been claimed")
    root = _safety._open_absolute_directory_no_follow(layout.run_dir)
    if _safety._identity(root) != layout.directory_identities.get("."):
        os.close(root)
        raise ValueError("external validation run ownership changed")
    return root


def _input_paths(inputs: ExternalZZInputs) -> dict[str, Path]:
    return {
        "training_manifest": inputs.training_manifest_path,
        "model": inputs.model_path,
        "working_points": inputs.working_points_path,
        "test_scores": inputs.test_scores_path,
        "external_root": inputs.external_root_path,
        "config": inputs.config_path,
    }


def _require_safe_directory(path: Path, name: str) -> Path:
    _assert_no_symlink_components(path)
    if not path.is_dir():
        raise FileNotFoundError(f"{name} is missing or is not a directory: {path}")
    return path


def _assert_no_symlink_components(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"input path contains a symlink component: {current}")


def _read_safe_regular(path: Path, name: str) -> bytes:
    _assert_no_symlink_components(path)
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
    except FileNotFoundError as error:
        raise FileNotFoundError(f"required {name} input is missing: {path}") from error
    except OSError as error:
        raise ValueError(f"required {name} input is unsafe: {path}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"required {name} input is not a regular file")
        chunks = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _hash_safe_regular(path: Path, name: str) -> tuple[str, int]:
    payload = _read_safe_regular(path, name)
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _safe_regular_size(path: Path, name: str) -> int:
    _assert_no_symlink_components(path)
    try:
        metadata = path.stat(follow_symlinks=False)
    except FileNotFoundError as error:
        raise FileNotFoundError(f"required {name} input is missing: {path}") from error
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"required {name} input is not a regular file")
    return int(metadata.st_size)


def _parse_json(payload: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} is not valid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return value


def _open_claimed(layout: ExternalZZOutputLayout) -> dict[str, int]:
    expected = layout.directory_identities
    if expected is None:
        raise RuntimeError("external validation output has not been claimed")
    descriptors: dict[str, int] = {}
    try:
        root = _safety._open_absolute_directory_no_follow(layout.run_dir)
        descriptors["."] = root
        if _safety._identity(root) != expected.get("."):
            raise ValueError("external validation run ownership changed")
        for name in ("artifacts", "predictions", "plots"):
            child = os.open(name, _safety._directory_flags(), dir_fd=root)
            descriptors[name] = child
            if _safety._identity(child) != expected.get(name):
                raise ValueError(f"external validation child ownership changed: {name}")
        return descriptors
    except Exception:
        _close_descriptors(descriptors)
        raise


def _close_descriptors(descriptors: Mapping[str, int]) -> None:
    for descriptor in reversed(tuple(descriptors.values())):
        os.close(descriptor)


def _assert_layout(
    descriptors: Mapping[str, int],
    *,
    manifest_present: bool,
    empty: bool,
    terminal_lock_present: bool = False,
    ignored_root_entries: set[str] | frozenset[str] = frozenset(),
) -> None:
    root_expected = {"artifacts", "predictions", "plots"}
    if not empty:
        root_expected.add("config.yaml")
    if manifest_present:
        root_expected.add("manifest.json")
    if terminal_lock_present:
        root_expected.add(".terminal.lock")
    root_actual = set(os.listdir(descriptors["."])) - set(ignored_root_entries)
    if root_actual != root_expected:
        raise FileExistsError("external validation output entry already exists or is missing")
    expected = {
        "artifacts": set() if empty else {"metrics.json"},
        "predictions": set() if empty else {"external_zz_scores.csv.gz"},
        "plots": set() if empty else set(EXTERNAL_PLOT_NAMES),
    }
    for name, names in expected.items():
        if set(os.listdir(descriptors[name])) != names:
            raise FileExistsError("external validation output entry already exists or is missing")


def _output_records(
    layout: ExternalZZOutputLayout, descriptors: Mapping[str, int]
) -> dict[str, dict[str, Any]]:
    mapping = {
        "config.yaml": (".", layout.config_snapshot, False, None),
        "artifacts/metrics.json": (
            "artifacts",
            layout.artifacts_dir / "metrics.json",
            False,
            None,
        ),
        "predictions/external_zz_scores.csv.gz": (
            "predictions",
            layout.predictions_dir / "external_zz_scores.csv.gz",
            True,
            "gzip",
        ),
        **{
            f"plots/{name}": ("plots", layout.plots_dir / name, False, None)
            for name in EXTERNAL_PLOT_NAMES
        },
    }
    output = {}
    for relative, (directory, path, csv_rows, compression) in mapping.items():
        payload, _ = _safety._read_entry_bytes(descriptors[directory], path.name)
        record: dict[str, Any] = {
            "path": str(path),
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        if csv_rows:
            try:
                record["row_count"] = len(
                    pd.read_csv(io.BytesIO(payload), compression=compression)
                )
            except Exception as error:
                raise ValueError("external scores output is not a valid CSV") from error
        output[relative] = record
    if set(output) != EXTERNAL_OUTPUT_NAMES:
        raise RuntimeError("internal external output contract mismatch")
    return output
