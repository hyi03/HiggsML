from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from src.preprocessing.pipeline import OUTPUT_COLUMNS
from src.training import test_opening
from src.training.test_opening import run_open_test
from src.training.trainer import run_development
from tests.refactor_training_support import (
    fake_factory,
    test_frame as synthetic_test_frame,
    write_eligible_development_run,
    write_preprocess_run,
)


PROJECT = Path(__file__).resolve().parents[2]


def _files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def _stub_model(monkeypatch) -> None:
    class Booster:
        def num_boosted_rounds(self) -> int:
            return 4

    class Model:
        def get_booster(self) -> Booster:
            return Booster()

    monkeypatch.setattr(test_opening, "_load_model", lambda path, features: Model())
    monkeypatch.setattr(
        test_opening,
        "positive_scores",
        lambda model, frame, features: np.linspace(0.01, 0.99, len(frame)),
    )
    monkeypatch.setattr(
        test_opening,
        "_plot_bytes",
        lambda frame: {
            "plots/roc_curve.png": b"roc",
            "plots/score_distribution.png": b"scores",
            "plots/score_vs_m4l.png": b"mass",
        },
    )


def _rewrite_test_input(
    input_run: Path,
    development: Path,
    frame: pd.DataFrame,
    *,
    rows: int | None = None,
    canonical_sha256: str | None = None,
) -> None:
    canonical = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    compressed = gzip.compress(canonical, compresslevel=9, mtime=0)
    (input_run / "processed/test.csv.gz").write_bytes(compressed)
    preprocess_manifest_path = input_run / "artifacts/manifest.json"
    preprocess_manifest = json.loads(preprocess_manifest_path.read_text(encoding="utf-8"))
    receipt = preprocess_manifest["outputs"]["test"]
    receipt.update(
        rows=len(frame) if rows is None else rows,
        columns=list(frame.columns),
        size_bytes=len(compressed),
        sha256_compressed=hashlib.sha256(compressed).hexdigest(),
        sha256_canonical_csv=(
            hashlib.sha256(canonical).hexdigest()
            if canonical_sha256 is None
            else canonical_sha256
        ),
    )
    expected_rows = len(frame) if rows is None else rows
    preprocess_manifest["counts"]["test"] = expected_rows
    preprocess_manifest["counts"]["total"] = (
        preprocess_manifest["counts"]["development"] + expected_rows
    )
    preprocess_manifest_path.write_text(
        json.dumps(preprocess_manifest, sort_keys=True), encoding="utf-8"
    )
    development_manifest_path = development / "artifacts/manifest.json"
    development_manifest = json.loads(
        development_manifest_path.read_text(encoding="utf-8")
    )
    development_manifest["upstream_run"]["manifest"]["sha256"] = hashlib.sha256(
        preprocess_manifest_path.read_bytes()
    ).hexdigest()
    development_manifest_path.write_text(
        json.dumps(development_manifest, sort_keys=True), encoding="utf-8"
    )


def test_open_test_claims_before_read_and_publishes_exact_contract(
    tmp_path: Path, monkeypatch
) -> None:
    input_run, development = write_eligible_development_run(tmp_path)
    _stub_model(monkeypatch)
    test_path = (input_run / "processed/test.csv.gz").absolute()
    output = tmp_path / "runs/test-evaluation"
    original = test_opening.read_regular_bytes
    observations: list[bool] = []

    def observe(path: str | Path, label: str) -> bytes:
        if Path(path).absolute() == test_path:
            observations.append((development / "state/test_opening.json").is_file())
        return original(path, label)

    monkeypatch.setattr(test_opening, "read_regular_bytes", observe)
    manifest = run_open_test(development_run=development, run_dir=output)

    assert observations == [True]
    assert manifest["status"] == "succeeded"
    assert _files(output) == {
        "artifacts/test_metrics.json",
        "artifacts/manifest.json",
        "predictions/test_scores.csv.gz",
        "plots/roc_curve.png",
        "plots/score_distribution.png",
        "plots/score_vs_m4l.png",
    }
    scores = pd.read_csv(output / "predictions/test_scores.csv.gz")
    assert tuple(scores.columns) == OUTPUT_COLUMNS + ("xgb_score",)
    metrics = json.loads((output / "artifacts/test_metrics.json").read_text())
    assert metrics["status"] == "complete"
    assert tuple(metrics["working_points"]) == ("loose", "medium", "tight")
    claim = json.loads(
        (development / "state/test_opening.json").read_text(encoding="utf-8")
    )
    assert claim["status"] == "claimed"
    assert claim["test_run_path"] == str(output.resolve(strict=True))
    assert json.loads(
        (development / "artifacts/manifest.json").read_text(encoding="utf-8")
    )["test_opened"] is False


