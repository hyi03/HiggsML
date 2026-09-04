from __future__ import annotations

import argparse
import logging
from pathlib import Path
from collections.abc import Sequence

from src.artifacts.transaction import RunPathError
from src.config import ExitCode, InputBindingError
from src.logging_config import configure_logging
from src.training.development import execute_development


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="higgsml-train",
        description="Run sealed development-only adversarial MLP qualification.",
    )
    parser.add_argument("--input-run", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable epoch progress bars.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_logging()
    allowed_root = Path.cwd() / "runs"
    try:
        execute_development(
            input_run=arguments.input_run,
            protocol_path=arguments.protocol,
            run_dir=arguments.run_dir,
            allowed_root=allowed_root,
            show_progress=not arguments.no_progress,
        )
    except InputBindingError as error:
        LOGGER.error("development input binding failed: %s", error)
        return int(ExitCode.INPUT_BINDING)
    except RunPathError as error:
        LOGGER.error("development run transaction failed: %s", error)
        return int(ExitCode.TRANSACTION)
    except Exception:
        LOGGER.exception("unexpected development failure")
        return int(ExitCode.INTERNAL_ERROR)
    return int(ExitCode.SUCCESS)


if __name__ == "__main__":
    raise SystemExit(main())
