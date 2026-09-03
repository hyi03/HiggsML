from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import io
import json
import logging
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd
import torch
import yaml

from src.artifacts.manifest import (
    peak_memory_bytes,
    sha256_file,
    software_record,
    write_canonical_json,
)
from src.artifacts.plots import write_development_plots
from src.artifacts.transaction import RunTransaction
from src.preprocessing.outputs import canonical_csv_bytes, write_canonical_table
from src.training.config import TrainingProtocol, load_training_protocol
from src.training.dataset import build_validated_fold
from src.training.development_reader import DevelopmentInput, read_development_input
from src.training.folds import assign_folds
from src.training.qualification import (
    OOF_COLUMNS,
    evaluate_candidate,
    select_candidate,
    validate_candidate_oof,
    weighted_roc_points,
)
from src.training.trainer import train_fixed_epochs, train_fold


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DevelopmentResult:
    status: str
    selected_lambda: float | None
    run_dir: Path


def _csv_token(value: Any) -> str:
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if not np.isfinite(number):
            raise ValueError("CSV metric must be finite")
        return format(number, ".17g")
    return str(value)


def _canonical_metric_csv(frame: pd.DataFrame, columns: tuple[str, ...]) -> bytes:
    if tuple(frame.columns) != columns:
        raise ValueError("metric dataframe columns changed")
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in frame.itertuples(index=False, name=None):
        writer.writerow([_csv_token(value) for value in row])
    return buffer.getvalue().encode("utf-8")


def _write_bytes(path: Path, payload: bytes) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}


def _record(root: Path, relative: str, *, canonical_sha: str | None = None, row_count: int | None = None) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "row_count": row_count,
        "canonical_content_sha256": canonical_sha,
    }


def _candidate_metric_row(candidate: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "target_lambda": candidate["target_lambda"],
        "weighted_oof_auc": candidate["weighted_oof_auc"],
    }
    for name in ("loose", "medium", "tight"):
        point = candidate["working_points"][name]
        row.update(
            {
                f"{name}_threshold": point["threshold"],
                f"{name}_target_background_efficiency": point["target_background_efficiency"],
                f"{name}_achieved_background_efficiency": point["achieved_background_efficiency"],
                f"{name}_signal_efficiency": point["signal_efficiency"],
                f"{name}_ks": point["ks"],
            }
        )
    row["eligible"] = candidate["eligible"]
    row["rejection_reasons_json"] = json.dumps(candidate["rejection_reasons"], separators=(",", ":"))
    return row


