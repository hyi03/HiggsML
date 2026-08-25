"""Run the sealed MC-only Angular5 enrichment."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import sys
from typing import Sequence

from src.angular5_enrichment import (
    enrich_angular5_mc,
    publish_angular5_manifest,
    record_angular5_failure,
    write_angular5_artifacts,
)
from src.angular5_enrichment_run import (
    claim_angular5_output,
    resolve_angular5_sources,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish the sealed MC-only Angular5 enrichment"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    sources = resolve_angular5_sources(
        project_root=project_root,
        config_path=Path(args.config),
    )
    layout = claim_angular5_output(
        sources=sources,
        project_root=project_root,
        working_directory=Path.cwd(),
        run_dir=Path(args.run_dir),
    )
    try:
        outcome = enrich_angular5_mc(sources)
        receipt = write_angular5_artifacts(
            layout,
            sources=sources,
            outcome=outcome,
        )
        publish_angular5_manifest(
            layout,
            sources=sources,
            receipt=receipt,
            software={
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
            },
        )
    except Exception as error:
        record_angular5_failure(layout, error)
        raise
    print(f"published {len(outcome.frame)} MC rows to {layout.run_dir}")


if __name__ == "__main__":
    main(sys.argv[1:])
