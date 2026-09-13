"""Stable directory naming for the three H4l workflow scripts."""

from __future__ import annotations

import re


RUN_DIRECTORY_PREFIX = "h4l-feature-combinations-prerequisites-"
_RUN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def workflow_directory_name(run_name: str) -> str:
    """Return the shared workflow directory name for a safe short run name."""
    if not isinstance(run_name, str) or _RUN_NAME.fullmatch(run_name) is None:
        raise ValueError(
            "run name must contain 1-64 letters, digits, underscores, or hyphens "
            "and must start with a letter or digit"
        )
    return f"{RUN_DIRECTORY_PREFIX}{run_name}"
