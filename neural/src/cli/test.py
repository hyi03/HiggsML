from __future__ import annotations

import argparse
from collections.abc import Sequence
import logging
from pathlib import Path

from src.artifacts.transaction import RunPathError
from src.config import (
    ExitCode,
    InputBindingError,
    TestOpeningFailure,
    TestOpeningRefused,
)
from src.logging_config import configure_logging
from src.training.test_opening import TestOpeningResult, execute_test_opening


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="higgsml-test",
        description="Evaluate an eligible frozen adversarial MLP on held-out MC.",
    )
    parser.add_argument("--train-run", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--authorization-reference",
        help="Optional public audit reference; when omitted, test opening is repeatable.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable test-opening stage progress.",
    )
    return parser


def format_test_results(result: TestOpeningResult) -> str:
    metrics = result.metrics
    rules = result.qualification_rules
    reasons = list(metrics["rejection_reasons"])
    completeness = metrics["prediction_completeness"]
    status_label = "PASS" if metrics["status"] == "test_reproduced" else "FAIL"
    auc_result = "FAIL" if "auc_below_minimum" in reasons else "PASS"

    lines = [
        "HiggsML held-out test results",
        f"Status          {status_label} ({metrics['status']})",
        f"Selected lambda {float(metrics['selected_lambda']):.6f}",
        (
            f"Test rows       {int(completeness['row_count']):,} "
            f"({int(completeness['unique_identities']):,} unique; "
            f"{'complete' if completeness['complete'] else 'incomplete'})"
        ),
        (
            f"Weighted AUC    {float(metrics['weighted_auc']):.6f}  "
            f"required >= {float(rules['auc_minimum']):.6f}  {auc_result}"
        ),
        "",
        "Working points",
        "Name    Threshold   Bkg target   Bkg actual   Signal eff.   KS         Result",
    ]
    for name in ("loose", "medium", "tight"):
        point = metrics["working_points"][name]
        point_failed = any(reason.startswith(f"{name}_") for reason in reasons)
        lines.append(
            f"{name:<7} "
            f"{float(point['threshold']):>9.6f}   "
            f"{float(point['target_background_efficiency']):>10.6f}   "
            f"{float(point['achieved_background_efficiency']):>10.6f}   "
            f"{float(point['signal_efficiency']):>11.6f}   "
            f"{float(point['ks']):>8.6f}   "
            f"{'FAIL' if point_failed else 'PASS'}"
        )
    lines.extend(
        [
            (
                f"Requirements: KS <= {float(rules['ks_maximum']):.6f}; "
                "signal efficiency > achieved background efficiency."
            ),
            f"Rejection reasons: {', '.join(reasons) if reasons else 'none'}",
            f"Metrics file: {result.run_dir / 'artifacts/test_metrics.json'}",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_logging()
    allowed_root = Path.cwd() / "runs"
    try:
        result = execute_test_opening(
            development_run=arguments.train_run,
            run_dir=arguments.run_dir,
            authorization_reference=arguments.authorization_reference,
            allowed_root=allowed_root,
            show_progress=not arguments.no_progress,
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
    except InputBindingError:
        LOGGER.error(
            "test-opening failed: stage=input_binding run_dir=%s",
            arguments.run_dir,
        )
        return int(ExitCode.INPUT_BINDING)
    except RunPathError as error:
        LOGGER.error("test-opening run transaction failed: %s", error)
        return int(ExitCode.TRANSACTION)
    except Exception:
        LOGGER.exception("unexpected test-opening failure")
        return int(ExitCode.INTERNAL_ERROR)
    print(format_test_results(result))
    return int(ExitCode.SUCCESS)


if __name__ == "__main__":
    raise SystemExit(main())
