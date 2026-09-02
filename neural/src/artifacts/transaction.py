from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType


_REPARSE_POINT = 0x400


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(path)):
        return True
    try:
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & _REPARSE_POINT)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise RunPathError(f"cannot inspect run path component: {path}") from error


class RunPathError(ValueError):
    """Raised when a requested run path violates the publication contract."""

    exit_code = 4


class RunTransaction:
    """Publish a new run directory atomically without ever overwriting a run."""

    def __init__(
        self,
        run_dir: str | Path,
        *,
        allowed_root: str | Path,
        safe_failure_message: str | None = None,
        safe_failure_stage: str | None = None,
    ) -> None:
        requested_run = Path(run_dir)
        requested_root = Path(allowed_root)
        if ".." in requested_run.parts or ".." in requested_root.parts:
            raise RunPathError("run directory is outside allowed root")
        self._requested_run = (
            requested_run if requested_run.is_absolute() else Path.cwd() / requested_run
        ).absolute()
        self._requested_root = (
            requested_root
            if requested_root.is_absolute()
            else Path.cwd() / requested_root
        ).absolute()
        try:
            relative = self._requested_run.relative_to(self._requested_root)
        except ValueError as error:
            raise RunPathError("run directory is outside allowed root") from error
        if not relative.parts:
            raise RunPathError("run directory is outside allowed root")
        try:
            self._requested_root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise RunPathError(
                f"cannot create allowed run root: {self._requested_root}"
            ) from error
        self._reject_link_components(self._requested_run.parent)
        try:
            self._requested_run.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise RunPathError(
                f"cannot create run parent directory: {self._requested_run.parent}"
            ) from error
        self._reject_link_components(self._requested_run.parent)
        self.allowed_root = self._requested_root.resolve(strict=True)
        self.run_dir = self._requested_run.resolve(strict=False)
        self._validate_target()
        self.path = self.run_dir.parent / f".{self.run_dir.name}.{uuid.uuid4().hex}.tmp"
        self.path.mkdir()
        self._finished = False
        self._safe_failure_message = safe_failure_message
        self._safe_failure_stage = safe_failure_stage

    def _reject_link_components(self, target_parent: Path) -> None:
        if _is_link_or_reparse(self._requested_root):
            raise RunPathError("allowed run root is a symlink or reparse point")
        try:
            relative = target_parent.relative_to(self._requested_root)
        except ValueError as error:
            raise RunPathError("run directory is outside allowed root") from error
        current = self._requested_root
        for part in relative.parts:
            current = current / part
            if _is_link_or_reparse(current):
                raise RunPathError("run directory contains a symlink or reparse point")

    def _validate_target(self) -> None:
        try:
            inside_root = os.path.commonpath([self.run_dir, self.allowed_root]) == str(
                self.allowed_root
            )
        except ValueError:
            inside_root = False
        if not inside_root or self.run_dir == self.allowed_root:
            raise RunPathError(f"run directory is outside allowed root: {self.run_dir}")
        if os.path.lexists(self._requested_run):
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
            message = self._safe_failure_message or str(exc)
            stage = getattr(exc, "stage", self._safe_failure_stage)
            self._write_failure_receipt(
                exc_type.__name__, message, self._exit_code(exc), stage=stage
            )
            self._publish()
        except BaseException as audit_error:
            preserved_path = self._preserve_failed_staging()
            if exc is not None:
                exc.add_note(
                    "failed to publish the run failure receipt; "
                    f"audit_error={audit_error!r}; staging={preserved_path}"
                )
        return False

    @staticmethod
    def _exit_code(error: BaseException | None) -> int:
        if error is not None and hasattr(error, "exit_code"):
            return int(error.exit_code)
        return 70

    def _write_failure_receipt(
        self,
        error_type: str,
        message: str,
        exit_code: int,
        *,
        stage: str | None = None,
    ) -> None:
        receipt = {
            "error_type": error_type,
            "exit_code": exit_code,
            "failed_at_utc": datetime.now(UTC).isoformat(),
            "message": message,
            "status": "failed",
        }
        if stage is not None:
            receipt["stage"] = stage
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
            message = self._safe_failure_message or str(error)
            stage = getattr(error, "stage", self._safe_failure_stage)
            self._write_failure_receipt(
                type(error).__name__,
                message,
                self._exit_code(error),
                stage=stage,
            )
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

    @property
    def published(self) -> bool:
        return self._finished and self.run_dir.is_dir()
