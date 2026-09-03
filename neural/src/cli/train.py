from __future__ import annotations

import argparse
import logging
from pathlib import Path
from collections.abc import Sequence

from src.artifacts.transaction import RunPathError
from src.config import (
    ExitCode,
    InputBindingError,
    TestOpeningFailure,
    TestOpeningRefused,
)
from src.logging_config import configure_logging
from src.training.development import execute_development
from src.training.test_opening import execute_test_opening


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="higgsml-train",
        description="Train or evaluate the frozen MC-only adversarial MLP workflow.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    develop = subcommands.add_parser(
        "develop", help="Run sealed development-only five-fold OOF qualification."
    )
    develop.add_argument("--input-run", required=True)
    develop.add_argument("--protocol", required=True)
    develop.add_argument("--run-dir", required=True)
    develop.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable epoch progress bars.",
    )
    open_test = subcommands.add_parser(
        "open-test",
        help="Open an eligible held-out MC test once after separate external authorization.",
    )
    open_test.add_argument("--development-run", required=True)
    open_test.add_argument("--run-dir", required=True)
    open_test.add_argument("--authorization-reference", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_logging()
    allowed_root = Path.cwd() / "runs"
    try:
        if arguments.command == "develop":
            execute_development(
                input_run=arguments.input_run,
                protocol_path=arguments.protocol,
                run_dir=arguments.run_dir,
                allowed_root=allowed_root,
                show_progress=not arguments.no_progress,
            )
        elif arguments.command == "open-test":
            execute_test_opening(
                development_run=arguments.development_run,
                run_dir=arguments.run_dir,
                authorization_reference=arguments.authorization_reference,
                allowed_root=allowed_root,
            )
    except TestOpeningRefused as error:
        LOGGER.error("test-opening refused: %s", error)
        return int(ExitCode.REFUSED)
    except TestOpeningFailure as error:
        if error.stage == "terminal_receipt":
            LOGGER.error(
                "test-opening failed: stage=%s run_dir=%s; "
                "output may be published; manual audit required",
                error.stage,
                arguments.run_dir,
            )
        else:
            LOGGER.error(
                "test-opening failed: stage=%s run_dir=%s",
                error.stage,
                arguments.run_dir,
            )
        return int(error.exit_code)
    except InputBindingError as error:
        if arguments.command == "open-test":
            LOGGER.error(
                "test-opening failed: stage=input_binding run_dir=%s",
                arguments.run_dir,
            )
        else:
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
