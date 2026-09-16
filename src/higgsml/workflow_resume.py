"""Shared validation and quarantine rules for resumable workflow stages."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable
import uuid

from higgsml.artifacts import LoadedRun, read_run
from higgsml.errors import ResearchError


def classify_stage(
    run_dir: str | Path,
    *,
    allowed_root: str | Path,
    dataset: str,
    protocol: dict,
    stages: tuple[str, ...],
    validator: Callable[[LoadedRun], None] | None = None,
) -> str:
    """Return run/skip/retry, preserving an invalid final directory in quarantine."""
    target = Path(run_dir)
    root = Path(allowed_root)
    try:
        relative = target.relative_to(root)
    except ValueError as error:
        raise ResearchError(f"stage run directory is outside workflow root: {target}") from error
    if not relative.parts:
        raise ResearchError(f"stage run directory cannot be workflow root: {target}")
    if not os.path.lexists(target):
        return "run"
    try:
        loaded = read_run(target, dataset=dataset, protocol=protocol, stages=stages)
        if validator is not None:
            validator(loaded)
    except ResearchError as error:
        quarantine = target.parent / f".{target.name}.{uuid.uuid4().hex}.invalid"
        try:
            target.rename(quarantine)
        except OSError as rename_error:
            raise ResearchError(f"cannot quarantine invalid stage run: {target}") from rename_error
        print(f"QUARANTINE invalid: {target} -> {quarantine} ({error})", flush=True)
        return "retry"
    print(f"SKIP complete: {target}", flush=True)
    return "skip"
