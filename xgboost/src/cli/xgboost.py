from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import NoReturn


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


def main(argv: Sequence[str] | None = None) -> NoReturn:
    args = build_parser().parse_args(argv)
    sprint = "M1-03" if args.command == "develop" else "M1-04"
    raise SystemExit(f"{args.command} implementation is delivered by Sprint {sprint}")


if __name__ == "__main__":
    raise SystemExit(main())