def test_occupied_output_is_zero_read_and_zero_write(tmp_path: Path, monkeypatch) -> None:
    _, development = write_eligible_development_run(tmp_path)
    output = tmp_path / "runs/occupied"
    output.mkdir()
    marker = output / "owned.txt"
    marker.write_text("preserve", encoding="utf-8")

    def deny(*args, **kwargs):
        pytest.fail("occupied output attempted an input read")

    monkeypatch.setattr(test_opening, "read_regular_bytes", deny)
    with pytest.raises(FileExistsError):
        run_open_test(development_run=development, run_dir=output)
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert _files(output) == {"owned.txt"}


def test_claimed_failure_is_terminal_and_second_run_dir_cannot_reopen(
    tmp_path: Path, monkeypatch
) -> None:
    _, development = write_eligible_development_run(tmp_path)
    first = tmp_path / "runs/first"
    _stub_model(monkeypatch)

    def fail_score(*args, **kwargs):
        raise RuntimeError("synthetic scoring failure")

    monkeypatch.setattr(test_opening, "positive_scores", fail_score)
    with pytest.raises(RuntimeError, match="synthetic scoring failure"):
        run_open_test(development_run=development, run_dir=first)
    assert (development / "state/test_opening.json").is_file()
    assert (first / "failure.json").is_file()
    assert not (first / "artifacts/manifest.json").exists()

    second = tmp_path / "runs/second"
    with pytest.raises(FileExistsError, match="already been opened"):
        run_open_test(development_run=development, run_dir=second)
    assert (second / "failure.json").is_file()


def test_preclaim_qualification_tamper_writes_failure_without_consuming_claim(
    tmp_path: Path,
) -> None:
    _, development = write_eligible_development_run(tmp_path)
    qualification = development / "artifacts/qualification.json"
    payload = json.loads(qualification.read_text(encoding="utf-8"))
    payload["checks"]["weighted_oof_auc"] = False
    qualification.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "runs/rejected"

    with pytest.raises(ValueError, match="qualification"):
        run_open_test(development_run=development, run_dir=output)
    assert (output / "failure.json").is_file()
    assert not (development / "state/test_opening.json").exists()


def test_frozen_threshold_comes_only_from_development_working_points(
    tmp_path: Path, monkeypatch
) -> None:
    _, development = write_eligible_development_run(tmp_path)
    _stub_model(monkeypatch)
    expected = json.loads(
        (development / "artifacts/working_points.json").read_text(encoding="utf-8")
    )
    output = tmp_path / "runs/frozen-threshold"
    run_open_test(development_run=development, run_dir=output)
    metrics = json.loads((output / "artifacts/test_metrics.json").read_text())
    assert {
        name: point["threshold"] for name, point in metrics["working_points"].items()
    } == {name: point["threshold"] for name, point in expected.items()}


def test_ineligible_development_is_rejected_without_claim(tmp_path: Path) -> None:
    input_run = write_preprocess_run(tmp_path, valid_test=True)
    runs = tmp_path / "runs"
    runs.mkdir()
    development = runs / "ineligible"
    manifest = run_development(
        input_run=input_run,
        protocol_path=PROJECT / "config/xgboost_protocol_v1.yaml",
        run_dir=development,
        model_factory=fake_factory,
    )
    assert manifest["status"] == "no_eligible_candidate"

    output = runs / "rejected-ineligible"
    with pytest.raises(ValueError, match="eligible and unopened"):
        run_open_test(development_run=development, run_dir=output)
    assert (output / "failure.json").is_file()
    assert not (development / "state/test_opening.json").exists()


