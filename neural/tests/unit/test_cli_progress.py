from __future__ import annotations

from pathlib import Path

from src.cli import preprocess, test as test_cli, train
from src.training.test_opening import TestOpeningResult


def _test_result(*, reproduced: bool = True) -> TestOpeningResult:
    reasons = [] if reproduced else ["auc_below_minimum", "medium_ks_above_maximum"]
    points = {
        name: {
            "threshold": threshold,
            "target_background_efficiency": target,
            "achieved_background_efficiency": target + 0.001,
            "signal_efficiency": signal,
            "ks": 0.08 if name != "medium" or reproduced else 0.12,
            "empty_selected_background": False,
        }
        for name, threshold, target, signal in (
            ("loose", 0.7, 0.5, 0.8),
            ("medium", 0.8, 0.2, 0.6),
            ("tight", 0.9, 0.1, 0.4),
        )
    }
    status = "test_reproduced" if reproduced else "test_nonreproduction"
    return TestOpeningResult(
        status=status,
        run_dir=Path("runs/test"),
        metrics={
            "status": status,
            "selected_lambda": 0.1,
            "weighted_auc": 0.84 if reproduced else 0.79,
            "working_points": points,
            "prediction_completeness": {
                "complete": True,
                "row_count": 39709,
                "unique_identities": 39709,
            },
            "rejection_reasons": reasons,
        },
        qualification_rules={
            "auc_minimum": 0.8,
            "ks_maximum": 0.1,
            "signal_efficiency_strictly_greater_than_background": True,
        },
    )


def test_preprocess_progress_is_enabled_by_default_and_can_be_disabled(
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr(preprocess, "configure_logging", lambda: None)
    monkeypatch.setattr(preprocess, "execute_preprocess", lambda **kwargs: calls.append(kwargs))

    required = [
        "--protocol", "protocol.yaml",
        "--run-config", "run.yaml",
        "--run-dir", "runs/example",
    ]
    assert preprocess.main(required) == 0
    assert preprocess.main([*required, "--no-progress"]) == 0

    assert [call["show_progress"] for call in calls] == [True, False]


def test_train_progress_is_enabled_by_default_and_can_be_disabled(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(train, "configure_logging", lambda: None)
    monkeypatch.setattr(train, "execute_development", lambda **kwargs: calls.append(kwargs))

    required = [
        "--input-run", "runs/input",
        "--protocol", "protocol.yaml",
        "--run-dir", "runs/output",
    ]
    assert train.main(required) == 0
    assert train.main([*required, "--no-progress"]) == 0

    assert [call["show_progress"] for call in calls] == [True, False]


def test_test_progress_is_enabled_by_default_and_can_be_disabled(
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr(test_cli, "configure_logging", lambda: None)

    def execute(**kwargs):
        calls.append(kwargs)
        return _test_result()

    monkeypatch.setattr(test_cli, "execute_test_opening", execute)
    required = [
        "--train-run", "runs/development",
        "--run-dir", "runs/test",
    ]

    assert test_cli.main(required) == 0
    assert test_cli.main([*required, "--no-progress"]) == 0

    assert [call["show_progress"] for call in calls] == [True, False]


def test_test_result_formatter_quantifies_passes_and_failures() -> None:
    formatted = test_cli.format_test_results(_test_result(reproduced=False))

    assert "FAIL (test_nonreproduction)" in formatted
    assert "Weighted AUC    0.790000  required >= 0.800000  FAIL" in formatted
    assert "medium" in formatted and "0.120000   FAIL" in formatted
    assert "39,709 unique; complete" in formatted
    assert "auc_below_minimum, medium_ks_above_maximum" in formatted
    assert str(Path("runs/test/artifacts/test_metrics.json")) in formatted
