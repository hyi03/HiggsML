from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.artifacts.transaction import RunPathError, RunTransaction


def test_transaction_publishes_atomically(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    target = root / "run-001"

    with RunTransaction(target, allowed_root=root) as transaction:
        assert transaction.path != target
        (transaction.path / "result.txt").write_text("ok", encoding="utf-8")

    assert target.joinpath("result.txt").read_text(encoding="utf-8") == "ok"
    assert not transaction.path.exists()


def test_transaction_rejects_existing_target(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    target = root / "run-001"
    target.mkdir(parents=True)

    with pytest.raises(RunPathError, match="already exists"):
        RunTransaction(target, allowed_root=root)


def test_transaction_rejects_path_outside_allowed_root(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    outside = tmp_path / "elsewhere" / "run-001"

    with pytest.raises(RunPathError, match="outside allowed root"):
        RunTransaction(outside, allowed_root=root)


def test_failed_transaction_publishes_failure_receipt(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    target = root / "run-failed"

    with pytest.raises(ValueError, match="bad input"):
        with RunTransaction(target, allowed_root=root):
            raise ValueError("bad input")

    receipt = json.loads(target.joinpath("failure.json").read_text(encoding="utf-8"))
    assert receipt["error_type"] == "ValueError"
    assert receipt["message"] == "bad input"
    assert receipt["status"] == "failed"
    assert receipt["exit_code"] == 70
    assert receipt["failed_at_utc"].endswith("+00:00")


def test_transaction_supports_nested_target(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    target = root / "campaign" / "run-001"

    with RunTransaction(target, allowed_root=root) as transaction:
        (transaction.path / "result.txt").write_text("ok", encoding="utf-8")

    assert target.joinpath("result.txt").read_text(encoding="utf-8") == "ok"


def test_transaction_rejects_allowed_root_as_target(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    with pytest.raises(RunPathError, match="outside allowed root"):
        RunTransaction(root, allowed_root=root)


def test_abort_removes_staging_and_prevents_publish(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    target = root / "run-aborted"
    transaction = RunTransaction(target, allowed_root=root)
    staging = transaction.path

    transaction.abort_without_receipt()

    assert not staging.exists()
    assert not target.exists()
    with pytest.raises(RuntimeError, match="already finished"):
        transaction._publish()


def test_double_publish_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    target = root / "run-published"
    transaction = RunTransaction(target, allowed_root=root)
    transaction._publish()

    with pytest.raises(RuntimeError, match="already finished"):
        transaction._publish()
