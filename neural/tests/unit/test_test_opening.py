from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import torch

from src.artifacts.manifest import canonical_json_bytes, sha256_file
from src.artifacts.transaction import RunPathError
from src.config import (
    ExitCode,
    InputBindingError,
    TestOpeningFailure as OpeningFailure,
    TestOpeningRefused as OpeningRefused,
)
from src.training.development import execute_development
from src.training import test_opening
from src.training.test_opening import _claim, _load_binding, execute_test_opening
from src.training import test_reader
from src.training.test_reader import read_test_rows_after_claim, validate_test_frame
from tests.development_fixtures import development_with_test_rows, write_synthetic_preprocess_run
from tests.integration.test_development_run import _install_fast_pipeline


PROJECT = Path(__file__).resolve().parents[2]
PROTOCOL = PROJECT / "config/adversarial_mlp_protocol_v1.yaml"
AUTHORIZATION = "synthetic-fixture-only"


@pytest.fixture
def eligible_development(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    allowed_root = tmp_path / "runs"
    preprocess, full_frame = write_synthetic_preprocess_run(allowed_root)
    _install_fast_pipeline(monkeypatch, eligible_lambda=0.0)
    development = allowed_root / "eligible-development"
    result = execute_development(
        input_run=preprocess,
        protocol_path=PROTOCOL,
        run_dir=development,
        allowed_root=allowed_root,
    )
    assert result.status == "eligible"
    return allowed_root, development, preprocess, full_frame


def _force_frozen_thresholds(
    monkeypatch: pytest.MonkeyPatch, *, threshold: float = 0.5
) -> None:
    original = test_opening._load_binding

    def controlled_binding(*args, **kwargs):
        binding = original(*args, **kwargs)
        for point in binding.working_points.values():
            point["threshold"] = threshold
        return binding

    monkeypatch.setattr(test_opening, "_load_binding", controlled_binding)


def _force_classifier_logits(
    monkeypatch: pytest.MonkeyPatch, logits: list[float]
) -> None:
    def controlled_forward(_model, features: torch.Tensor) -> torch.Tensor:
        assert features.shape[0] == len(logits)
        return torch.tensor(logits, dtype=torch.float32)

    monkeypatch.setattr(
        "src.training.network.Classifier.forward",
        controlled_forward,
    )


def _tree_receipts(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in root.rglob("*")
        if path.is_file()
    }


def _rewrite_gzip_table(table: Path, mutate) -> None:
    lines = gzip.decompress(table.read_bytes()).splitlines(keepends=True)
    mutate(lines)
    table.write_bytes(gzip.compress(b"".join(lines), compresslevel=9, mtime=0))


def test_synthetic_opening_publishes_terminal_run_and_only_mutates_state(
    eligible_development,
) -> None:
    allowed_root, development, _, full_frame = eligible_development
    before = _tree_receipts(development)
    output = allowed_root / "test-opening"

    result = execute_test_opening(
        development_run=development,
        run_dir=output,
        authorization_reference=AUTHORIZATION,
        allowed_root=allowed_root,
    )

    assert result.status in {"test_reproduced", "test_nonreproduction"}
    assert set(path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()) == {
        "config.yaml",
        "artifacts/test_metrics.json",
        "artifacts/manifest.json",
        "predictions/test_scores.csv.gz",
        "plots/test_roc.png",
        "plots/test_mass_sculpting.png",
    }
    scores = pd.read_csv(output / "predictions/test_scores.csv.gz")
    assert len(scores) == int((full_frame["split"] == "test").sum())
    assert list(zip(scores["source_sample"], scores["source_entry"], strict=True)) == sorted(
        zip(scores["source_sample"], scores["source_entry"], strict=True),
        key=lambda item: (str(item[0]).encode("utf-8"), int(item[1])),
    )
    manifest_bytes = (output / "artifacts/manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    assert manifest_bytes == canonical_json_bytes(manifest)
    assert manifest["schema_version"] == "test-manifest-v1"
    assert manifest["run_type"] == "test_opening"
    assert manifest["counts"]["test_rows"] == len(scores)
    assert manifest["boundaries"] == {
        "authority_environment_verified": False,
        "educational_technical_demo": True,
        "held_out_test_opened": True,
        "open_test_run": True,
        "real_data_read": False,
    }
    assert manifest["performance"]["wall_seconds"] >= 0.0
    assert set(manifest["development"]["artifacts"]) == {
        "qualification_sha256",
        "working_points_sha256",
        "oof_scores_sha256",
        "model_sha256",
        "scaler_sha256",
    }
    score_record = next(
        record for record in manifest["outputs"]
        if record["path"] == "predictions/test_scores.csv.gz"
    )
    assert hashlib.sha256(gzip.decompress((output / score_record["path"]).read_bytes())).hexdigest() == score_record["canonical_content_sha256"]
    state = json.loads((development / "state/test_opening.json").read_bytes())
    assert state["status"] == result.status
    assert state["terminal_receipt"] is True
    assert state["test_features_opened"] is True
    assert state["claimed_at_utc"].endswith("Z")
    assert state["output_staging"].endswith(".tmp")
    after = _tree_receipts(development)
    assert {key: value for key, value in after.items() if key != "state/test_opening.json"} == before

    second_output = allowed_root / "second-opening"
    with pytest.raises(OpeningRefused):
        execute_test_opening(
            development_run=development,
            run_dir=second_output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )
    assert not second_output.exists()


def test_blank_authorization_refuses_before_claim(
    eligible_development,
) -> None:
    allowed_root, development, _, _ = eligible_development
    blank_output = allowed_root / "blank"
    with pytest.raises(OpeningRefused):
        execute_test_opening(
            development_run=development,
            run_dir=blank_output,
            authorization_reference="  ",
            allowed_root=allowed_root,
        )
    assert not blank_output.exists()
    assert not (development / "state").exists()


def test_development_artifact_tamper_refuses_before_claim(
    eligible_development,
) -> None:
    allowed_root, development, _, _ = eligible_development
    model = development / "model/model.pt"
    model.write_bytes(model.read_bytes() + b"tamper")
    tamper_output = allowed_root / "tamper"
    with pytest.raises(InputBindingError):
        execute_test_opening(
            development_run=development,
            run_dir=tamper_output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )
    assert not tamper_output.exists()
    assert not (development / "state").exists()


def test_adjusted_manifest_cannot_hide_scaler_binding_drift(
    eligible_development,
) -> None:
    allowed_root, development, _, _ = eligible_development
    scaler_path = development / "model/scaler.json"
    scaler = json.loads(scaler_path.read_bytes())
    scaler["fitting_rows"] += 1
    scaler_path.write_bytes(canonical_json_bytes(scaler))
    manifest_path = development / "artifacts/manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    record = next(
        item for item in manifest["outputs"] if item["path"] == "model/scaler.json"
    )
    record["sha256"] = sha256_file(scaler_path)
    record["size_bytes"] = scaler_path.stat().st_size
    manifest_path.write_bytes(canonical_json_bytes(manifest))

    output = allowed_root / "scaler-drift"
    with pytest.raises(InputBindingError):
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )
    assert not output.exists()
    assert not (development / "state").exists()