def _candidate_oof(
    input_data: DevelopmentInput,
    protocol: TrainingProtocol,
    folds: np.ndarray,
    *,
    target_lambda: float,
    show_progress: bool = False,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[int], dict[str, Any]]:
    development = input_data.development
    scores = np.full(len(development.frame), np.nan, dtype=np.float64)
    fold_rows: list[dict[str, Any]] = []
    best_epochs: list[int] = []
    environment: dict[str, Any] | None = None
    for fold_index in range(protocol.fold_count):
        validation_indices = np.flatnonzero(folds == fold_index)
        fitting_indices = np.flatnonzero(folds != fold_index)
        fold = build_validated_fold(
            development, fitting_indices, validation_indices, fold_index=fold_index
        )
        training_kwargs: dict[str, Any] = {"target_lambda": target_lambda}
        if show_progress:
            training_kwargs.update(
                show_progress=True,
                progress_label=(
                    f"train lambda={target_lambda:g} "
                    f"fold={fold_index + 1}/{protocol.fold_count}"
                ),
            )
        result = train_fold(fold, protocol, **training_kwargs)
        scores[validation_indices] = np.asarray(result.validation_scores, dtype=np.float64)
        best_epochs.append(result.best_epoch)
        environment = result.environment
        for metric in result.epochs:
            fold_rows.append(
                {
                    "target_lambda": target_lambda,
                    "fold_index": fold_index,
                    "fold_seed": fold.fold_seed,
                    "epoch": metric.epoch,
                    "lambda_effective": metric.lambda_effective,
                    "train_cls_loss": metric.train_cls_loss,
                    "train_adv_loss": metric.train_adv_loss,
                    "train_total_loss": metric.train_total_loss,
                    "validation_weighted_auc": metric.validation_weighted_auc,
                    "is_best": metric.is_best,
                    "duration_seconds": metric.duration_seconds,
                    "events_per_second": metric.events_per_second,
                    "best_epoch": result.best_epoch,
                    "best_validation_weighted_auc": result.best_validation_weighted_auc,
                    "epochs_completed": result.epochs_completed,
                    "stopped_early": result.stopped_early,
                }
            )
    source = development.frame
    oof = pd.DataFrame(
        {
            "target_lambda": np.full(len(source), target_lambda),
            "source_sample": source["source_sample"].to_numpy(copy=True),
            "source_entry": source["source_entry"].to_numpy(copy=True),
            "fold_index": folds.copy(),
            "label": source["label"].to_numpy(copy=True),
            "m4l": source["m4l"].to_numpy(copy=True),
            "physical_weight": source["physical_weight"].to_numpy(copy=True),
            "train_weight": source["train_weight"].to_numpy(copy=True),
            "score": scores,
        },
        columns=OOF_COLUMNS,
    )
    validate_candidate_oof(oof, development, folds, target_lambda=target_lambda)
    if environment is None:
        raise RuntimeError("candidate completed without fold environment")
    return oof, fold_rows, best_epochs, environment


