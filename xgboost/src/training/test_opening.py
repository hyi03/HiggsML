"""Exactly-once held-out MC test opening for an eligible development run."""

from __future__ import annotations

from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import stat
from typing import Any, Mapping

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

from ..artifacts.manifest import canonical_json_bytes
from ..artifacts.transaction import RunTransaction
from ..config import load_preprocessing_protocol, load_xgboost_protocol
from ..preprocessing.pipeline import MODEL_FEATURES, OUTPUT_COLUMNS
from .dataset import (
    DevelopmentInput,
    load_development_input,
    read_regular_bytes,
    verify_development_input,
)
from .evaluation import OOF_COLUMNS, background_mass_ks, build_working_points, weighted_oof_auc
from .model import model_parameters, positive_scores
from .qualification import qualify
from .trainer import _code_sha256, _git_identity, _software_versions


WORKING_POINT_NAMES = ("loose", "medium", "tight")
PREDICTION_COLUMNS = OUTPUT_COLUMNS + ("xgb_score",)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _strict_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase 64-hex SHA-256")
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown or missing:
        raise ValueError(f"{label} keys mismatch; unknown={unknown}, missing={missing}")


def _json_object(content: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid UTF-8 JSON") from exc
    return _mapping(value, label)


def _safe_artifact(root: Path, relative_path: object, expected: str, label: str) -> Path:
    if not isinstance(relative_path, str) or relative_path != expected:
        raise ValueError(f"unknown {label} artifact layout")
    relative = Path(relative_path)
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink {label} artifact paths are not allowed")
    destination = root.joinpath(*relative.parts)
    resolved_root = root.resolve(strict=True)
    resolved = destination.resolve(strict=True)
    if resolved_root not in resolved.parents:
        raise ValueError(f"{label} artifact escapes its run")
    return destination


def _receipt_bytes(
    root: Path,
    receipt_value: object,
    *,
    expected_path: str,
    label: str,
    extra_keys: set[str] | None = None,
) -> bytes:
    receipt = _mapping(receipt_value, f"{label} receipt")
    keys = {"path", "sha256", "size_bytes"} | (extra_keys or set())
    _exact_keys(receipt, keys, f"{label} receipt")
    expected_sha256 = _strict_sha256(receipt.get("sha256"), f"{label} receipt sha256")
    path = _safe_artifact(root, receipt.get("path"), expected_path, label)
    content = read_regular_bytes(path, label)
    if receipt.get("size_bytes") != len(content) or expected_sha256 != sha256_bytes(content):
        raise ValueError(f"{label} receipt does not match artifact bytes")
    return content


def _csv_frame(content: bytes, label: str) -> pd.DataFrame:
    try:
        frame = pd.read_csv(io.BytesIO(content))
    except (UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise ValueError(f"{label} must be valid UTF-8 CSV") from exc
    if frame.empty:
        raise ValueError(f"{label} must not be empty")
    return frame


def _validate_csv_receipt(
    receipt_value: object,
    frame: pd.DataFrame,
    expected_columns: tuple[str, ...],
    label: str,
) -> None:
    receipt = _mapping(receipt_value, f"{label} receipt")
    if receipt.get("rows") != len(frame):
        raise ValueError(f"{label} receipt rows do not match CSV")
    if receipt.get("columns") != list(expected_columns):
        raise ValueError(f"{label} receipt columns do not match CSV")
    if tuple(frame.columns) != expected_columns:
        raise ValueError(f"{label} columns do not match the frozen schema")


def _integer_values(series: pd.Series, label: str, *, minimum: int = 0) -> np.ndarray:
    try:
        values = series.to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must contain integers") from exc
    if (
        not np.isfinite(values).all()
        or not np.equal(values, np.rint(values)).all()
        or (values < minimum).any()
    ):
        raise ValueError(f"{label} must contain integers >= {minimum}")
    return values.astype(int)


def _validate_training_receipts(
    candidate_bytes: bytes,
    candidate_receipt: object,
    fold_bytes: bytes,
    fold_receipt: object,
    protocol: object,
) -> int:
    candidate = _csv_frame(candidate_bytes, "development candidate metrics")
    candidate_columns = (
        "candidate_index",
        *tuple(protocol.candidate),
        "mean_weighted_auc",
        "standard_error_weighted_auc",
        "selected",
    )
    _validate_csv_receipt(
        candidate_receipt,
        candidate,
        candidate_columns,
        "development candidate metrics",
    )
    candidate_indices = _integer_values(
        candidate["candidate_index"], "development candidate indices"
    )
    if len(candidate) != 1 or set(candidate_indices) != {0}:
        raise ValueError("development candidate coverage must be exactly candidate 0")
    selected = candidate["selected"].iloc[0]
    if not isinstance(selected, (bool, np.bool_)) or not bool(selected):
        raise ValueError("development candidate 0 must be selected")
    for name, expected in protocol.candidate.items():
        if candidate[name].iloc[0] != expected:
            raise ValueError("development candidate parameters do not match protocol")
    candidate_metrics = candidate.loc[
        :, ["mean_weighted_auc", "standard_error_weighted_auc"]
    ].to_numpy(dtype=float)
    if not np.isfinite(candidate_metrics).all():
        raise ValueError("development candidate metrics must be finite")

    folds = _csv_frame(fold_bytes, "development fold metrics")
    fold_columns = (
        "candidate_index", "fold", "weighted_auc", "unweighted_auc", "best_iteration"
    )
    _validate_csv_receipt(
        fold_receipt,
        folds,
        fold_columns,
        "development fold metrics",
    )
    fold_candidates = _integer_values(
        folds["candidate_index"], "development fold candidate indices"
    )
    fold_indices = _integer_values(folds["fold"], "development fold indices")
    expected_folds = set(range(int(protocol.common["folds"])))
    if (
        set(fold_candidates) != {0}
        or set(fold_indices) != expected_folds
        or len(folds) != len(expected_folds)
        or folds.duplicated(["candidate_index", "fold"]).any()
    ):
        raise ValueError("development fold coverage is incomplete or duplicated")
    aucs = folds.loc[:, ["weighted_auc", "unweighted_auc"]].to_numpy(dtype=float)
    if not np.isfinite(aucs).all():
        raise ValueError("development fold metrics must be finite")
    best_iterations = _integer_values(
        folds["best_iteration"], "development fold best iterations"
    )
    return max(1, int(np.rint(np.median(best_iterations + 1))))


def _file_fingerprint(path: Path, label: str) -> tuple[int, int, int, int]:
    if path.is_symlink():
        raise ValueError(f"symlink {label} inputs are not allowed")
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"{label} does not exist: {path}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"{label} must be a regular file")
    return (info.st_size, info.st_mtime_ns, info.st_ctime_ns, getattr(info, "st_ino", 0))


def _resolve_test_path(binding: DevelopmentInput) -> tuple[Path, Mapping[str, Any], tuple[int, int, int, int]]:
    outputs = _mapping(binding.manifest.get("outputs"), "preprocessing outputs")
    receipt = _mapping(outputs.get("test"), "preprocessing test receipt")
    _exact_keys(
        receipt,
        {"path", "rows", "columns", "sha256_compressed", "sha256_canonical_csv", "size_bytes"},
        "preprocessing test receipt",
    )
    path = _safe_artifact(
        binding.input_run, receipt.get("path"), "processed/test.csv.gz", "held-out test"
    )
    fingerprint = _file_fingerprint(path, "held-out test")
    if receipt.get("size_bytes") != fingerprint[0]:
        raise ValueError("held-out test size does not match preprocessing manifest")
    if receipt.get("columns") != list(OUTPUT_COLUMNS):
        raise ValueError("held-out test columns do not match the frozen schema")
    rows = receipt.get("rows")
    if isinstance(rows, bool) or not isinstance(rows, int) or rows <= 0:
        raise ValueError("held-out test row count must be a positive integer")
    for name in ("sha256_compressed", "sha256_canonical_csv"):
        value = receipt.get(name)
        _strict_sha256(value, f"held-out test {name}")
    return path, receipt, fingerprint


def _load_model(path: Path, features: tuple[str, ...]):
    try:
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise RuntimeError("install requirements.txt before opening test") from exc
    model = XGBClassifier()
    model.load_model(path)
    names = model.get_booster().feature_names
    if tuple(names or ()) != features or model.get_booster().num_features() != len(features):
        raise ValueError("frozen model feature binding does not match Angular19")
    return model


def _validate_oof(content: bytes, binding: DevelopmentInput) -> pd.DataFrame:
    try:
        canonical = gzip.decompress(content)
        frame = pd.read_csv(io.BytesIO(canonical))
    except (gzip.BadGzipFile, EOFError, OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise ValueError("development OOF artifact is invalid") from exc
    if tuple(frame.columns) != OOF_COLUMNS or len(frame) != len(binding.frame):
        raise ValueError("development OOF schema or row count is invalid")
    if frame.duplicated(["channelNumber", "eventNumber"]).any():
        raise ValueError("development OOF identity must be unique")
    numeric = frame.loc[:, [name for name in OOF_COLUMNS if name != "split"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("development OOF contains NaN or infinity")
    return frame


def _validate_development(development_run: Path) -> dict[str, object]:
    if development_run.is_symlink() or not development_run.is_dir():
        raise ValueError("development_run must be an existing non-symlink directory")
    claim_path = development_run / "state/test_opening.json"
    if claim_path.exists() or claim_path.is_symlink():
        raise FileExistsError("held-out test has already been opened")

    manifest_path = development_run / "artifacts/manifest.json"
    manifest_bytes = read_regular_bytes(manifest_path, "development manifest")
    manifest = _json_object(manifest_bytes, "development manifest")
    _exact_keys(
        manifest,
        {
            "schema_version", "run_type", "status", "created_at_utc", "test_opened",
            "protocol", "code", "software", "upstream_run", "candidate",
            "selected_candidate", "final_parameters", "working_points", "qualification",
            "outputs", "counts", "schema",
        },
        "development manifest",
    )
    if (
        manifest.get("schema_version") != "1.0"
        or manifest.get("run_type") != "xgboost_development"
        or manifest.get("status") != "eligible"
        or manifest.get("test_opened") is not False
    ):
        raise ValueError("development run is not eligible and unopened")

    outputs = _mapping(manifest.get("outputs"), "development outputs")
    _exact_keys(
        outputs,
        {"candidate_metrics", "fold_metrics", "qualification", "working_points", "oof_scores", "plots", "model"},
        "development outputs",
    )
    qualification_bytes = _receipt_bytes(
        development_run, outputs.get("qualification"),
        expected_path="artifacts/qualification.json", label="development qualification",
    )
    working_points_bytes = _receipt_bytes(
        development_run, outputs.get("working_points"),
        expected_path="artifacts/working_points.json", label="development working points",
    )
    candidate_bytes = _receipt_bytes(
        development_run, outputs.get("candidate_metrics"),
        expected_path="artifacts/candidate_metrics.csv", label="development candidate metrics",
        extra_keys={"rows", "columns"},
    )
    fold_bytes = _receipt_bytes(
        development_run, outputs.get("fold_metrics"),
        expected_path="artifacts/fold_metrics.csv", label="development fold metrics",
        extra_keys={"rows", "columns"},
    )
    oof_receipt = _mapping(outputs.get("oof_scores"), "development OOF receipt")
    _exact_keys(
        oof_receipt,
        {"path", "sha256", "size_bytes", "rows", "columns", "sha256_compressed", "sha256_canonical_csv"},
        "development OOF receipt",
    )
    oof_bytes = _receipt_bytes(
        development_run, oof_receipt,
        expected_path="predictions/oof_scores.csv.gz", label="development OOF",
        extra_keys={"rows", "columns", "sha256_compressed", "sha256_canonical_csv"},
    )
    if oof_receipt.get("sha256") != oof_receipt.get("sha256_compressed"):
        raise ValueError("development OOF compressed hashes are inconsistent")
    try:
        oof_canonical = gzip.decompress(oof_bytes)
    except (gzip.BadGzipFile, EOFError, OSError) as exc:
        raise ValueError("development OOF is not valid gzip") from exc
    if oof_receipt.get("sha256_canonical_csv") != sha256_bytes(oof_canonical):
        raise ValueError("development OOF canonical hash does not match receipt")

    model_bytes = _receipt_bytes(
        development_run, outputs.get("model"),
        expected_path="model/model.json", label="development model",
    )
    plots = _mapping(outputs.get("plots"), "development plot receipts")
    if set(plots) != {"plots/oof_scores.png"}:
        raise ValueError("unknown development plot layout")
    plot_bytes = _receipt_bytes(
        development_run, plots["plots/oof_scores.png"],
        expected_path="plots/oof_scores.png", label="development OOF plot",
    )

    protocol_identity = _mapping(manifest.get("protocol"), "development protocol identity")
    _exact_keys(protocol_identity, {"path", "schema_version", "sha256"}, "development protocol identity")
    config_path = development_run / "config.yaml"
    protocol_bytes = read_regular_bytes(config_path, "sealed XGBoost protocol")
    if _strict_sha256(
        protocol_identity.get("sha256"), "development protocol sha256"
    ) != sha256_bytes(protocol_bytes):
        raise ValueError("sealed XGBoost protocol hash does not match manifest")
    protocol = load_xgboost_protocol(config_path)
    if protocol_identity.get("schema_version") != protocol.raw["schema_version"]:
        raise ValueError("sealed XGBoost protocol schema does not match manifest")

    upstream = _mapping(manifest.get("upstream_run"), "development upstream binding")
    _exact_keys(upstream, {"path", "manifest", "protocol", "run_config", "development"}, "development upstream binding")
    binding = load_development_input(str(upstream.get("path")))
    upstream_manifest = _mapping(upstream.get("manifest"), "upstream manifest identity")
    if upstream_manifest != {"path": "artifacts/manifest.json", "sha256": binding.manifest_sha256}:
        raise ValueError("preprocessing manifest binding does not match development run")
    if upstream.get("protocol") != binding.upstream_protocol or upstream.get("run_config") != binding.upstream_run_config:
        raise ValueError("preprocessing identity binding does not match development run")
    development_identity = _mapping(upstream.get("development"), "upstream development identity")
    source_development = _mapping(binding.manifest["outputs"]["development"], "source development receipt")
    if development_identity != {
        "path": source_development["path"],
        "sha256_compressed": source_development["sha256_compressed"],
        "sha256_canonical_csv": source_development["sha256_canonical_csv"],
    }:
        raise ValueError("development input binding is inconsistent")

    preprocessing_protocol_path = Path(str(binding.upstream_protocol["path"]))
    preprocessing_protocol_bytes = read_regular_bytes(
        preprocessing_protocol_path, "preprocessing protocol"
    )
    if sha256_bytes(preprocessing_protocol_bytes) != binding.upstream_protocol["sha256"]:
        raise ValueError("preprocessing protocol hash does not match manifest")
    load_preprocessing_protocol(preprocessing_protocol_path)

    points = _json_object(working_points_bytes, "development working points")
    qualification = _json_object(qualification_bytes, "development qualification")
    if tuple(points) != WORKING_POINT_NAMES:
        raise ValueError("development working points must be loose, medium, tight")
    oof = _validate_oof(oof_bytes, binding)
    rebuilt_points = build_working_points(oof, protocol.working_points)
    rebuilt_qualification = qualify(
        oof,
        weighted_oof_auc(oof),
        rebuilt_points,
        background_mass_ks(oof, rebuilt_points),
        protocol.qualification,
        expected_development=binding.frame,
    )
    if points != rebuilt_points or manifest.get("working_points") != rebuilt_points:
        raise ValueError("development working points are inconsistent")
    if (
        qualification != rebuilt_qualification
        or manifest.get("qualification") != rebuilt_qualification
        or rebuilt_qualification.get("eligible") is not True
    ):
        raise ValueError("development qualification is inconsistent")
    counts = _mapping(manifest.get("counts"), "development counts")
    if counts != {"development": len(binding.frame), "oof": len(oof)}:
        raise ValueError("development counts are inconsistent")
    schema = _mapping(manifest.get("schema"), "development schema")
    if (
        schema.get("model_features") != list(MODEL_FEATURES)
        or schema.get("input_columns") != list(OUTPUT_COLUMNS)
        or schema.get("oof_columns") != list(OOF_COLUMNS)
    ):
        raise ValueError("development schema does not match Angular19")
    if manifest.get("candidate") != dict(protocol.candidate) or manifest.get("selected_candidate") != 0:
        raise ValueError("development candidate binding is inconsistent")
    final_tree_count = _validate_training_receipts(
        candidate_bytes,
        outputs.get("candidate_metrics"),
        fold_bytes,
        outputs.get("fold_metrics"),
        protocol,
    )
    expected_final_parameters = model_parameters(
        protocol, final=True, tree_count=final_tree_count
    )
    if manifest.get("final_parameters") != expected_final_parameters:
        raise ValueError("development final parameters are inconsistent")
    if oof_receipt.get("rows") != len(oof) or oof_receipt.get("columns") != list(
        OOF_COLUMNS
    ):
        raise ValueError("development OOF receipt rows or columns are inconsistent")

    allowed_files = {
        "config.yaml", "artifacts/candidate_metrics.csv", "artifacts/fold_metrics.csv",
        "artifacts/qualification.json", "artifacts/working_points.json",
        "artifacts/manifest.json", "predictions/oof_scores.csv.gz",
        "plots/oof_scores.png", "model/model.json",
    }
    allowed_directories = {"artifacts", "predictions", "plots", "model"}
    entries = list(development_run.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise ValueError("development run may not contain symlinks")
    actual_files = {
        path.relative_to(development_run).as_posix()
        for path in entries if path.is_file()
    }
    actual_directories = {
        path.relative_to(development_run).as_posix()
        for path in entries if path.is_dir()
    }
    if claim_path.exists() or claim_path.is_symlink():
        raise FileExistsError("held-out test has already been opened")
    if actual_files != allowed_files or actual_directories != allowed_directories:
        raise ValueError("development run contains an unknown or missing artifact")

    model_path = development_run / "model/model.json"
    model = _load_model(model_path, tuple(protocol.features))
    if model.get_booster().num_boosted_rounds() != final_tree_count:
        raise ValueError("development model boosted rounds do not match final parameters")

    test_path, test_receipt, test_fingerprint = _resolve_test_path(binding)
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "manifest_bytes": manifest_bytes,
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "protocol": protocol,
        "protocol_bytes": protocol_bytes,
        "config_path": config_path,
        "binding": binding,
        "preprocessing_protocol_path": preprocessing_protocol_path,
        "preprocessing_protocol_bytes": preprocessing_protocol_bytes,
        "model": model,
        "model_path": model_path,
        "model_bytes": model_bytes,
        "working_points": points,
        "test_path": test_path,
        "test_receipt": test_receipt,
        "test_fingerprint": test_fingerprint,
        "source_bytes": (
            (manifest_path, "development manifest", manifest_bytes),
            (config_path, "sealed XGBoost protocol", protocol_bytes),
            (development_run / "artifacts/candidate_metrics.csv", "development candidate metrics", candidate_bytes),
            (development_run / "artifacts/fold_metrics.csv", "development fold metrics", fold_bytes),
            (development_run / "artifacts/qualification.json", "development qualification", qualification_bytes),
            (development_run / "artifacts/working_points.json", "development working points", working_points_bytes),
            (development_run / "predictions/oof_scores.csv.gz", "development OOF", oof_bytes),
            (development_run / "plots/oof_scores.png", "development OOF plot", plot_bytes),
            (preprocessing_protocol_path, "preprocessing protocol", preprocessing_protocol_bytes),
            (model_path, "development model", model_bytes),
        ),
    }


def _claim(development_run: Path, test_run: Path, evidence: Mapping[str, object]) -> tuple[Path, bytes]:
    state = development_run / "state"
    if state.is_symlink():
        raise ValueError("development state path may not be a symlink")
    state.mkdir(exist_ok=True)
    if state.is_symlink():
        raise ValueError("development state path may not be a symlink")
    try:
        state_info = state.lstat()
    except FileNotFoundError as exc:
        raise ValueError("development state directory disappeared") from exc
    if (
        not stat.S_ISDIR(state_info.st_mode)
        or state.resolve(strict=True).parent != development_run.resolve(strict=True)
    ):
        raise ValueError("development state must remain a direct non-symlink directory")
    claim_path = state / "test_opening.json"
    test_receipt = _mapping(evidence["test_receipt"], "held-out test receipt")
    payload = {
        "schema_version": "1.0",
        "status": "claimed",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "development_manifest_sha256": evidence["manifest_sha256"],
        "test_run_path": str(test_run.resolve(strict=True)),
        "test_artifact": dict(test_receipt),
    }
    content = canonical_json_bytes(payload)
    try:
        with claim_path.open("xb") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise FileExistsError("held-out test has already been opened") from exc
    return claim_path, content


def _validate_test_frame(frame: pd.DataFrame) -> None:
    if tuple(frame.columns) != OUTPUT_COLUMNS or frame.empty:
        raise ValueError("held-out test must match the non-empty frozen 32-column schema")
    if set(frame["split"]) != {"test"} or set(frame["label"]) != {0, 1}:
        raise ValueError("held-out input must be test-only Higgs/ZZ MC")
    numeric = frame.loc[:, [name for name in OUTPUT_COLUMNS if name != "split"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("held-out test contains NaN or infinity")
    if frame.duplicated(["channelNumber", "eventNumber"]).any():
        raise ValueError("held-out test event identity must be unique")
    for label in (0, 1):
        weights = np.abs(frame.loc[frame["label"] == label, "physical_weight"].to_numpy(dtype=float))
        if weights.sum() <= 0:
            raise ValueError("each held-out class must have positive absolute physical weight")


def _test_metrics(test: pd.DataFrame, points: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    weights = np.abs(test["physical_weight"].to_numpy(dtype=float))
    working: dict[str, object] = {}
    for name, point in points.items():
        threshold = float(point["threshold"])
        selected = test["xgb_score"] >= threshold
        by_class: dict[str, object] = {}
        for label, class_name in ((0, "background"), (1, "signal")):
            class_mask = test["label"] == label
            denominator = float(weights[class_mask].sum())
            numerator = float(weights[class_mask & selected].sum())
            by_class[class_name] = {
                "efficiency": numerator / denominator,
                "selected_rows": int((class_mask & selected).sum()),
            }
        working[name] = {"threshold": threshold, **by_class}
    return {
        "schema_version": "1.0",
        "status": "complete",
        "test_rows": len(test),
        "weighted_auc": float(roc_auc_score(test["label"], test["xgb_score"], sample_weight=weights)),
        "unweighted_auc": float(roc_auc_score(test["label"], test["xgb_score"])),
        "working_points": working,
    }


def _plot_bytes(test: pd.DataFrame) -> dict[str, bytes]:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    output: dict[str, bytes] = {}
    weights = np.abs(test["physical_weight"].to_numpy(dtype=float))
    fpr, tpr, _ = roc_curve(test["label"], test["xgb_score"], sample_weight=weights)
    figure, axis = plt.subplots(figsize=(6, 5))
    axis.plot(fpr, tpr)
    axis.plot([0, 1], [0, 1], "--", color="0.6")
    axis.set(xlabel="Background efficiency", ylabel="Signal efficiency")
    figure.tight_layout()
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=160)
    plt.close(figure)
    output["plots/roc_curve.png"] = buffer.getvalue()

    figure, axis = plt.subplots(figsize=(7, 4.5))
    for label, name, color in ((0, "ZZ*", "tab:blue"), (1, "Higgs", "tab:red")):
        axis.hist(
            test.loc[test["label"] == label, "xgb_score"], bins=np.linspace(0, 1, 31),
            density=True, histtype="step", color=color, label=name,
        )
    axis.set(xlabel="XGBoost score", ylabel="Normalized events")
    axis.legend()
    figure.tight_layout()
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=160)
    plt.close(figure)
    output["plots/score_distribution.png"] = buffer.getvalue()

    figure, axis = plt.subplots(figsize=(6, 5))
    axis.scatter(test["m4l"], test["xgb_score"], s=5, alpha=0.25)
    axis.set(xlabel=r"$m_{4\ell}$ [GeV]", ylabel="XGBoost score")
    figure.tight_layout()
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=160)
    plt.close(figure)
    output["plots/score_vs_m4l.png"] = buffer.getvalue()
    return output


def _receipt(content: bytes, path: str, **extra: object) -> dict[str, object]:
    return {"path": path, "sha256": sha256_bytes(content), "size_bytes": len(content), **extra}


def _verify_sources_before_manifest(
    evidence: Mapping[str, object], claim_path: Path, claim_bytes: bytes
) -> None:
    binding = evidence.get("binding")
    if not isinstance(binding, DevelopmentInput):
        raise RuntimeError("validated development binding is unavailable")
    verify_development_input(binding)
    source_bytes = evidence.get("source_bytes")
    if not isinstance(source_bytes, tuple):
        raise RuntimeError("validated development source inventory is unavailable")
    checks = (*source_bytes, (claim_path, "test opening claim", claim_bytes))
    for path, label, expected in checks:
        if read_regular_bytes(path, label) != expected:
            raise RuntimeError(f"{label} changed during test opening")


def run_open_test(*, development_run: str | Path, run_dir: str | Path) -> Mapping[str, object]:
    destination = Path(run_dir).absolute()
    if destination.parent.name != "runs":
        raise ValueError("run directory must be a direct child of a named runs root")
    development = Path(development_run).absolute()
    project_root = Path(__file__).resolve().parents[2]
    with RunTransaction(destination, runs_root=destination.parent) as transaction:
        if development.is_symlink():
            raise ValueError("development_run must be an existing non-symlink directory")
        resolved_destination = destination.resolve(strict=True)
        resolved_development = development.resolve(strict=True)
        if (
            resolved_destination.parent != resolved_development.parent
            or resolved_destination.parent.name != "runs"
            or resolved_destination == resolved_development
        ):
            raise ValueError(
                "development and test runs must be distinct direct children of the same resolved runs root"
            )
        evidence = _validate_development(resolved_development)
        claim_path, claim_bytes = _claim(
            resolved_development, resolved_destination, evidence
        )

        test_path = evidence.get("test_path")
        if not isinstance(test_path, Path):
            raise RuntimeError("validated held-out test path is unavailable")
        compressed = read_regular_bytes(test_path, "held-out test")
        test_receipt = _mapping(evidence["test_receipt"], "held-out test receipt")
        if len(compressed) != test_receipt["size_bytes"] or sha256_bytes(compressed) != test_receipt["sha256_compressed"]:
            raise ValueError("held-out test compressed bytes do not match preprocessing manifest")
        try:
            canonical = gzip.decompress(compressed)
        except (gzip.BadGzipFile, EOFError, OSError) as exc:
            raise ValueError("held-out test is not valid gzip") from exc
        if sha256_bytes(canonical) != test_receipt["sha256_canonical_csv"]:
            raise ValueError("held-out test canonical CSV hash does not match preprocessing manifest")
        try:
            test = pd.read_csv(io.BytesIO(canonical))
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            raise ValueError("held-out test is not valid CSV") from exc
        _validate_test_frame(test)
        if len(test) != test_receipt["rows"]:
            raise ValueError("held-out test row count does not match preprocessing manifest")
        test["xgb_score"] = positive_scores(evidence["model"], test, tuple(MODEL_FEATURES))
        test = test.loc[:, PREDICTION_COLUMNS]
        points = evidence.get("working_points")
        if not isinstance(points, Mapping):
            raise RuntimeError("validated development working points are unavailable")
        metrics = _test_metrics(test, points)
        metrics_bytes = canonical_json_bytes(metrics)
        canonical_scores = test.to_csv(index=False, lineterminator="\n").encode("utf-8")
        compressed_scores = gzip.compress(canonical_scores, compresslevel=9, mtime=0)
        plots = _plot_bytes(test)

        transaction.write_bytes("artifacts/test_metrics.json", metrics_bytes)
        transaction.write_bytes("predictions/test_scores.csv.gz", compressed_scores)
        for path, content in plots.items():
            transaction.write_bytes(path, content)

        _verify_sources_before_manifest(evidence, claim_path, claim_bytes)
        if _file_fingerprint(test_path, "held-out test") != evidence["test_fingerprint"]:
            raise RuntimeError("held-out test changed during test opening")

        outputs = {
            "test_metrics": _receipt(metrics_bytes, "artifacts/test_metrics.json"),
            "test_scores": _receipt(
                compressed_scores, "predictions/test_scores.csv.gz", rows=len(test),
                columns=list(PREDICTION_COLUMNS), sha256_compressed=sha256_bytes(compressed_scores),
                sha256_canonical_csv=sha256_bytes(canonical_scores),
            ),
            "plots": {path: _receipt(content, path) for path, content in plots.items()},
        }
        binding = evidence.get("binding")
        if not isinstance(binding, DevelopmentInput):
            raise RuntimeError("validated development binding is unavailable")
        manifest = {
            "schema_version": "1.0",
            "run_type": "xgboost_test",
            "status": "succeeded",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "claim": {
                "path": "state/test_opening.json",
                "sha256": sha256_bytes(claim_bytes),
                "size_bytes": len(claim_bytes),
            },
            "development_run": {
                "path": str(resolved_development),
                "manifest_sha256": evidence["manifest_sha256"],
            },
            "upstream_run": {
                "path": str(binding.input_run),
                "manifest_sha256": binding.manifest_sha256,
                "protocol": dict(binding.upstream_protocol),
            },
            "protocol": {
                "schema_version": evidence["protocol"].raw["schema_version"],
                "sha256": sha256_bytes(evidence["protocol_bytes"]),
            },
            "code": {**_git_identity(project_root), "sha256": _code_sha256(project_root)},
            "software": _software_versions(),
            "model": _receipt(evidence["model_bytes"], "model/model.json"),
            "test_input": {
                **dict(test_receipt),
                "resolved_path": str(test_path.resolve(strict=True)),
            },
            "features": list(MODEL_FEATURES),
            "working_points": dict(points),
            "counts": {"test": len(test)},
            "schema": {
                "input_columns": list(OUTPUT_COLUMNS),
                "model_features": list(MODEL_FEATURES),
                "prediction_columns": list(PREDICTION_COLUMNS),
            },
            "outputs": outputs,
        }
        transaction.publish_manifest(manifest, "artifacts/manifest.json")
        return manifest