def test_preprocess_table_drift_refuses_before_claim(eligible_development) -> None:
    allowed_root, development, preprocess, _ = eligible_development
    table = preprocess / "processed/mc_events.csv.gz"
    table.write_bytes(table.read_bytes() + b"tamper")
    output = allowed_root / "preprocess-drift"

    with pytest.raises(InputBindingError):
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )
    assert not output.exists()
    assert not (development / "state").exists()


def test_missing_required_model_refuses_before_claim(eligible_development) -> None:
    allowed_root, development, _, _ = eligible_development
    (development / "model/model.pt").unlink()
    output = allowed_root / "missing-model"
    with pytest.raises(InputBindingError):
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )
    assert not output.exists()
    assert not (development / "state").exists()


def test_no_eligible_development_is_refused_without_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root = tmp_path / "runs"
    preprocess, _ = write_synthetic_preprocess_run(allowed_root)
    _install_fast_pipeline(monkeypatch, eligible_lambda=None)
    development = allowed_root / "no-eligible-development"
    result = execute_development(
        input_run=preprocess,
        protocol_path=PROTOCOL,
        run_dir=development,
        allowed_root=allowed_root,
    )
    assert result.status == "no_eligible_candidate"

    output = allowed_root / "refused-test-opening"
    with pytest.raises(OpeningRefused):
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )
    assert not output.exists()
    assert not (development / "state").exists()


