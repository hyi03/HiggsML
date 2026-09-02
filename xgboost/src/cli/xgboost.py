from __future__ import annotations

import argparse
from collections.abc import Sequence
import sys

from ..training.trainer import run_development


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="higgsml-xgboost",
        description="Develop or open the held-out test for a frozen XGBoost model",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    develop = commands.add_parser("develop")
    develop.add_argument("--input-run", required=True)
    develop.add_argument("--protocol", required=True)
    develop.add_argument("--run-dir", required=True)
    open_test = commands.add_parser("open-test")
    open_test.add_argument("--development-run", required=True)
    open_test.add_argument("--run-dir", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "develop":
        try:
            manifest = run_development(
                input_run=args.input_run,
                protocol_path=args.protocol,
                run_dir=args.run_dir,
                show_progress=True,
            )
        except Exception as exc:
            print(
                f"higgsml-xgboost failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 1
        print(manifest["status"])
        return 0
    raise SystemExit("open-test implementation is delivered by Sprint M1-04")


if __name__ == "__main__":
    raise SystemExit(main())
