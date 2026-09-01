from __future__ import annotations

import json
from dataclasses import dataclass
from numbers import Integral
from pathlib import Path
from typing import Any, Literal, Mapping

import pandas as pd


def _positive_integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


@dataclass(frozen=True)
class ReadPolicy:
    mode: Literal["head", "full"]
    entry_stop: int | None
    chunk_size_events: int

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "entry_stop": self.entry_stop,
            "chunk_size_events": self.chunk_size_events,
        }


@dataclass(frozen=True)
class OutputLayout:
    run_dir: Path | None
    processed_dir: Path
    artifacts_dir: Path
    config_snapshot: Path | None

    def manifest_locations(self) -> dict[str, str | None]:
        return {
            "run_dir": None if self.run_dir is None else str(self.run_dir),
            "processed_dir": str(self.processed_dir),
            "artifacts_dir": str(self.artifacts_dir),
        }


def _is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _path_entry_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def resolve_output_layout(
    *,
    project_root: Path,
    working_directory: Path,
    read_policy: ReadPolicy,
    run_dir: str | Path | None,
    output_dir: str | Path | None,
) -> OutputLayout:
    if read_policy.mode == "full" and run_dir is None:
        raise ValueError("full read mode requires --run-dir")
    if run_dir is not None and output_dir is not None:
        raise ValueError("--run-dir and --output-dir cannot be used together")
    if run_dir is None:
        return OutputLayout(
            run_dir=None,
            processed_dir=Path("data/processed"),
            artifacts_dir=Path("outputs") if output_dir is None else Path(output_dir),
            config_snapshot=None,
        )

    logical_run_dir = Path(run_dir)
    resolved_project = project_root.resolve()
    unresolved_run = (
        logical_run_dir
        if logical_run_dir.is_absolute()
        else working_directory.resolve() / logical_run_dir
    )
    resolved_run = unresolved_run.resolve()
    protected_descendants = [
        resolved_project / "data/raw",
        resolved_project / "data/processed",
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
        _is_within(resolved_run, path.resolve()) for path in protected_descendants
    ):
        raise ValueError("--run-dir resolves inside a protected project path")
    if _path_entry_exists(unresolved_run):
        raise FileExistsError(f"run directory already exists: {logical_run_dir}")
    return OutputLayout(
        run_dir=logical_run_dir,
        processed_dir=logical_run_dir / "processed",
        artifacts_dir=logical_run_dir / "artifacts",
        config_snapshot=logical_run_dir / "config.yaml",
    )


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"


def write_preparation_outputs(
    layout: OutputLayout,
    *,
    config_source: Path,
    config_bytes: bytes,
    mc_frame: pd.DataFrame,
    data_frame: pd.DataFrame,
    cutflow_payload: Mapping[str, Any],
    summary_payload: Mapping[str, Any],
    manifest_payload: Mapping[str, Any],
) -> None:
    serialized_cutflow = _json_text(cutflow_payload)
    serialized_summary = _json_text(summary_payload)
    serialized_manifest = _json_text(manifest_payload)
    if config_source.read_bytes() != config_bytes:
        raise RuntimeError("config changed during preparation")
    if layout.run_dir is not None:
        if _path_entry_exists(layout.run_dir):
            raise FileExistsError(f"run directory already exists: {layout.run_dir}")
        try:
            layout.run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise FileExistsError(
                f"run directory already exists: {layout.run_dir}"
            ) from exc

    layout.processed_dir.mkdir(parents=True, exist_ok=True)
    layout.artifacts_dir.mkdir(parents=True, exist_ok=True)
    if layout.config_snapshot is not None:
        layout.config_snapshot.write_bytes(config_bytes)
    mc_frame.to_csv(layout.processed_dir / "mc_events.csv.gz", index=False)
    data_frame.to_csv(layout.processed_dir / "data_events.csv.gz", index=False)
    (layout.artifacts_dir / "cutflow.json").write_text(
        serialized_cutflow, encoding="utf-8"
    )
    (layout.artifacts_dir / "data_summary.json").write_text(
        serialized_summary, encoding="utf-8"
    )
    manifest_path = layout.artifacts_dir / "run_manifest.json"
    manifest_temp_path = manifest_path.with_name(f"{manifest_path.name}.tmp")
    manifest_temp_path.write_text(serialized_manifest, encoding="utf-8")
    manifest_temp_path.replace(manifest_path)


def resolve_read_policy(
    config: Mapping[str, Any], *, full_override: bool
) -> ReadPolicy:
    chunk_size = _positive_integer(
        config.get("chunk_size_events", 50_000), "chunk_size_events"
    )
    if full_override:
        return ReadPolicy("full", None, chunk_size)

    entry_stop = config.get("entry_stop")
    if entry_stop is None:
        return ReadPolicy("full", None, chunk_size)
    try:
        validated_stop = _positive_integer(entry_stop, "entry_stop")
    except ValueError as exc:
        raise ValueError("entry_stop must be null or a positive integer") from exc
    return ReadPolicy("head", validated_stop, chunk_size)