@pytest.mark.parametrize(
    "reference",
    [
        "token=abc",
        "api_key:abc",
        "password=abc",
        "line-one\nline-two",
        "audit-" + "x" * 251,
        "audit-\u202e123",
        "audit-\u0085123",
    ],
)
def test_sensitive_authorization_reference_is_refused_before_output(
    eligible_development, reference: str
) -> None:
    allowed_root, development, _, _ = eligible_development
    output = allowed_root / "sensitive-authorization"
    with pytest.raises(OpeningRefused):
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=reference,
            allowed_root=allowed_root,
        )
    assert not output.exists()
    assert not (development / "state").exists()


def test_adjusted_manifest_cannot_hide_working_point_schema_drift(
    eligible_development,
) -> None:
    allowed_root, development, _, _ = eligible_development
    points_path = development / "artifacts/working_points.json"
    points = json.loads(points_path.read_bytes())
    points["candidates"][0]["working_points"]["loose"]["unexpected"] = 1.0
    points_path.write_bytes(canonical_json_bytes(points))
    manifest_path = development / "artifacts/manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    record = next(
        item for item in manifest["outputs"]
        if item["path"] == "artifacts/working_points.json"
    )
    record["sha256"] = sha256_file(points_path)
    record["size_bytes"] = points_path.stat().st_size
    manifest_path.write_bytes(canonical_json_bytes(manifest))

    output = allowed_root / "schema-drift"
    with pytest.raises(InputBindingError):
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )
    assert not output.exists()
    assert not (development / "state").exists()


def test_output_path_escape_and_existing_output_refuse_before_claim(
    eligible_development, tmp_path: Path
) -> None:
    allowed_root, development, _, _ = eligible_development
    with pytest.raises(RunPathError):
        execute_test_opening(
            development_run=development,
            run_dir=tmp_path / "outside",
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )
    existing = allowed_root / "existing"
    existing.mkdir()
    with pytest.raises(RunPathError):
        execute_test_opening(
            development_run=development,
            run_dir=existing,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )
    assert not (development / "state").exists()

@pytest.mark.parametrize("payload", [b"", b"{", b'{"status":"claimed"}\n'])
def test_any_existing_state_permanently_refuses_and_aborts_staging(
    eligible_development, payload: bytes
) -> None:
    allowed_root, development, _, _ = eligible_development
    state = development / "state/test_opening.json"
    state.parent.mkdir()
    state.write_bytes(payload)
    output = allowed_root / f"existing-state-{len(payload)}"

    with pytest.raises(OpeningRefused):
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )

    assert not output.exists()
    assert not list(allowed_root.glob(f".{output.name}.*.tmp"))


def test_atomic_claim_allows_exactly_one_concurrent_winner(eligible_development) -> None:
    allowed_root, development, _, _ = eligible_development
    binding = _load_binding(development, allowed_root=allowed_root)
    staging = [allowed_root / ".one.tmp", allowed_root / ".two.tmp"]
    for path in staging:
        path.mkdir()

    def claim(index: int) -> str:
        try:
            _claim(
                binding,
                output_run=allowed_root / f"test-{index}",
                authorization=AUTHORIZATION,
                staging=staging[index],
                claimed_at_utc="2026-09-02T00:00:00Z",
            )
        except OpeningRefused:
            return "refused"
        return "claimed"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(claim, (0, 1)))

    assert sorted(outcomes) == ["claimed", "refused"]
    claim_payload = json.loads((development / "state/test_opening.json").read_bytes())
    assert claim_payload["status"] == "claimed"
    assert claim_payload["terminal_receipt"] is False
    refused_output = allowed_root / "after-simulated-crash"
    with pytest.raises(OpeningRefused):
        execute_test_opening(
            development_run=development,
            run_dir=refused_output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )
    assert not refused_output.exists()


