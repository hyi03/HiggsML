from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from types import TracebackType


class RunPathError(ValueError):
    """Raised when a requested run path violates the publication contract."""


class RunTransaction:
    """Publish a new run directory atomically without ever overwriting a run."""

    def __init__(self, run_dir: str | Path, *, allowed_root: str | Path) -> None:
        self.run_dir = Path(run_dir).resolve(strict=False)
        self.allowed_root = Path(allowed_root).resolve(strict=False)
        self._validate_target()
        self.allowed_root.mkdir(parents=True, exist_ok=True)
        try:
            self.run_dir.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise RunPathError(
                f"cannot create run parent directory: {self.run_dir.parent}"
            ) from error
        self.path = self.run_dir.parent / f".{self.run_dir.name}.{uuid.uuid4().hex}.tmp"
        self.path.mkdir()
        self._finished = False

    def _validate_target(self) -> None:
        try:
            inside_root = os.path.commonpath([self.run_dir, self.allowed_root]) == str(
                self.allowed_root
            )
        except ValueError:
            inside_root = False
        if not inside_root or self.run_dir == self.allowed_root:
            raise RunPathError(f"run directory is outside allowed root: {self.run_dir}")
        if self.run_dir.exists():
            raise RunPathError(f"run directory already exists: {self.run_dir}")

    def __enter__(self) -> RunTransaction:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del traceback
        if exc_type is None:
            try:
                self._publish()
            except BaseException as publish_error:
                self._record_publish_failure(publish_error)
                raise
            return False

        try:
            self._write_failure_receipt(exc_type.__name__, str(exc))
            self._publish()
        except BaseException as audit_error:
            preserved_path = self._preserve_failed_staging()
            if exc is not None:
                exc.add_note(
                    "failed to publish the run failure receipt; "
                    f"audit_error={audit_error!r}; staging={preserved_path}"
                )
        return False

    def _write_failure_receipt(self, error_type: str, message: str) -> None:
        receipt = {
            "error_type": error_type,
            "message": message,
            "status": "failed",
        }
        (self.path / "failure.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _publish(self) -> None:
        if self._finished:
            raise RuntimeError("run transaction already finished")
        if self.run_dir.exists():
            raise RunPathError(f"run directory already exists: {self.run_dir}")
        try:
            self.path.rename(self.run_dir)
        except OSError as error:
            raise RunPathError(f"cannot publish run directory: {self.run_dir}") from error
        self._finished = True

    def _record_publish_failure(self, error: BaseException) -> None:
        try:
            self._write_failure_receipt(type(error).__name__, str(error))
        finally:
            self._preserve_failed_staging()

    def _preserve_failed_staging(self) -> Path:
        if self._finished or not self.path.exists():
            return self.path
        failed_path = self.path.with_suffix(".failed")
        try:
            self.path.rename(failed_path)
        except OSError:
            return self.path
        self.path = failed_path
        return failed_path

    def abort_without_receipt(self) -> None:
        """Remove only this transaction's unpublished staging directory."""
        if not self._finished and self.path.exists():
            shutil.rmtree(self.path)
            self._finished = True
