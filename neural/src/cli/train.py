from __future__ import annotations

import argparse
from collections.abc import Sequence

from src.config import ExitCode
from src.logging_config import configure_logging


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="higgsml-train",
        description="Train or evaluate the frozen MC-only adversarial MLP workflow.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    configure_logging()
    return int(ExitCode.SUCCESS)


if __name__ == "__main__":
    raise SystemExit(main())
