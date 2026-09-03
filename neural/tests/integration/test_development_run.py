from __future__ import annotations

import gzip
import hashlib
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import torch

from src.artifacts.manifest import canonical_json_bytes, sha256_file
from src.artifacts.transaction import RunPathError
from src.cli import train as train_cli
from src.config import ExitCode, InputBindingError
from src.training.config import load_training_protocol
from src.training.dataset import FEATURE_COLUMNS, FoldLocalScaler
from src.training.development import execute_development
from src.training import development_reader
from src.training.development_reader import read_development_input
from src.training.qualification import weighted_auc
from src.training.trainer import EpochMetric, FinalTrainingResult
from src.training.network import AdversarialMLP
from tests.development_fixtures import write_synthetic_preprocess_run


PROJECT = Path(__file__).resolve().parents[2]
PROTOCOL = PROJECT / "config/adversarial_mlp_protocol_normal.yaml"


def _fake_fold_result(fold, target_lambda: float):
    scores = tuple(0.9 if label == 1 else 0.1 for label in fold.validation_labels.tolist())
    best_epoch = (3, 9, 5, 11, 7)[fold.fold_index]
    metric = EpochMetric(best_epoch, 0.0, 0.2, 0.0, 0.2, 0.9, True, 0.01, 100.0)
    return SimpleNamespace(
        validation_scores=scores,
        best_epoch=best_epoch,
        best_validation_weighted_auc=0.9,
        epochs=(metric,),
        epochs_completed=1,
        stopped_early=False,
        environment={"device": "cpu", "deterministic_algorithms": True},
    )


def _candidate(target_lambda: float, *, eligible_lambda: float | None):
    eligible = eligible_lambda is not None and target_lambda == eligible_lambda
    points = {
        name: {
            "threshold": 0.1,
            "target_background_efficiency": target,
            "achieved_background_efficiency": 0.1,
            "signal_efficiency": 0.9,
            "ks": 0.05 if eligible else 0.20,
        }
        for name, target in (("loose", 0.5), ("medium", 0.2), ("tight", 0.1))
    }
    return {
        "target_lambda": target_lambda,
        "weighted_oof_auc": 0.9 - target_lambda / 100.0,
        "working_points": points,
        "eligible": eligible,
        "rejection_reasons": []
        if eligible
        else [
            "loose_ks_above_maximum",
            "medium_ks_above_maximum",
            "tight_ks_above_maximum",
        ],
    }


def _install_fast_pipeline(monkeypatch: pytest.MonkeyPatch, *, eligible_lambda: float | None):
    fold_calls: list[tuple[float, int]] = []
    plot_inputs: list[pd.DataFrame] = []
    final_calls: list[tuple[float, int]] = []

    def fake_train_fold(fold, protocol, *, target_lambda: float):
        fold_calls.append((target_lambda, fold.fold_index))
        return _fake_fold_result(fold, target_lambda)

    def fake_evaluate(frame: pd.DataFrame, protocol):
        return _candidate(float(frame["target_lambda"].iloc[0]), eligible_lambda=eligible_lambda)

    def fake_final(development, protocol, *, target_lambda: float, epochs: int):
        final_calls.append((target_lambda, epochs))
        scaler = FoldLocalScaler.fit(
            development.frame[list(FEATURE_COLUMNS)].to_numpy(dtype="float64")
        )
        model = AdversarialMLP().cpu().to(torch.float32)
        return FinalTrainingResult(
            {
                "schema_version": "adversarial-mlp-final-v1",
                "protocol_sha256": protocol.sha256,
                "feature_tuple": FEATURE_COLUMNS,
                "scaler": scaler.to_dict(),
                "target_lambda": target_lambda,
                "seed": 42,
                "epochs": epochs,
                "classifier_state_dict": {
                    name: tensor.detach().cpu().clone()
                    for name, tensor in model.classifier.state_dict().items()
                },
                "adversary_state_dict": {
                    name: tensor.detach().cpu().clone()
                    for name, tensor in model.adversary.state_dict().items()
                },
                "environment": {"device": "cpu"},
            },
            ({"epoch": 1, "train_total_loss": 0.1},),
            scaler,
            {"device": "cpu"},
        )

    def fake_plots(directory, candidates, oof, *, selected_lambda, roc_points, mass_edges):
        assert "split" not in oof
        assert len(roc_points) == 2
        assert tuple(mass_edges) == tuple(protocol_mass_edges())
        assert set(oof["source_entry"]) and len(oof) == len(set(zip(oof["source_sample"], oof["source_entry"]))) * 5
        plot_inputs.append(oof.copy())
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        paths = tuple(destination / name for name in ("auc_vs_lambda.png", "ks_vs_lambda.png", "oof_roc.png", "oof_mass_sculpting.png"))
        for path in paths:
            path.write_bytes(b"synthetic educational plot")
        return paths

    monkeypatch.setattr("src.training.development.train_fold", fake_train_fold)
    monkeypatch.setattr("src.training.development.evaluate_candidate", fake_evaluate)
    monkeypatch.setattr("src.training.development.train_fixed_epochs", fake_final)
    monkeypatch.setattr("src.training.development.write_development_plots", fake_plots)
    return fold_calls, plot_inputs, final_calls