def test_preclaim_failure_never_overwrites_concurrent_winner_state(
    eligible_development, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root, development, _, _ = eligible_development
    state = development / "state/test_opening.json"
    winner = canonical_json_bytes({"owner": "concurrent-winner"})
    original_flush = test_opening._flush_directory

    def fail_after_winner_claim(path: Path) -> None:
        if path == development:
            state.write_bytes(winner)
            raise OSError("simulated pre-O_EXCL durability race")
        original_flush(path)

    monkeypatch.setattr(test_opening, "_flush_directory", fail_after_winner_claim)
    output = allowed_root / "losing-preclaim-race"
    with pytest.raises(OpeningRefused):
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )

    assert state.read_bytes() == winner
    assert not output.exists()
    assert not list(allowed_root.glob(f".{output.name}.*.tmp"))


def test_preclaim_directory_durability_failure_is_exit_four_without_receipt(
    eligible_development, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root, development, _, _ = eligible_development
    original_flush = test_opening._flush_directory

    def fail_parent_flush(path: Path) -> None:
        if path == development:
            raise OSError("simulated parent directory flush failure")
        original_flush(path)

    monkeypatch.setattr(test_opening, "_flush_directory", fail_parent_flush)
    output = allowed_root / "preclaim-durability"
    with pytest.raises(RunPathError) as raised:
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )

    assert raised.value.exit_code == int(ExitCode.TRANSACTION)
    assert not (development / "state/test_opening.json").exists()
    assert not output.exists()


@pytest.mark.parametrize(
    ("error", "expected_code", "expected_stage"),
    [
        (InputBindingError("poison-test-value-123"), ExitCode.INPUT_BINDING, "test_frame_binding"),
        (RuntimeError("poison-test-value-123"), ExitCode.INTERNAL_ERROR, "model_scoring"),
    ],
)
def test_post_claim_failures_publish_only_sanitized_receipts(
    eligible_development,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_code: ExitCode,
    expected_stage: str,
) -> None:
    allowed_root, development, _, _ = eligible_development
    output = allowed_root / f"post-claim-{int(expected_code)}"
    monkeypatch.setattr("src.training.test_opening._evaluate", lambda binding: (_ for _ in ()).throw(error))

    with pytest.raises(OpeningFailure) as raised:
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )

    assert raised.value.exit_code == expected_code
    failure = (output / "failure.json").read_text(encoding="utf-8")
    state = (development / "state/test_opening.json").read_text(encoding="utf-8")
    assert "poison-test-value-123" not in failure
    assert "poison-test-value-123" not in state
    receipt = json.loads(state)
    assert receipt["status"] == "failed_after_claim"
    assert receipt["failed_stage"] == expected_stage
    assert receipt["exit_code"] == int(expected_code)
    assert receipt["test_features_opened"] is True


def test_invalid_classifier_score_is_model_scoring_exit_seventy(
    eligible_development, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root, development, _, full_frame = eligible_development
    rows = int((full_frame["split"] == "test").sum())
    _force_classifier_logits(monkeypatch, [float("nan")] * rows)
    output = allowed_root / "invalid-model-score"

    with pytest.raises(OpeningFailure) as raised:
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )

    assert raised.value.stage == "model_scoring"
    assert raised.value.exit_code == ExitCode.INTERNAL_ERROR
    state = json.loads((development / "state/test_opening.json").read_bytes())
    assert state["failed_stage"] == "model_scoring"
    assert state["exit_code"] == int(ExitCode.INTERNAL_ERROR)
    assert state["test_features_opened"] is True
    assert state["terminal_receipt"] is True
    assert (output / "failure.json").is_file()


