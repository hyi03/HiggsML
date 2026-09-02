from __future__ import annotations

import os
from pathlib import Path, PurePath
from types import TracebackType
from typing import Any

from .manifest import canonical_json_bytes


class RunTransaction:
    """Claim one fresh run directory and publish entries without clobbering."""

    def __init__(self, run_dir: str | Path, *, runs_root: str | Path) -> None:
        self.run_dir = Path(run_dir).absolute()
        self.runs_root = Path(runs_root).absolute()
        self._published = False
        self._claimed = False
        self._resolved_run_dir: Path | None = None

    def __enter__(self) -> "RunTransaction":
        self._validate_target()
        self.run_dir.mkdir()
        self._claimed = True
        self._resolved_run_dir = self.run_dir.resolve(strict=True)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if exc is not None and not self._published:
            self._write_failure(exc)
        elif not self._published:
            self._write_failure(RuntimeError("run exited without a success manifest"))
        return False

    def write_bytes(self, relative_path: str | PurePath, content: bytes) -> Path:
        if not self._claimed:
            raise RuntimeError("run directory has not been claimed")
        if self._published:
            raise RuntimeError("cannot write artifacts after publication")
        destination = self._safe_destination(relative_path)
        with destination.open("xb") as handle:
            handle.write(content)
        return destination

    def _safe_destination(
        self, relative_path: str | PurePath, *, terminal: bool = False
    ) -> Path:
        raw_path = str(relative_path)
        relative = PurePath(relative_path)
        if (
            raw_path.startswith(("/", "\\"))
            or relative.is_absolute()
            or bool(relative.drive)
            or ".." in relative.parts
            or not relative.parts
        ):
            raise ValueError("output path must be a safe relative path")
        if not terminal and relative.as_posix() in {"manifest.json", "failure.json"}:
            raise ValueError("terminal receipt names are reserved")
        if self._resolved_run_dir is None:
            raise RuntimeError("run directory has not been claimed")
        if self.run_dir.is_symlink() or self.run_dir.resolve(strict=True) != self._resolved_run_dir:
            raise ValueError("claimed run directory was replaced")
        destination = self.run_dir.joinpath(*relative.parts)
        current = self.run_dir
        for part in relative.parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise ValueError("symlink output paths are not allowed")
            current.mkdir(exist_ok=True)
            resolved = current.resolve(strict=True)
            if self._resolved_run_dir not in resolved.parents:
                raise ValueError("output path must stay inside the claimed run directory")
        resolved_parent = destination.parent.resolve(strict=True)
        if (
            resolved_parent != self._resolved_run_dir
            and self._resolved_run_dir not in resolved_parent.parents
        ):
            raise ValueError("output path must stay inside the claimed run directory")
        if destination.is_symlink():
            raise ValueError("symlink output paths are not allowed")
        return destination

    def publish_manifest(
        self, payload: Any, relative_path: str | PurePath = "manifest.json"
    ) -> Path:
        if not self._claimed:
            raise RuntimeError("run directory has not been claimed")
        if self._published:
            raise RuntimeError("manifest has already been published")
        destination = self._safe_destination(relative_path, terminal=True)
        with destination.open("xb") as handle:
            handle.write(canonical_json_bytes(payload))
        self._published = True
        return destination

    def _validate_target(self) -> None:
        if not self.runs_root.is_dir() or self.runs_root.is_symlink():
            raise ValueError("runs_root must be an existing non-symlink directory")
        root = self.runs_root.resolve(strict=True)
        target_parent = self.run_dir.parent.resolve(strict=True)
        if target_parent != root:
            raise ValueError("run directory must be a direct child of runs_root")
        if os.path.lexists(self.run_dir):
            raise FileExistsError(self.run_dir)

    def _write_failure(self, exc: BaseException) -> None:
        try:
            failure = self._safe_destination("failure.json", terminal=True)
        except (RuntimeError, ValueError):
            return
        if failure.exists() or failure.is_symlink():
            return
        payload = {
            "schema_version": "1.0",
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        try:
            with failure.open("xb") as handle:
                handle.write(canonical_json_bytes(payload))
        except FileExistsError:
            pass