def protocol_mass_edges() -> list[float]:
    return list(load_training_protocol(PROTOCOL).raw["adversary"]["mass_edges_gev"])


def test_two_stage_reader_skips_poison_test_feature_before_numeric_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root = tmp_path / "runs"
    input_run, full_frame = write_synthetic_preprocess_run(
        allowed_root, poison_test_feature=True
    )
    protocol = load_training_protocol(PROTOCOL)

    original_decoder = development_reader._decode_development_rows
    decoder_payloads: list[bytes] = []

    def spy_decoder(payload: bytes):
        decoder_payloads.append(payload)
        assert b"this-test-feature-must-never-be-decoded" not in payload
        return original_decoder(payload)

    monkeypatch.setattr(development_reader, "_decode_development_rows", spy_decoder)
    loaded = read_development_input(
        input_run, allowed_root=allowed_root, protocol_sha256=protocol.sha256
    )

    assert loaded.total_rows == len(full_frame)
    assert loaded.held_out_test_rows == 6
    assert loaded.development_rows == len(full_frame) - 6
    assert set(loaded.development.frame["split"]) == {"train", "validation"}
    assert "this-test-feature-must-never-be-decoded" not in loaded.development.frame.to_string()
    assert len(decoder_payloads) == 1


@pytest.mark.parametrize("eligible_lambda", [None, 0.05])
def test_development_run_publishes_exact_normal_terminal_layouts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    eligible_lambda: float | None,
) -> None:
    allowed_root = tmp_path / "runs"
    input_run, full_frame = write_synthetic_preprocess_run(allowed_root)
    fold_calls, plot_inputs, final_calls = _install_fast_pipeline(
        monkeypatch, eligible_lambda=eligible_lambda
    )
    output = allowed_root / ("eligible" if eligible_lambda is not None else "no-eligible")
    caplog.set_level(logging.INFO, logger="src.training.development")

    result = execute_development(
        input_run=input_run,
        protocol_path=PROTOCOL,
        run_dir=output,
        allowed_root=allowed_root,
    )

    assert len(fold_calls) == 25
    assert fold_calls == [
        (target_lambda, fold_index)
        for target_lambda in (0.0, 0.05, 0.1, 0.2, 0.5)
        for fold_index in range(5)
    ]
    assert len(plot_inputs) == 1
    assert final_calls == ([] if eligible_lambda is None else [(eligible_lambda, 7)])
    assert result.status == ("eligible" if eligible_lambda is not None else "no_eligible_candidate")
    candidate_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "src.training.development"
        and record.getMessage().startswith("development candidate complete:")
    ]
    protocol = load_training_protocol(PROTOCOL)
    auc_minimum = float(protocol.raw["qualification"]["auc_minimum"])
    ks_maximum = float(protocol.raw["qualification"]["ks_maximum"])
    expected_messages = []
    for target_lambda in (0.0, 0.05, 0.1, 0.2, 0.5):
        eligible = eligible_lambda is not None and target_lambda == eligible_lambda
        auc = 0.9 - target_lambda / 100.0
        ks = 0.05 if eligible else 0.20
        expected_messages.append(
            "development candidate complete:\n"
            f"  target_lambda\t\t= {target_lambda:g}\t\tthreshold = registered\tPass\n"
            f"  weighted_oof_auc\t= {auc:.6f}\tthreshold >= {auc_minimum:.6f}\t"
            f"{'Pass' if auc >= auc_minimum else 'Fail'}\n"
            f"  loose_ks\t\t= {ks:.6f}\tthreshold <= {ks_maximum:.6f}\t"
            f"{'Pass' if ks <= ks_maximum else 'Fail'}\n"
            f"  medium_ks\t\t= {ks:.6f}\tthreshold <= {ks_maximum:.6f}\t"
            f"{'Pass' if ks <= ks_maximum else 'Fail'}\n"
            f"  tight_ks\t\t= {ks:.6f}\tthreshold <= {ks_maximum:.6f}\t"
            f"{'Pass' if ks <= ks_maximum else 'Fail'}\n"
            f"  eligible\t\t= {str(eligible).lower()}\t\tthreshold = true\t"
            f"{'Pass' if eligible else 'Fail'}"
        )
    assert candidate_messages == expected_messages
    assert (output / "model").exists() is (eligible_lambda is not None)
    manifest = json.loads((output / "artifacts" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["boundaries"] == {
        "authority_environment_verified": False,
        "educational_technical_demo": True,
        "held_out_test_opened": False,
        "open_test_run": False,
        "real_data_read": False,
    }
    assert manifest["counts"]["candidates"] == 5
    assert manifest["counts"]["folds_per_candidate"] == 5
    assert manifest["counts"]["held_out_test_rows_not_opened"] == 6
    assert manifest["counts"]["fold_epoch_rows"] == 25
    assert manifest["input"]["preprocess_protocol_sha256"] == "1" * 64
    assert manifest["input"]["preprocess_run_config_sha256"] == "2" * 64
    assert manifest["schema"]["oof_columns"] == list(protocol.raw["development_artifacts"]["oof_columns"])
    assert manifest["oof_completeness"] == {
        "candidate_count": 5,
        "complete": True,
        "rows_per_candidate": len(full_frame) - 6,
        "unique_identities_per_candidate": len(full_frame) - 6,
    }
    for record in manifest["outputs"]:
        assert sha256_file(output / record["path"]) == record["sha256"]
    assert tuple(pd.read_csv(output / "artifacts" / "candidate_metrics.csv").columns) == tuple(
        protocol.raw["development_artifacts"]["candidate_metric_columns"]
    )
    assert tuple(pd.read_csv(output / "artifacts" / "fold_metrics.csv").columns) == tuple(
        protocol.raw["development_artifacts"]["fold_metric_columns"]
    )
    for relative in (
        "artifacts/qualification.json",
        "artifacts/working_points.json",
        "artifacts/manifest.json",
    ):
        payload = (output / relative).read_bytes()
        assert payload == canonical_json_bytes(json.loads(payload))
        assert payload.count(b"\n") == 1 and payload.endswith(b"\n")
    with gzip.open(output / "predictions" / "oof_scores.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        oof = pd.read_csv(stream)
    assert len(oof) == (len(full_frame) - 6) * 5
    assert "split" not in oof
    expected_identity = sorted(
        zip(
            full_frame.loc[full_frame["split"] != "test", "source_sample"],
            full_frame.loc[full_frame["split"] != "test", "source_entry"],
            strict=True,
        ),
        key=lambda item: (item[0].encode("utf-8"), int(item[1])),
    )
    for target_lambda, block in oof.groupby("target_lambda", sort=False):
        assert list(zip(block["source_sample"], block["source_entry"], strict=True)) == expected_identity
    oof_payload = gzip.decompress((output / "predictions" / "oof_scores.csv.gz").read_bytes())
    oof_record = next(
        item for item in manifest["outputs"] if item["path"] == "predictions/oof_scores.csv.gz"
    )
    assert hashlib.sha256(oof_payload).hexdigest() == oof_record["canonical_content_sha256"]
    if eligible_lambda is not None:
        payload = torch.load(output / "model" / "model.pt", weights_only=False)
        assert payload["schema_version"] == "adversarial-mlp-final-v1"
        for relative in ("model/model.pt", "model/scaler.json"):
            record = next(item for item in manifest["outputs"] if item["path"] == relative)
            assert sha256_file(output / relative) == record["sha256"]


def test_poison_fixture_passes_command_pipeline_without_test_feature_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root = tmp_path / "runs"
    input_run, _ = write_synthetic_preprocess_run(allowed_root, poison_test_feature=True)
    _install_fast_pipeline(monkeypatch, eligible_lambda=None)
    result = execute_development(
        input_run=input_run,
        protocol_path=PROTOCOL,
        run_dir=allowed_root / "poison-command",
        allowed_root=allowed_root,
    )
    assert result.status == "no_eligible_candidate"


def test_real_synthetic_development_e2e_uses_actual_science_pipeline(tmp_path: Path) -> None:
    allowed_root = tmp_path / "runs"
    input_run, full_frame = write_synthetic_preprocess_run(allowed_root)
    output = allowed_root / "real-e2e"
    result = execute_development(
        input_run=input_run,
        protocol_path=PROTOCOL,
        run_dir=output,
        allowed_root=allowed_root,
    )
    assert result.status == "eligible"
    oof = pd.read_csv(output / "predictions" / "oof_scores.csv.gz")
    candidates = pd.read_csv(output / "artifacts" / "candidate_metrics.csv")
    assert len(oof) == (len(full_frame) - 6) * 5
    for row in candidates.itertuples(index=False):
        block = oof.loc[oof["target_lambda"] == row.target_lambda]
        assert weighted_auc(block["label"], block["score"], block["train_weight"]) == pytest.approx(
            row.weighted_oof_auc, rel=0.0, abs=1e-15
        )
    manifest = json.loads((output / "artifacts" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "eligible"
    assert (output / "model" / "model.pt").is_file()
    assert (output / "model" / "scaler.json").is_file()


def test_abnormal_fold_failure_stops_candidates_and_publishes_no_success_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root = tmp_path / "runs"
    input_run, _ = write_synthetic_preprocess_run(allowed_root)
    calls = 0

    def fail_on_seventh(fold, protocol, *, target_lambda: float):
        nonlocal calls
        calls += 1
        if calls == 7:
            raise RuntimeError("synthetic fold failure")
        return _fake_fold_result(fold, target_lambda)

    monkeypatch.setattr("src.training.development.train_fold", fail_on_seventh)
    output = allowed_root / "failed"
    with pytest.raises(RuntimeError, match="synthetic fold failure"):
        execute_development(
            input_run=input_run,
            protocol_path=PROTOCOL,
            run_dir=output,
            allowed_root=allowed_root,
        )

    assert calls == 7
    assert (output / "failure.json").is_file()
    assert not (output / "artifacts" / "manifest.json").exists()


def test_train_cli_dispatch_and_exit_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = []

    def success(**kwargs):
        captured.append(kwargs)

    arguments = [
        "develop",
        "--input-run", "runs/input",
        "--protocol", "config/adversarial_mlp_protocol_normal.yaml",
        "--run-dir", "runs/output",
    ]
    monkeypatch.setattr(train_cli, "execute_development", success)
    assert train_cli.main(arguments) == int(ExitCode.SUCCESS)
    assert captured[0]["input_run"] == "runs/input"

    for error, code in (
        (InputBindingError("bound failure"), ExitCode.INPUT_BINDING),
        (RunPathError("run failure"), ExitCode.TRANSACTION),
        (RuntimeError("internal failure"), ExitCode.INTERNAL_ERROR),
    ):
        monkeypatch.setattr(
            train_cli,
            "execute_development",
            lambda **kwargs: (_ for _ in ()).throw(error),
        )
        assert train_cli.main(arguments) == int(code)
