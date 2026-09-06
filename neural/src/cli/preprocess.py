from __future__ import annotations

import argparse
from src.data_contract import DATASET_NAMES
import logging
from collections.abc import Sequence
from pathlib import Path

from src.artifacts.transaction import RunPathError
from src.config import ExitCode, InputBindingError
from src.logging_config import configure_logging
from src.preprocessing.pipeline import execute_preprocess


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="higgsml-preprocess",
        description="Prepare SHA-256-bound MC inputs for the HiggsML neural workflow.",
    )
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--run-config", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable event progress bars.",
    )
    parser.add_argument("--dataset", choices=DATASET_NAMES, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_logging()
    LOGGER.info("dataset=%s", arguments.dataset)
    allowed_root = Path.cwd() / "runs"
    try:
        execute_preprocess(
            dataset=arguments.dataset,            protocol_path=arguments.protocol,
            run_config_path=arguments.run_config,
            run_dir=arguments.run_dir,
            allowed_root=allowed_root,
            show_progress=not arguments.no_progress,
        )
    except InputBindingError as error:
        LOGGER.error("preprocess input binding failed: %s", error)
        return int(ExitCode.INPUT_BINDING)
    except RunPathError as error:
        LOGGER.error("preprocess run transaction failed: %s", error)
        return int(ExitCode.TRANSACTION)
    except Exception:
        LOGGER.exception("unexpected preprocess failure")
        return int(ExitCode.INTERNAL_ERROR)
    return int(ExitCode.SUCCESS)


if __name__ == "__main__":
    raise SystemExit(main())