def execute_development(
    *,
    input_run: str | Path,
    protocol_path: str | Path,
    run_dir: str | Path,
    allowed_root: str | Path,
    input_allowed_root: str | Path | None = None,
    show_progress: bool = False,
) -> DevelopmentResult:
    protocol = load_training_protocol(protocol_path)
    started = time.perf_counter()
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    input_root = input_allowed_root if input_allowed_root is not None else allowed_root
    with RunTransaction(run_dir, allowed_root=allowed_root) as transaction:
        input_data = read_development_input(
            input_run, allowed_root=input_root, protocol_sha256=protocol.sha256
        )
        folds = assign_folds(input_data.development)
        candidate_frames: list[pd.DataFrame] = []
        fold_rows: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        epochs_by_lambda: dict[float, list[int]] = {}
        environment: dict[str, Any] | None = None
        auc_minimum = float(protocol.raw["qualification"]["auc_minimum"])
        ks_maximum = float(protocol.raw["qualification"]["ks_maximum"])
        for target_lambda in protocol.target_lambdas:
            oof, rows, best_epochs, environment = _candidate_oof(
                input_data,
                protocol,
                folds,
                target_lambda=target_lambda,
                show_progress=show_progress,
            )
            candidate_frames.append(oof)
            fold_rows.extend(rows)
            epochs_by_lambda[target_lambda] = best_epochs
            candidate = evaluate_candidate(oof, protocol)
            candidates.append(candidate)
            working_points = candidate["working_points"]
            LOGGER.info(
                "development candidate complete:\n"
                "  target_lambda\t\t= %g\t\tthreshold = registered\tPass\n"
                "  weighted_oof_auc\t= %.6f\tthreshold >= %.6f\t%s\n"
                "  loose_ks\t\t= %.6f\tthreshold <= %.6f\t%s\n"
                "  medium_ks\t\t= %.6f\tthreshold <= %.6f\t%s\n"
                "  tight_ks\t\t= %.6f\tthreshold <= %.6f\t%s\n"
                "  eligible\t\t= %s\t\tthreshold = true\t%s",
                target_lambda,
                candidate["weighted_oof_auc"],
                auc_minimum,
                "Pass" if candidate["weighted_oof_auc"] >= auc_minimum else "Fail",
                working_points["loose"]["ks"],
                ks_maximum,
                "Pass" if working_points["loose"]["ks"] <= ks_maximum else "Fail",
                working_points["medium"]["ks"],
                ks_maximum,
                "Pass" if working_points["medium"]["ks"] <= ks_maximum else "Fail",
                working_points["tight"]["ks"],
                ks_maximum,
                "Pass" if working_points["tight"]["ks"] <= ks_maximum else "Fail",
                str(candidate["eligible"]).lower(),
                "Pass" if candidate["eligible"] else "Fail",
            )
        selected = select_candidate(candidates, protocol)
        selected_lambda = None if selected is None else float(selected["target_lambda"])
        status = "no_eligible_candidate" if selected is None else "eligible"
        final_result = None
        final_epochs = None
        if selected is not None:
            ordered_epochs = sorted(epochs_by_lambda[selected_lambda])
            final_epochs = int(ordered_epochs[2])
            final_kwargs: dict[str, Any] = {
                "target_lambda": selected_lambda,
                "epochs": final_epochs,
            }
            if show_progress:
                final_kwargs["show_progress"] = True
            final_result = train_fixed_epochs(
                input_data.development, protocol, **final_kwargs
            )

        artifacts = transaction.path / "artifacts"
        predictions = transaction.path / "predictions"
        artifacts.mkdir()
        predictions.mkdir()
        snapshot = {
            "schema_version": "development-config-v1",
            "input_run": str(Path(input_run)),
            "input_manifest_sha256": input_data.input_manifest_sha256,
            "protocol_sha256": protocol.sha256,
            "protocol": protocol.raw,
        }
        config_payload = yaml.safe_dump(snapshot, sort_keys=False).encode("utf-8")
        _write_bytes(transaction.path / "config.yaml", config_payload)

        candidate_columns = tuple(protocol.raw["development_artifacts"]["candidate_metric_columns"])
        candidate_frame = pd.DataFrame(
            [_candidate_metric_row(item) for item in candidates], columns=candidate_columns
        )
        _write_bytes(
            artifacts / "candidate_metrics.csv",
            _canonical_metric_csv(candidate_frame, candidate_columns),
        )
        fold_columns = tuple(protocol.raw["development_artifacts"]["fold_metric_columns"])
        fold_frame = pd.DataFrame(fold_rows, columns=fold_columns)
        _write_bytes(
            artifacts / "fold_metrics.csv", _canonical_metric_csv(fold_frame, fold_columns)
        )

        qualification = {
            "schema_version": "development-qualification-v1",
            "status": status,
            "selected_lambda": selected_lambda,
            "final_epochs": final_epochs,
            "tie_rule": {"reference": "maximum_eligible_auc", "rtol": 0.0, "atol": 1.0e-6, "prefer": "smaller_lambda"},
            "candidates": candidates,
        }
        write_canonical_json(artifacts / "qualification.json", qualification)
        write_canonical_json(
            artifacts / "working_points.json",
            {
                "schema_version": "development-working-points-v1",
                "selected_lambda": selected_lambda,
                "candidates": [
                    {"target_lambda": item["target_lambda"], "working_points": item["working_points"]}
                    for item in candidates
                ],
            },
        )

        source_samples = input_data.development.frame["source_sample"].astype(str).tolist()
        source_entries = input_data.development.frame["source_entry"].tolist()
        sample_bytes = [sample.encode("utf-8") for sample in source_samples]
        identity_order = sorted(
            range(input_data.development_rows),
            key=lambda index: (sample_bytes[index], int(source_entries[index])),
        )
        published_oof = pd.concat(
            [frame.iloc[identity_order] for frame in candidate_frames], ignore_index=True
        )
        oof_payload = canonical_csv_bytes(
            published_oof,
            OOF_COLUMNS,
            integer_columns={"source_entry", "fold_index", "label"},
            string_columns={"source_sample"},
        )
        table_receipt = write_canonical_table(
            predictions / "oof_scores.csv.gz",
            oof_payload,
            row_count=len(published_oof),
        )

        display_lambda = selected_lambda
        if display_lambda is None:
            display_lambda = float(
                max(candidates, key=lambda item: item["weighted_oof_auc"])["target_lambda"]
            )
        display_oof = published_oof.loc[published_oof["target_lambda"] == display_lambda]
        write_development_plots(
            transaction.path / "plots",
            candidates,
            published_oof,
            selected_lambda=selected_lambda,
            roc_points=weighted_roc_points(display_oof),
            mass_edges=tuple(float(value) for value in protocol.raw["adversary"]["mass_edges_gev"]),
        )
        if final_result is not None:
            model = transaction.path / "model"
            model.mkdir()
            torch.save(final_result.model_payload, model / "model.pt")
            write_canonical_json(model / "scaler.json", final_result.scaler.to_dict())

        required = list(protocol.raw["development_artifacts"]["required_paths"])
        output_paths = [path for path in required if path != "artifacts/manifest.json"]
        if final_result is not None:
            output_paths.extend(protocol.raw["development_artifacts"]["eligible_only_paths"])
        outputs = [
            _record(
                transaction.path,
                relative,
                canonical_sha=(table_receipt.canonical_content_sha256 if relative == "predictions/oof_scores.csv.gz" else None),
                row_count=(len(published_oof) if relative == "predictions/oof_scores.csv.gz" else None),
            )
            for relative in output_paths
        ]
        software = software_record()
        manifest = {
            "schema_version": "development-manifest-v1",
            "status": status,
            "run_type": "development",
            "started_at_utc": started_utc,
            "completed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "input": {
                "manifest_sha256": input_data.input_manifest_sha256,
                "table_sha256": input_data.input_table_sha256,
                "canonical_content_sha256": input_data.input_canonical_content_sha256,
                "preprocess_protocol_sha256": input_data.preprocess_protocol_sha256,
                "preprocess_run_config_sha256": input_data.preprocess_run_config_sha256,
            },
            "protocol": {"id": protocol.protocol_id, "sha256": protocol.sha256},
            "outputs": outputs,
            "counts": {
                "input_rows": input_data.total_rows,
                "development_rows": input_data.development_rows,
                "held_out_test_rows_not_opened": input_data.held_out_test_rows,
                "candidates": len(candidates),
                "folds_per_candidate": protocol.fold_count,
                "fold_epoch_rows": len(fold_rows),
                "oof_rows": len(published_oof),
            },
            "schema": {
                "oof_columns": list(published_oof.columns),
                "oof_dtypes": {
                    name: str(published_oof[name].dtype) for name in published_oof.columns
                },
                "candidate_metric_columns": list(candidate_frame.columns),
                "candidate_metric_dtypes": {
                    name: str(candidate_frame[name].dtype) for name in candidate_frame.columns
                },
                "fold_metric_columns": list(fold_frame.columns),
                "fold_metric_dtypes": {
                    name: str(fold_frame[name].dtype) for name in fold_frame.columns
                },
            },
            "oof_completeness": {
                "complete": True,
                "candidate_count": len(candidates),
                "rows_per_candidate": input_data.development_rows,
                "unique_identities_per_candidate": input_data.development_rows,
            },
            "selection": {"selected_lambda": selected_lambda, "final_epochs": final_epochs},
            "environment": environment,
            "software": software,
            "performance": {"wall_seconds": time.perf_counter() - started, "peak_memory_bytes": peak_memory_bytes()},
            "boundaries": {
                "educational_technical_demo": True,
                "real_data_read": False,
                "held_out_test_opened": False,
                "open_test_run": False,
                "authority_environment_verified": False,
            },
        }
        write_canonical_json(artifacts / "manifest.json", manifest)
    published_run = Path(run_dir).resolve()
    LOGGER.info(
        "development run complete: status=%s selected_lambda=%s run_dir=%s",
        status,
        selected_lambda,
        published_run,
    )
    return DevelopmentResult(status, selected_lambda, published_run)
