"""Publish the sealed R3-ARM64 MC-only Angular5 enrichment."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import sys
from typing import Sequence

from src.angular5_enrichment_r3_arm64 import (
    enrich_angular5_r3_arm64_mc,
    publish_angular5_r3_arm64_manifest,
    write_angular5_r3_arm64_artifacts,
)
from src.angular5_enrichment_r3_arm64_run import (
    claim_angular5_r3_arm64_output,
    resolve_angular5_r3_arm64_sources,
)
from src.angular5_enrichment import record_angular5_failure


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish sealed R3-ARM64 MC-only Angular5 observables")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    sources = resolve_angular5_r3_arm64_sources(project_root=root, config_path=Path(args.config))
    layout = claim_angular5_r3_arm64_output(sources=sources, project_root=root, working_directory=Path.cwd(), run_dir=Path(args.run_dir))
    try:
        outcome = enrich_angular5_r3_arm64_mc(sources)
        receipt = write_angular5_r3_arm64_artifacts(layout, sources=sources, outcome=outcome)
        publish_angular5_r3_arm64_manifest(layout, sources=sources, receipt=receipt, software={"python": platform.python_version(), "implementation": platform.python_implementation()})
    except BaseException as error:
        record_angular5_failure(layout, error)
        raise
    print(f"published {len(outcome.frame)} R3-ARM64 MC Angular5 rows to {layout.run_dir}")


if __name__ == "__main__":
    main(sys.argv[1:])