@pytest.mark.parametrize(
    "relative_path",
    [
        "config.yaml",
        "artifacts/working_points.json",
        "predictions/oof_scores.csv.gz",
        "model/model.json",
    ],
)
def test_upstream_artifact_tamper_is_rejected_before_claim(
    tmp_path: Path, relative_path: str
) -> None:
    _, development = write_eligible_development_run(tmp_path)
    target = development / relative_path
    target.write_bytes(target.read_bytes() + b"tamper")
    output = tmp_path / "runs/rejected-tamper"

    with pytest.raises((ValueError, RuntimeError)):
        run_open_test(development_run=development, run_dir=output)
    assert (output / "failure.json").is_file()
    assert not (development / "state/test_opening.json").exists()


def test_preprocessing_manifest_tamper_is_rejected_before_claim(tmp_path: Path) -> None:
    input_run, development = write_eligible_development_run(tmp_path)
    manifest = input_run / "artifacts/manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")
    output = tmp_path / "runs/rejected-preprocess"

    with pytest.raises(ValueError, match="manifest binding"):
        run_open_test(development_run=development, run_dir=output)
    assert not (development / "state/test_opening.json").exists()


def test_unknown_development_layout_is_rejected_before_claim(tmp_path: Path) -> None:
    _, development = write_eligible_development_run(tmp_path)
    (development / "unexpected.txt").write_text("unknown", encoding="utf-8")
    output = tmp_path / "runs/rejected-layout"

    with pytest.raises(ValueError, match="unknown or missing artifact"):
        run_open_test(development_run=development, run_dir=output)
    assert not (development / "state/test_opening.json").exists()


def test_missing_development_artifact_is_rejected_before_claim(tmp_path: Path) -> None:
    _, development = write_eligible_development_run(tmp_path)
    (development / "plots/oof_scores.png").unlink()

    with pytest.raises(FileNotFoundError):
        run_open_test(
            development_run=development,
            run_dir=tmp_path / "runs/rejected-missing",
        )
    assert not (development / "state/test_opening.json").exists()


def test_extra_empty_development_directory_is_rejected_before_claim(tmp_path: Path) -> None:
    _, development = write_eligible_development_run(tmp_path)
    (development / "unexpected-empty").mkdir()

    with pytest.raises(ValueError, match="unknown or missing artifact"):
        run_open_test(
            development_run=development,
            run_dir=tmp_path / "runs/rejected-empty-directory",
        )
    assert not (development / "state/test_opening.json").exists()


def test_development_and_test_must_be_distinct_siblings_under_same_runs_root(
    tmp_path: Path,
) -> None:
    _, development = write_eligible_development_run(tmp_path / "source")
    other_runs = tmp_path / "other/runs"
    other_runs.mkdir(parents=True)

    with pytest.raises(ValueError, match="same resolved runs root"):
        run_open_test(
            development_run=development,
            run_dir=other_runs / "test",
        )
    assert not (development / "state/test_opening.json").exists()


