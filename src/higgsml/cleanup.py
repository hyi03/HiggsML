"""Constrained cleanup helpers for generated H4l workflow directories."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import shutil


def remove_run_directories(
    targets: Iterable[str | Path],
    *,
    allowed_root: str | Path,
) -> dict[str, list[Path]]:
    """Remove exact child directories without following caller-selected links."""
    root = Path(allowed_root).resolve()
    checked = []
    for value in targets:
        lexical = Path(value).absolute()
        if lexical.is_symlink():
            raise ValueError(f"Cleanup target cannot be a symbolic link: {lexical}")
        target = lexical.resolve()
        try:
            relative = target.relative_to(root)
        except ValueError as error:
            raise ValueError(f"Cleanup target must be below {root}: {target}") from error
        if not relative.parts:
            raise ValueError(f"Cleanup cannot target the runs root: {target}")
        if target.exists() and not target.is_dir():
            raise ValueError(f"Cleanup target is not a directory: {target}")
        if target not in checked:
            checked.append(target)

    removed = []
    missing = []
    for target in sorted(checked, key=lambda path: len(path.parts), reverse=True):
        if target.exists():
            shutil.rmtree(target)
            removed.append(target)
        else:
            missing.append(target)
    return {"removed": removed, "missing": missing}
