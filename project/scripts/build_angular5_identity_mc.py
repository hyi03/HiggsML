"""Build and publish a sealed Angular5 source-identity baseline."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import sys
from typing import Sequence

from src.angular5_identity_run import (
    build_identity_mc,
    claim_identity_output,
    publish_identity_manifest,
    record_identity_failure,
    resolve_identity_sources,
    write_identity_artifacts,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish the sealed MC-only Angular5 source identities"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    sources = resolve_identity_sources(
        project_root=project_root, config_path=Path(args.config)
    )
    layout = claim_identity_output(
        sources=sources,
        project_root=project_root,
        working_directory=Path.cwd(),
        run_dir=Path(args.run_dir),
    )
    try:
        outcome = build_identity_mc(sources)
        receipt = write_identity_artifacts(layout, sources=sources, outcome=outcome)
        publish_identity_manifest(
            layout,
            sources=sources,
            receipt=receipt,
            software={
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
            },
        )
    except BaseException as error:
        record_identity_failure(layout, error)
        raise
    print(f"published {len(outcome.frame)} MC source identities to {layout.run_dir}")


if __name__ == "__main__":
    main(sys.argv[1:])