def test_non_hex_test_identity_is_rejected_before_claim_without_test_read(
    tmp_path: Path, monkeypatch
) -> None:
    input_run, development = write_eligible_development_run(tmp_path)
    preprocess_manifest_path = input_run / "artifacts/manifest.json"
    preprocess_manifest = json.loads(preprocess_manifest_path.read_text(encoding="utf-8"))
    preprocess_manifest["outputs"]["test"]["sha256_compressed"] = "g" * 64
    preprocess_manifest_path.write_text(
        json.dumps(preprocess_manifest, sort_keys=True), encoding="utf-8"
    )
    development_manifest_path = development / "artifacts/manifest.json"
    development_manifest = json.loads(development_manifest_path.read_text(encoding="utf-8"))
    development_manifest["upstream_run"]["manifest"]["sha256"] = hashlib.sha256(
        preprocess_manifest_path.read_bytes()
    ).hexdigest()
    development_manifest_path.write_text(
        json.dumps(development_manifest, sort_keys=True), encoding="utf-8"
    )
    test_path = (input_run / "processed/test.csv.gz").resolve()
    original = test_opening.read_regular_bytes

    def deny_test(path: str | Path, label: str) -> bytes:
        if Path(path).resolve() == test_path:
            pytest.fail("non-hex identity caused a held-out test read")
        return original(path, label)

    monkeypatch.setattr(test_opening, "read_regular_bytes", deny_test)
    with pytest.raises(ValueError, match="sha256_compressed"):
        run_open_test(
            development_run=development,
            run_dir=tmp_path / "runs/rejected-non-hex",
        )
    assert not (development / "state/test_opening.json").exists()


def test_candidate_receipt_rows_are_exact_validated_before_claim(tmp_path: Path) -> None:
    _, development = write_eligible_development_run(tmp_path)
    manifest_path = development / "artifacts/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outputs"]["candidate_metrics"]["rows"] += 1
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="candidate metrics receipt rows"):
        run_open_test(
            development_run=development,
            run_dir=tmp_path / "runs/rejected-candidate-receipt",
        )
    assert not (development / "state/test_opening.json").exists()


def test_final_parameters_are_recomputed_from_fold_receipt_before_claim(tmp_path: Path) -> None:
    _, development = write_eligible_development_run(tmp_path)
    manifest_path = development / "artifacts/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["final_parameters"]["n_estimators"] += 1
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="final parameters"):
        run_open_test(
            development_run=development,
            run_dir=tmp_path / "runs/rejected-final-parameters",
        )
    assert not (development / "state/test_opening.json").exists()


def test_loaded_model_rounds_match_recomputed_final_tree_count(
    tmp_path: Path, monkeypatch
) -> None:
    _, development = write_eligible_development_run(tmp_path)

    class Booster:
        def num_boosted_rounds(self) -> int:
            return 99

    class Model:
        def get_booster(self) -> Booster:
            return Booster()

    monkeypatch.setattr(test_opening, "_load_model", lambda path, features: Model())
    with pytest.raises(ValueError, match="boosted rounds"):
        run_open_test(
            development_run=development,
            run_dir=tmp_path / "runs/rejected-model-rounds",
        )
    assert not (development / "state/test_opening.json").exists()


def test_same_size_corrupt_test_fails_after_claim_and_consumes_opening(
    tmp_path: Path, monkeypatch
) -> None:
    input_run, development = write_eligible_development_run(tmp_path)
    _stub_model(monkeypatch)
    test_path = input_run / "processed/test.csv.gz"
    content = bytearray(test_path.read_bytes())
    content[-1] ^= 0x01
    test_path.write_bytes(content)
    output = tmp_path / "runs/corrupt-test"

    with pytest.raises(ValueError, match="compressed bytes"):
        run_open_test(development_run=development, run_dir=output)
    assert (development / "state/test_opening.json").is_file()
    assert (output / "failure.json").is_file()


