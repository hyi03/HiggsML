from __future__ import annotations

from src.cli import preprocess, train


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
        "develop",
        "--input-run", "runs/input",
        "--protocol", "protocol.yaml",
        "--run-dir", "runs/output",
    ]
    assert train.main(required) == 0
    assert train.main([*required, "--no-progress"]) == 0

    assert [call["show_progress"] for call in calls] == [True, False]
