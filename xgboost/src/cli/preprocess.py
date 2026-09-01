from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import NoReturn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="higgsml-preprocess",
        description="Prepare immutable Angular19 Higgs/ZZ MC datasets",
    )
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--run-config", required=True)
    parser.add_argument("--run-dir", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> NoReturn:
    build_parser().parse_args(argv)
    raise SystemExit("preprocessing implementation is delivered by Sprint M1-02")


if __name__ == "__main__":
    raise SystemExit(main())