def test_invalid_test_schema_fails_only_after_claim(tmp_path: Path, monkeypatch) -> None:
    input_run, development = write_eligible_development_run(tmp_path)
    _stub_model(monkeypatch)
    test_path = input_run / "processed/test.csv.gz"
    frame = pd.read_csv(test_path).drop(columns=[OUTPUT_COLUMNS[-1]])
    canonical = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    compressed = gzip.compress(canonical, compresslevel=9, mtime=0)
    test_path.write_bytes(compressed)

    preprocess_manifest_path = input_run / "artifacts/manifest.json"
    preprocess_manifest = json.loads(
        preprocess_manifest_path.read_text(encoding="utf-8")
    )
    receipt = preprocess_manifest["outputs"]["test"]
    receipt.update(
        rows=len(frame),
        size_bytes=len(compressed),
        sha256_compressed=hashlib.sha256(compressed).hexdigest(),
        sha256_canonical_csv=hashlib.sha256(canonical).hexdigest(),
    )
    preprocess_manifest_path.write_text(
        json.dumps(preprocess_manifest, sort_keys=True), encoding="utf-8"
    )
    development_manifest_path = development / "artifacts/manifest.json"
    development_manifest = json.loads(
        development_manifest_path.read_text(encoding="utf-8")
    )
    development_manifest["upstream_run"]["manifest"]["sha256"] = hashlib.sha256(
        preprocess_manifest_path.read_bytes()
    ).hexdigest()
    development_manifest_path.write_text(
        json.dumps(development_manifest, sort_keys=True), encoding="utf-8"
    )

    output = tmp_path / "runs/invalid-schema"
    with pytest.raises(ValueError, match="32-column schema"):
        run_open_test(development_run=development, run_dir=output)
    assert (development / "state/test_opening.json").is_file()
    assert (output / "failure.json").is_file()


@pytest.mark.parametrize("failure", ["split", "single_class", "zero_weight", "duplicate"])
def test_invalid_test_content_matrix_fails_after_claim(
    tmp_path: Path, monkeypatch, failure: str
) -> None:
    input_run, development = write_eligible_development_run(tmp_path)
    _stub_model(monkeypatch)
    frame = synthetic_test_frame()
    if failure == "split":
        frame.loc[0, "split"] = "development"
    elif failure == "single_class":
        frame = frame.loc[frame["label"] == 1].copy()
    elif failure == "zero_weight":
        frame.loc[frame["label"] == 0, "physical_weight"] = 0.0
    else:
        frame.loc[1, ["channelNumber", "eventNumber"]] = frame.loc[
            0, ["channelNumber", "eventNumber"]
        ].to_numpy()
    _rewrite_test_input(input_run, development, frame)

    output = tmp_path / f"runs/invalid-{failure}"
    with pytest.raises(ValueError):
        run_open_test(development_run=development, run_dir=output)
    assert (development / "state/test_opening.json").is_file()
    assert (output / "failure.json").is_file()


@pytest.mark.parametrize("failure", ["rows", "canonical_hash"])
def test_test_receipt_content_mismatch_fails_after_claim(
    tmp_path: Path, monkeypatch, failure: str
) -> None:
    input_run, development = write_eligible_development_run(tmp_path)
    _stub_model(monkeypatch)
    frame = synthetic_test_frame()
    _rewrite_test_input(
        input_run,
        development,
        frame,
        rows=(len(frame) + 1 if failure == "rows" else None),
        canonical_sha256=("0" * 64 if failure == "canonical_hash" else None),
    )

    output = tmp_path / f"runs/mismatched-{failure}"
    with pytest.raises(ValueError):
        run_open_test(development_run=development, run_dir=output)
    assert (development / "state/test_opening.json").is_file()
    assert (output / "failure.json").is_file()


def test_concurrent_distinct_test_runs_have_one_claim_winner(
    tmp_path: Path, monkeypatch
) -> None:
    _, development = write_eligible_development_run(tmp_path)
    outputs = [tmp_path / "runs/concurrent-a", tmp_path / "runs/concurrent-b"]
    _stub_model(monkeypatch)

    def attempt(output: Path) -> str:
        try:
            run_open_test(development_run=development, run_dir=output)
        except FileExistsError:
            return "lost"
        return "won"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, outputs))
    assert sorted(results) == ["lost", "won"]
    assert sum((path / "artifacts/manifest.json").is_file() for path in outputs) == 1
    assert sum((path / "failure.json").is_file() for path in outputs) == 1


