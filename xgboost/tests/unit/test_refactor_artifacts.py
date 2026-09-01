from __future__ import annotations

import json
from pathlib import Path
import threading

import pytest

from src.artifacts.manifest import canonical_json_bytes, sha256_file
from src.artifacts.transaction import RunTransaction


def test_transaction_claims_fresh_run_and_publishes_manifest_last(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    target = runs / "run-1"
    with RunTransaction(target, runs_root=runs) as transaction:
        transaction.write_bytes("artifacts/value.json", canonical_json_bytes({"value": 1}))
        transaction.publish_manifest({"schema_version": "1.0", "status": "complete"})
    assert json.loads((target / "manifest.json").read_text(encoding="utf-8"))["status"] == "complete"
    assert sha256_file(target / "artifacts/value.json")
    with pytest.raises(FileExistsError):
        with RunTransaction(target, runs_root=runs):
            pass


def test_transaction_records_failure_without_success_manifest(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    target = runs / "failed"
    with pytest.raises(RuntimeError, match="boom"):
        with RunTransaction(target, runs_root=runs):
            raise RuntimeError("boom")
    assert (target / "failure.json").is_file()
    assert not (target / "manifest.json").exists()


@pytest.mark.parametrize(
    "relative", ["../escape", "manifest.json", "/absolute", "C:drive-relative"]
)
def test_transaction_rejects_unsafe_or_reserved_outputs(tmp_path: Path, relative: str) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    with RunTransaction(runs / "new", runs_root=runs) as transaction:
        with pytest.raises(ValueError):
            transaction.write_bytes(relative, b"x")


def test_manifest_is_terminal_and_success_failure_receipts_are_exclusive(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    target = runs / "complete"
    with pytest.raises(RuntimeError, match="after publication"):
        with RunTransaction(target, runs_root=runs) as transaction:
            transaction.publish_manifest({"schema_version": "1.0", "status": "complete"})
            transaction.write_bytes("late.bin", b"late")
    assert (target / "manifest.json").is_file()
    assert not (target / "failure.json").exists()
    assert not (target / "late.bin").exists()


def test_concurrent_claim_has_exactly_one_winner(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    target = runs / "race"
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def claim() -> None:
        barrier.wait()
        try:
            with RunTransaction(target, runs_root=runs) as transaction:
                transaction.publish_manifest({"schema_version": "1.0", "status": "complete"})
            outcomes.append("won")
        except FileExistsError:
            outcomes.append("lost")

    threads = [threading.Thread(target=claim) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["lost", "won"]
    assert (target / "manifest.json").is_file()
    assert not (target / "failure.json").exists()


def test_intermediate_symlink_is_rejected_when_platform_allows_it(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    with RunTransaction(runs / "symlink", runs_root=runs) as transaction:
        link = transaction.run_dir / "artifacts"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            pytest.skip(f"native symlink unavailable on this Windows host: {error}")
        with pytest.raises(ValueError, match="symlink|inside"):
            transaction.write_bytes("artifacts/escape.bin", b"x")
    assert not (outside / "escape.bin").exists()


def test_intermediate_symlink_rejection_branch_is_covered_without_privilege(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    target = runs / "fake-symlink"
    original = Path.is_symlink
    simulated = target / "artifacts"

    def fake_is_symlink(path: Path) -> bool:
        return path == simulated or original(path)

    with RunTransaction(target, runs_root=runs) as transaction:
        monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)
        with pytest.raises(ValueError, match="symlink"):
            transaction.write_bytes("artifacts/value.bin", b"x")
