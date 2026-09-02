from __future__ import annotations

import argparse
from collections.abc import Sequence
import sys

from ..preprocessing.application import run_preprocessing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="higgsml-preprocess",
        description="Prepare immutable Angular19 Higgs/ZZ MC datasets",
    )
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--run-config", required=True)
    parser.add_argument("--run-dir", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = run_preprocessing(
            protocol_path=args.protocol,
            run_config_path=args.run_config,
            run_dir=args.run_dir,
        )
    except Exception as exc:
        print(
            f"higgsml-preprocess failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1
    print(
        "preprocessing complete: "
        f"{manifest['counts']['development']} development, "
        f"{manifest['counts']['test']} test events"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