def test_two_independent_processes_competing_for_claim_have_one_winner(
    tmp_path: Path,
) -> None:
    runs = tmp_path / "runs"
    development = runs / "development"
    outputs = [runs / "process-a", runs / "process-b"]
    development.mkdir(parents=True)
    for output in outputs:
        output.mkdir()
    barrier = tmp_path / "start"
    program = (
        "import pathlib, sys, time; "
        "from src.training.test_opening import _claim; "
        "barrier=pathlib.Path(sys.argv[3]); "
        "\nwhile not barrier.exists(): time.sleep(0.001)\n"
        "try:\n"
        " _claim(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), "
        "{'manifest_sha256':'a'*64,'test_receipt':{'path':'processed/test.csv.gz'}})\n"
        " print('won')\n"
        "except FileExistsError:\n"
        " print('lost')\n"
    )
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", program, str(development), str(output), str(barrier)],
            cwd=PROJECT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for output in outputs
    ]
    barrier.touch()
    results = [process.communicate(timeout=30) for process in processes]
    assert [process.returncode for process in processes] == [0, 0], results
    assert sorted(stdout.strip() for stdout, _ in results) == ["lost", "won"]


def test_test_fingerprint_change_before_manifest_is_terminal(
    tmp_path: Path, monkeypatch
) -> None:
    input_run, development = write_eligible_development_run(tmp_path)
    _stub_model(monkeypatch)
    test_path = input_run / "processed/test.csv.gz"
    original = test_opening._verify_sources_before_manifest

    def mutate_after_source_verification(evidence, claim_path, claim_bytes) -> None:
        original(evidence, claim_path, claim_bytes)
        info = test_path.stat()
        os.utime(test_path, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))

    monkeypatch.setattr(
        test_opening,
        "_verify_sources_before_manifest",
        mutate_after_source_verification,
    )
    output = tmp_path / "runs/fingerprint-change"
    with pytest.raises(RuntimeError, match="held-out test changed"):
        run_open_test(development_run=development, run_dir=output)
    assert (development / "state/test_opening.json").is_file()
    assert (output / "failure.json").is_file()
    assert not (output / "artifacts/manifest.json").exists()


def test_new_metrics_and_plots_match_legacy_test_authority(
    tmp_path: Path,
) -> None:
    from src import experiment_runner

    scored = synthetic_test_frame()
    scored["xgb_score"] = np.linspace(0.01, 0.99, len(scored))
    points = {
        "loose": {"threshold": 0.2},
        "medium": {"threshold": 0.5},
        "tight": {"threshold": 0.8},
    }
    assert test_opening._test_metrics(scored, points) == experiment_runner._test_metrics(
        scored, points
    )

    legacy = tmp_path / "legacy-plots"
    experiment_runner._save_test_plots(scored, legacy)
    migrated = test_opening._plot_bytes(scored)
    assert set(migrated) == {
        "plots/roc_curve.png",
        "plots/score_distribution.png",
        "plots/score_vs_m4l.png",
    }
    for relative, content in migrated.items():
        assert content == (legacy / Path(relative).name).read_bytes()


def test_success_does_not_write_back_any_development_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    _, development = write_eligible_development_run(tmp_path)
    _stub_model(monkeypatch)
    before = {
        path.relative_to(development).as_posix(): path.read_bytes()
        for path in development.rglob("*")
        if path.is_file()
    }
    run_open_test(development_run=development, run_dir=tmp_path / "runs/no-writeback")
    after = {
        path.relative_to(development).as_posix(): path.read_bytes()
        for path in development.rglob("*")
        if path.is_file() and path.relative_to(development).as_posix() != "state/test_opening.json"
    }
    assert after == before


def test_test_scores_cannot_change_frozen_thresholds(
    tmp_path: Path, monkeypatch
) -> None:
    _, development = write_eligible_development_run(tmp_path)
    _stub_model(monkeypatch)
    points = json.loads(
        (development / "artifacts/working_points.json").read_text(encoding="utf-8")
    )

    def poisoned_scores(model, frame, features):
        return np.linspace(0.99, 0.01, len(frame))

    monkeypatch.setattr(test_opening, "positive_scores", poisoned_scores)
    output = tmp_path / "runs/poisoned-scores"
    run_open_test(development_run=development, run_dir=output)
    metrics = json.loads((output / "artifacts/test_metrics.json").read_text())
    assert [metrics["working_points"][name]["threshold"] for name in points] == [
        points[name]["threshold"] for name in points
    ]