def test_output_publish_failure_records_exit_four_without_raw_message(
    eligible_development, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root, development, _, _ = eligible_development
    output = allowed_root / "publish-failure"

    def fail_publish(transaction) -> None:
        from src.artifacts.transaction import RunPathError

        raise RunPathError("poison-output-path-value")

    monkeypatch.setattr("src.artifacts.transaction.RunTransaction._publish", fail_publish)
    with pytest.raises(OpeningFailure) as raised:
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )

    assert raised.value.exit_code == ExitCode.TRANSACTION
    state = json.loads((development / "state/test_opening.json").read_bytes())
    assert state["failed_stage"] == "output_transaction"
    assert state["exit_code"] == int(ExitCode.TRANSACTION)
    assert state["output_failure_run_published"] is False
    failed_staging = list(allowed_root.glob(".publish-failure.*.failed"))
    assert len(failed_staging) == 1
    failure = (failed_staging[0] / "failure.json").read_text(encoding="utf-8")
    assert "poison-output-path-value" not in failure
    assert json.loads(failure)["stage"] == "output_transaction"


def test_opening_never_calls_training_fit_or_selection_paths(
    eligible_development, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root, development, _, _ = eligible_development
    forbidden = (
        "src.training.dataset.FoldLocalScaler.fit",
        "src.training.trainer.train_fold",
        "src.training.trainer.train_fixed_epochs",
        "src.training.qualification.working_point_metrics",
        "src.training.qualification.select_candidate",
    )

    def fail(*args, **kwargs):
        pytest.fail("test-opening called a forbidden fitting or selection path")

    for target in forbidden:
        monkeypatch.setattr(target, fail)
    assert not hasattr(test_opening, "train_fold")
    assert not hasattr(test_opening, "train_fixed_epochs")
    assert not hasattr(test_opening, "working_point_metrics")
    assert not hasattr(test_opening, "select_candidate")
    execute_test_opening(
        development_run=development,
        run_dir=allowed_root / "no-training",
        authorization_reference=AUTHORIZATION,
        allowed_root=allowed_root,
    )


def test_claim_and_terminal_receipt_flush_directories_durably(
    eligible_development, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root, development, _, _ = eligible_development
    original = test_opening._flush_directory
    flushed: list[Path] = []

    def spy(path: Path) -> None:
        flushed.append(path)
        original(path)

    monkeypatch.setattr(test_opening, "_flush_directory", spy)
    execute_test_opening(
        development_run=development,
        run_dir=allowed_root / "durable",
        authorization_reference=AUTHORIZATION,
        allowed_root=allowed_root,
    )

    assert flushed[0] == development
    assert flushed[1:] == [development / "state", development / "state"]


def test_claim_durability_failure_is_terminal_without_test_decode(
    eligible_development, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root, development, _, _ = eligible_development
    output = allowed_root / "claim-durability-failure"
    original = test_opening._flush_directory
    state_flushes = 0

    def fail_first_state_flush(path: Path) -> None:
        nonlocal state_flushes
        if path == development / "state":
            state_flushes += 1
            if state_flushes == 1:
                raise OSError("synthetic durability failure")
        original(path)

    monkeypatch.setattr(test_opening, "_flush_directory", fail_first_state_flush)
    monkeypatch.setattr(
        test_opening,
        "_evaluate",
        lambda binding: pytest.fail("test rows must not be decoded before a durable claim"),
    )

    with pytest.raises(OpeningFailure) as raised:
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )

    assert raised.value.exit_code == ExitCode.TRANSACTION
    assert (output / "failure.json").is_file()
    state = json.loads((development / "state/test_opening.json").read_bytes())
    assert state["status"] == "failed_after_claim"
    assert state["failed_stage"] == "claim_durability"
    assert state["test_features_opened"] is False


def test_terminal_receipt_failure_preserves_published_run_and_claim(
    eligible_development, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root, development, _, _ = eligible_development
    output = allowed_root / "terminal-receipt-failure"
    monkeypatch.setattr(
        test_opening,
        "_replace_state",
        lambda path, value: (_ for _ in ()).throw(OSError("receipt flush failed")),
    )

    with pytest.raises(OpeningFailure) as raised:
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )

    assert raised.value.exit_code == ExitCode.TRANSACTION
    assert raised.value.stage == "terminal_receipt"
    assert (output / "artifacts/manifest.json").is_file()
    state = json.loads((development / "state/test_opening.json").read_bytes())
    assert state["status"] == "claimed"
    assert state["terminal_receipt"] is False
    with pytest.raises(OpeningRefused):
        execute_test_opening(
            development_run=development,
            run_dir=allowed_root / "retry-after-terminal-failure",
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )


def test_post_publish_manifest_hash_failure_is_terminal_receipt_exit_four(
    eligible_development, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root, development, _, _ = eligible_development
    output = allowed_root / "post-publish-manifest-read-failure"
    original_sha256 = test_opening.sha256_file

    def fail_published_manifest(path: Path) -> str:
        if Path(path) == output / "artifacts/manifest.json":
            raise OSError("simulated published manifest read failure")
        return original_sha256(path)

    monkeypatch.setattr(test_opening, "sha256_file", fail_published_manifest)
    with pytest.raises(OpeningFailure) as raised:
        execute_test_opening(
            development_run=development,
            run_dir=output,
            authorization_reference=AUTHORIZATION,
            allowed_root=allowed_root,
        )

    assert raised.value.stage == "terminal_receipt"
    assert raised.value.exit_code == ExitCode.TRANSACTION
    assert (output / "artifacts/manifest.json").is_file()
    state = json.loads((development / "state/test_opening.json").read_bytes())
    assert state["status"] == "failed_after_claim"
    assert state["failed_stage"] == "terminal_receipt"
    assert state["output_failure_run_published"] is True


def test_claim_fdopen_failure_releases_owned_descriptor(
    eligible_development, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root, development, _, _ = eligible_development
    binding = _load_binding(development, allowed_root=allowed_root)
    staging = allowed_root / ".fdopen-claim.tmp"
    staging.mkdir()
    monkeypatch.setattr(
        test_opening.os,
        "fdopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("fdopen failed")),
    )

    with pytest.raises(RunPathError) as raised:
        _claim(
            binding,
            output_run=allowed_root / "fdopen-claim",
            authorization=AUTHORIZATION,
            staging=staging,
            claimed_at_utc="2026-09-02T00:00:00Z",
        )

    assert raised.value.claim_created is True
    state = development / "state/test_opening.json"
    state.unlink()
    assert not state.exists()


def test_replace_state_fdopen_failure_releases_owned_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "test_opening.json"
    state.write_bytes(canonical_json_bytes({"status": "claimed"}))
    monkeypatch.setattr(
        test_opening.os,
        "fdopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("fdopen failed")),
    )

    with pytest.raises(OSError, match="fdopen failed"):
        test_opening._replace_state(state, {"status": "complete"})

    temporary = next(tmp_path.glob(".test_opening.json.*.tmp"))
    temporary.unlink()
    assert json.loads(state.read_bytes()) == {"status": "claimed"}


def test_controlled_empty_background_is_normal_nonreproduction(
    eligible_development, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root, development, _, full_frame = eligible_development
    rows = int((full_frame["split"] == "test").sum())
    _force_frozen_thresholds(monkeypatch)
    _force_classifier_logits(monkeypatch, [-100.0] * rows)
    output = allowed_root / "empty-background-nonreproduction"

    result = execute_test_opening(
        development_run=development,
        run_dir=output,
        authorization_reference=AUTHORIZATION,
        allowed_root=allowed_root,
    )

    assert result.status == "test_nonreproduction"
    metrics = json.loads((output / "artifacts/test_metrics.json").read_bytes())
    for name, point in metrics["working_points"].items():
        assert point["achieved_background_efficiency"] == 0.0
        assert point["ks"] == 1.0
        assert point["empty_selected_background"] is True
        assert f"{name}_empty_selected_background" in metrics["rejection_reasons"]
        assert f"{name}_ks_above_maximum" in metrics["rejection_reasons"]
    assert (output / "plots/test_roc.png").is_file()
    assert (output / "plots/test_mass_sculpting.png").is_file()


def test_controlled_valid_metrics_publish_reproduced_terminal_status(
    eligible_development, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root, development, _, _ = eligible_development
    _force_frozen_thresholds(monkeypatch)
    _force_classifier_logits(monkeypatch, [-10.0, -10.0, 10.0, 10.0, 10.0, 10.0])
    original_reader = test_opening.read_test_rows_after_claim

    def same_background_mass(*args, **kwargs):
        validated = original_reader(*args, **kwargs)
        frame = validated.frame.copy(deep=True)
        frame.loc[frame["label"] == 0, "m4l"] = 120.0
        validate_test_frame(frame, expected_rows=len(frame))
        return test_reader.ValidatedTest(frame)

    monkeypatch.setattr(
        test_opening,
        "read_test_rows_after_claim",
        same_background_mass,
    )
    output = allowed_root / "controlled-reproduced"
    result = execute_test_opening(
        development_run=development,
        run_dir=output,
        authorization_reference=AUTHORIZATION,
        allowed_root=allowed_root,
    )

    assert result.status == "test_reproduced"
    metrics = json.loads((output / "artifacts/test_metrics.json").read_bytes())
    assert metrics["rejection_reasons"] == []
    assert all(point["ks"] == 0.0 for point in metrics["working_points"].values())


@pytest.mark.parametrize(
    ("column", "dtype"),
    [("label", "int32"), ("lep1_pt", "float32")],
)
def test_test_frame_rejects_non_exact_numeric_dtype(column: str, dtype: str) -> None:
    frame = development_with_test_rows()
    frame = frame.loc[frame["split"] == "test"].copy(deep=True)
    frame[column] = frame[column].astype(dtype)

    with pytest.raises(InputBindingError, match="dtype|numeric"):
        validate_test_frame(frame, expected_rows=len(frame))


@pytest.mark.parametrize("weight_column", ["train_weight", "physical_weight"])
def test_test_frame_rejects_zero_total_class_weight(
    tmp_path: Path, weight_column: str
) -> None:
    allowed_root = tmp_path / "runs"
    _, frame = write_synthetic_preprocess_run(allowed_root)
    test_frame = frame.loc[frame["split"] == "test"].copy(deep=True)
    test_frame.loc[test_frame["label"] == 0, weight_column] = 0.0

    with pytest.raises(InputBindingError, match="class weight total"):
        validate_test_frame(test_frame, expected_rows=len(test_frame))


def test_test_reader_skips_poison_development_features_before_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root = tmp_path / "runs"
    preprocess, frame = write_synthetic_preprocess_run(allowed_root)
    table = preprocess / "processed/mc_events.csv.gz"

    def poison(lines: list[bytes]) -> None:
        tokens = lines[1].rstrip(b"\n").split(b",")
        tokens[0] = b"poison-development-feature"
        lines[1] = b",".join(tokens) + b"\n"

    _rewrite_gzip_table(table, poison)
    original = test_reader._decode_test_rows
    payloads: list[bytes] = []

    def spy(payload: bytes):
        payloads.append(payload)
        assert b"poison-development-feature" not in payload
        return original(payload)

    monkeypatch.setattr(test_reader, "_decode_test_rows", spy)
    result = read_test_rows_after_claim(
        table,
        expected_rows=int((frame["split"] == "test").sum()),
    )
    assert len(result.frame) == 6
    assert len(payloads) == 1


def test_unknown_split_fails_before_full_row_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root = tmp_path / "runs"
    preprocess, frame = write_synthetic_preprocess_run(allowed_root)
    table = preprocess / "processed/mc_events.csv.gz"

    def poison(lines: list[bytes]) -> None:
        tokens = lines[1].rstrip(b"\n").split(b",")
        tokens[0] = b"poison-must-not-be-decoded"
        tokens[21] = b"unknown"
        lines[1] = b",".join(tokens) + b"\n"

    _rewrite_gzip_table(table, poison)
    monkeypatch.setattr(
        test_reader,
        "_decode_test_rows",
        lambda payload: pytest.fail("full row decoder must not run"),
    )
    with pytest.raises(InputBindingError, match="split token"):
        read_test_rows_after_claim(
            table,
            expected_rows=int((frame["split"] == "test").sum()),
        )
