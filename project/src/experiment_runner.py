from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

import json
import os
import shutil

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import roc_auc_score, roc_curve

from .experiment_config import ExperimentConfig, FEATURE_PROFILES
from .full_training_evaluation import build_working_points
from .full_training_policy import (
    assign_development_folds,
    class_balanced_training_weights,
    identity_collision_summary,
)
from .provenance import software_versions
from .validation import weighted_ks_distance


TRAIN_ROLE = "higgsml-flexible-xgboost-training"
PREDICT_ROLE = "higgsml-flexible-xgboost-prediction"
TEST_ROLE = "higgsml-flexible-xgboost-test-evaluation"
GENERIC_ROLES = {TRAIN_ROLE, PREDICT_ROLE, TEST_ROLE}
_REQUIRED_TRAINING_COLUMNS = {
    "label",
    "split",
    "physical_weight",
    "channelNumber",
    "eventNumber",
    "m4l",
}


@dataclass(frozen=True)
class FoldResult:
    fold: int
    weighted_auc: float
    unweighted_auc: float
    best_iteration: int


@dataclass(frozen=True)
class CandidateResult:
    index: int
    parameters: Mapping[str, object]
    folds: tuple[FoldResult, ...]
    mean_weighted_auc: float
    standard_error_weighted_auc: float
    oof_scores: pd.Series


@dataclass(frozen=True)
class TrainingOutcome:
    model: Any
    candidates: tuple[CandidateResult, ...]
    selected: CandidateResult
    final_parameters: Mapping[str, object]
    oof_frame: pd.DataFrame
    working_points: Mapping[str, Mapping[str, object]]
    metrics: Mapping[str, object]


ModelFactory = Callable[..., Any]


def load_training_frame(path: str | Path) -> pd.DataFrame:
    input_path = _regular_file(path, "training input")
    return pd.read_csv(input_path)


def validate_training_frame(
    frame: pd.DataFrame, features: Sequence[str], *, require_test: bool = True
) -> None:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("training input must be a non-empty DataFrame")
    if not frame.index.is_unique:
        raise ValueError("training input index must be unique")
    required = _REQUIRED_TRAINING_COLUMNS | set(features)
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"training input is missing required columns: {missing}")
    expected_splits = {"train", "validation", "test"} if require_test else {
        "train",
        "validation",
    }
    if set(frame["split"]) != expected_splits:
        raise ValueError(f"training splits must be exactly {sorted(expected_splits)}")
    if set(frame["label"]) != {0, 1}:
        raise ValueError("training labels must be exactly 0 and 1")
    collisions = identity_collision_summary(frame)
    if collisions["cross_label_groups"] or collisions["cross_split_groups"]:
        raise ValueError("identifier collision groups may not span labels or splits")
    for split in expected_splits:
        if set(frame.loc[frame["split"] == split, "label"]) != {0, 1}:
            raise ValueError(f"{split} split must contain labels 0 and 1")
    development = frame.loc[frame["split"] != "test"]
    numeric = development.loc[
        :, [*features, "physical_weight", "channelNumber", "eventNumber", "m4l"]
    ].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("development input contains NaN or infinity")
    if np.abs(development["physical_weight"].to_numpy(dtype=float)).sum() <= 0:
        raise ValueError("development physical weights must have positive absolute sum")


def train_experiment(
    frame: pd.DataFrame,
    config: ExperimentConfig,
    *,
    model_factory: ModelFactory | None = None,
) -> TrainingOutcome:
    validate_training_frame(frame, config.features)
    development = frame.loc[frame["split"] != "test"]
    folds = assign_development_folds(development, folds=config.folds)
    factory = model_factory or _xgboost_factory
    results: list[CandidateResult] = []
    for index, candidate in enumerate(config.candidates()):
        oof = pd.Series(np.nan, index=development.index, dtype=float, name="oof_score")
        fold_results: list[FoldResult] = []
        for fold in range(config.folds):
            fitting = development.loc[folds != fold]
            evaluation = development.loc[folds == fold]
            parameters = _model_parameters(config, candidate, final=False)
            classifier = factory(**parameters)
            fitting_weights = class_balanced_training_weights(fitting)
            evaluation_weights = np.abs(
                evaluation["physical_weight"].to_numpy(dtype=float)
            )
            classifier.fit(
                fitting.loc[:, config.features],
                fitting["label"],
                sample_weight=fitting_weights,
                eval_set=[(evaluation.loc[:, config.features], evaluation["label"])],
                sample_weight_eval_set=[evaluation_weights],
                verbose=False,
            )
            scores = _positive_scores(classifier, evaluation, config.features)
            oof.loc[evaluation.index] = scores
            best_iteration = getattr(classifier, "best_iteration", None)
            if not isinstance(best_iteration, (int, np.integer)):
                best_iteration = config.n_estimators - 1
            fold_results.append(
                FoldResult(
                    fold=fold,
                    weighted_auc=float(
                        roc_auc_score(
                            evaluation["label"],
                            scores,
                            sample_weight=evaluation_weights,
                        )
                    ),
                    unweighted_auc=float(roc_auc_score(evaluation["label"], scores)),
                    best_iteration=int(best_iteration),
                )
            )
        if oof.isna().any():
            raise RuntimeError("OOF predictions do not cover every development row")
        weighted = np.asarray([item.weighted_auc for item in fold_results], dtype=float)
        results.append(
            CandidateResult(
                index=index,
                parameters=dict(candidate),
                folds=tuple(fold_results),
                mean_weighted_auc=float(weighted.mean()),
                standard_error_weighted_auc=float(
                    weighted.std(ddof=1) / np.sqrt(config.folds)
                    if config.folds > 1
                    else 0.0
                ),
                oof_scores=oof,
            )
        )
    selected = max(results, key=lambda item: item.mean_weighted_auc)
    final_parameters = _model_parameters(config, selected.parameters, final=True)
    final_parameters["n_estimators"] = _final_tree_count(selected)
    model = factory(**final_parameters)
    model.fit(
        development.loc[:, config.features],
        development["label"],
        sample_weight=class_balanced_training_weights(development),
        verbose=False,
    )

    audit_columns = [
        name
        for name in (
            "channelNumber",
            "eventNumber",
            "split",
            "label",
            "physical_weight",
            "m4l",
        )
        if name in development.columns
    ]
    oof_frame = development.loc[:, audit_columns].copy()
    oof_frame["development_fold"] = folds.loc[oof_frame.index].astype(int)
    oof_frame["oof_score"] = selected.oof_scores.loc[oof_frame.index]
    working_points = build_working_points(oof_frame, config.working_points)
    metrics = _development_metrics(
        oof_frame, selected, final_parameters, working_points, config
    )
    return TrainingOutcome(
        model=model,
        candidates=tuple(results),
        selected=selected,
        final_parameters=dict(final_parameters),
        oof_frame=oof_frame,
        working_points=working_points,
        metrics=metrics,
    )


def run_training(
    *,
    input_path: str | Path,
    output_dir: str | Path,
    config: ExperimentConfig,
    overwrite: bool = False,
    project_root: str | Path | None = None,
    cli_overrides: Mapping[str, object] | None = None,
) -> Path:
    source = _regular_file(input_path, "training input")
    with OutputTransaction(
        output_dir, overwrite=overwrite, project_root=project_root
    ) as output:
        source_record = _source_record(source)
        frame = pd.read_csv(source)
        outcome = train_experiment(frame, config)
        _assert_source_unchanged(source, source_record, "training input")
        outcome.model.save_model(output / "model.json")
        (output / "effective_config.yaml").write_text(
            yaml.safe_dump(config.as_dict(), sort_keys=False), encoding="utf-8"
        )
        _write_json(output / "metrics.json", outcome.metrics)
        _candidate_table(outcome.candidates).to_csv(
            output / "cv_results.csv", index=False
        )
        outcome.oof_frame.to_csv(output / "oof_scores.csv.gz", index=False)
        _save_training_plots(outcome, output / "plots")
        manifest = _manifest(
            role=TRAIN_ROLE,
            input_path=source,
            output=output,
            extra={
                "feature_profile": config.feature_profile,
                "features": list(config.features),
                "effective_config": config.as_dict(),
                "cli_overrides": dict(cli_overrides or {}),
                "candidate_count": len(outcome.candidates),
                "selected_candidate": outcome.selected.index,
                "selected_parameters": dict(outcome.final_parameters),
                "working_points": outcome.working_points,
                "test_opened": False,
            },
        )
        _assert_source_unchanged(source, source_record, "training input")
        _write_json(output / "manifest.json", manifest)
    return Path(output_dir)


def run_prediction(
    *,
    input_path: str | Path,
    model_dir: str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
    project_root: str | Path | None = None,
) -> Path:
    source = _regular_file(input_path, "prediction input")
    with OutputTransaction(
        output_dir, overwrite=overwrite, project_root=project_root
    ) as output:
        source_record = _source_record(source)
        model_root, training_manifest = _load_training_manifest(model_dir)
        model_record = _source_record(model_root / "model.json")
        frame = pd.read_csv(source)
        if "split" in frame and frame["split"].eq("test").any():
            raise ValueError("predict refuses split=test rows; use evaluate-test")
        features = _manifest_features(training_manifest)
        _validate_prediction_columns(frame, features)
        model = _load_model(model_root / "model.json")
        scored = frame.copy()
        scored["xgb_score"] = _positive_scores(model, frame, features)
        scored.to_csv(output / "predictions.csv.gz", index=False)
        manifest = _manifest(
            role=PREDICT_ROLE,
            input_path=source,
            output=output,
            extra={
                "training_run": _source_record(model_root / "manifest.json"),
                "model": _source_record(model_root / "model.json"),
                "features": list(features),
                "rows": len(scored),
            },
        )
        _assert_source_unchanged(source, source_record, "prediction input")
        _assert_source_unchanged(model_root / "model.json", model_record, "model")
        _write_json(output / "manifest.json", manifest)
    return Path(output_dir)


def run_test_evaluation(
    *,
    input_path: str | Path,
    model_dir: str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
    project_root: str | Path | None = None,
) -> Path:
    source = _regular_file(input_path, "test input")
    with OutputTransaction(
        output_dir, overwrite=overwrite, project_root=project_root
    ) as output:
        source_record = _source_record(source)
        model_root, training_manifest = _load_training_manifest(model_dir)
        model_record = _source_record(model_root / "model.json")
        frame = pd.read_csv(source)
        features = _manifest_features(training_manifest)
        validate_training_frame(frame, features)
        test = frame.loc[frame["split"] == "test"].copy()
        _validate_test_frame(test, features)
        model = _load_model(model_root / "model.json")
        test["xgb_score"] = _positive_scores(model, test, features)
        points = training_manifest.get("working_points")
        if not isinstance(points, Mapping) or not points:
            raise ValueError("training manifest is missing working_points")
        metrics = _test_metrics(test, points)
        test.to_csv(output / "test_scores.csv.gz", index=False)
        _write_json(output / "metrics.json", metrics)
        _save_test_plots(test, output / "plots")
        manifest = _manifest(
            role=TEST_ROLE,
            input_path=source,
            output=output,
            extra={
                "training_run": _source_record(model_root / "manifest.json"),
                "model": _source_record(model_root / "model.json"),
                "features": list(features),
                "working_points": points,
                "test_rows": len(test),
                "test_opened": True,
            },
        )
        _assert_source_unchanged(source, source_record, "test input")
        _assert_source_unchanged(model_root / "model.json", model_record, "model")
        _write_json(output / "manifest.json", manifest)
    return Path(output_dir)


class OutputTransaction(AbstractContextManager[Path]):
    def __init__(
        self,
        target: str | Path,
        *,
        overwrite: bool,
        project_root: str | Path | None,
    ) -> None:
        self.target = Path(target)
        self.overwrite = overwrite
        self.project_root = (
            Path(project_root).resolve() if project_root is not None else Path.cwd().resolve()
        )
        self.staging: Path | None = None

    def __enter__(self) -> Path:
        _validate_output_target(self.target, self.project_root)
        if self.target.exists() or self.target.is_symlink():
            if not self.overwrite:
                raise FileExistsError(f"output directory already exists: {self.target}")
            _validate_overwrite_target(self.target)
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.staging = self.target.with_name(
            f".{self.target.name}.staging-{uuid4().hex}"
        )
        self.staging.mkdir()
        return self.staging

    def __exit__(self, exc_type, exc, traceback) -> bool:
        assert self.staging is not None
        if exc_type is not None:
            shutil.rmtree(self.staging, ignore_errors=True)
            return False
        backup: Path | None = None
        try:
            if self.target.exists():
                backup = self.target.with_name(
                    f".{self.target.name}.backup-{uuid4().hex}"
                )
                os.replace(self.target, backup)
            os.replace(self.staging, self.target)
            if backup is not None:
                shutil.rmtree(backup, ignore_errors=True)
        except Exception:
            if not self.target.exists() and backup is not None and backup.exists():
                os.replace(backup, self.target)
            if self.staging.exists():
                shutil.rmtree(self.staging, ignore_errors=True)
            raise
        return False


def _model_parameters(
    config: ExperimentConfig, candidate: Mapping[str, object], *, final: bool
) -> dict[str, object]:
    output = {
        **dict(candidate),
        "n_estimators": config.n_estimators,
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "random_state": config.random_seed,
        "n_jobs": config.n_jobs,
        "tree_method": config.tree_method,
    }
    if not final:
        output["early_stopping_rounds"] = config.early_stopping_rounds
    return output


def _xgboost_factory(**parameters: object):
    try:
        from xgboost import XGBClassifier
    except ImportError as error:
        raise RuntimeError("install requirements.txt before training") from error
    return XGBClassifier(**parameters)


def _load_model(path: Path):
    try:
        from xgboost import XGBClassifier
    except ImportError as error:
        raise RuntimeError("install requirements.txt before prediction") from error
    model = XGBClassifier()
    model.load_model(path)
    return model


def _positive_scores(model: Any, frame: pd.DataFrame, features: Sequence[str]) -> np.ndarray:
    _validate_finite_features(frame, features)
    probabilities = np.asarray(model.predict_proba(frame.loc[:, features]), dtype=float)
    if probabilities.ndim != 2 or probabilities.shape != (len(frame), 2):
        raise ValueError("classifier must return a two-column probability matrix")
    scores = probabilities[:, 1]
    if not np.isfinite(scores).all():
        raise ValueError("classifier returned NaN or infinity")
    return scores


def _final_tree_count(result: CandidateResult) -> int:
    counts = np.asarray([item.best_iteration + 1 for item in result.folds], dtype=float)
    return max(1, int(np.rint(np.median(counts))))


def _development_metrics(
    oof: pd.DataFrame,
    selected: CandidateResult,
    final_parameters: Mapping[str, object],
    working_points: Mapping[str, Mapping[str, object]],
    config: ExperimentConfig,
) -> dict[str, object]:
    weights = np.abs(oof["physical_weight"].to_numpy(dtype=float))
    return {
        "schema_version": "1.0",
        "status": "complete",
        "feature_profile": config.feature_profile,
        "features": list(config.features),
        "development_rows": len(oof),
        "test_opened": False,
        "selected_candidate": selected.index,
        "selected_parameters": dict(final_parameters),
        "weighted_oof_auc": float(
            roc_auc_score(oof["label"], oof["oof_score"], sample_weight=weights)
        ),
        "unweighted_oof_auc": float(roc_auc_score(oof["label"], oof["oof_score"])),
        "working_points": working_points,
        "background_mass_ks": _background_mass_ks(oof, working_points),
    }


def _background_mass_ks(
    frame: pd.DataFrame, points: Mapping[str, Mapping[str, object]]
) -> dict[str, float | None]:
    background = frame.loc[frame["label"] == 0]
    output: dict[str, float | None] = {}
    for name, point in points.items():
        selected = background.loc[
            background["oof_score"] >= float(point["threshold"])
        ]
        output[name] = (
            None
            if selected.empty
            else weighted_ks_distance(
                background["m4l"],
                selected["m4l"],
                background["physical_weight"],
                selected["physical_weight"],
            )
        )
    return output


def _test_metrics(
    test: pd.DataFrame, points: Mapping[str, Mapping[str, object]]
) -> dict[str, object]:
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
        "weighted_auc": float(
            roc_auc_score(test["label"], test["xgb_score"], sample_weight=weights)
        ),
        "unweighted_auc": float(roc_auc_score(test["label"], test["xgb_score"])),
        "working_points": working,
    }


def _candidate_table(candidates: Sequence[CandidateResult]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for candidate in candidates:
        for fold in candidate.folds:
            rows.append(
                {
                    "candidate": candidate.index,
                    **dict(candidate.parameters),
                    "fold": fold.fold,
                    "weighted_auc": fold.weighted_auc,
                    "unweighted_auc": fold.unweighted_auc,
                    "best_iteration": fold.best_iteration,
                    "mean_weighted_auc": candidate.mean_weighted_auc,
                    "standard_error_weighted_auc": candidate.standard_error_weighted_auc,
                }
            )
    return pd.DataFrame(rows)


def _save_training_plots(outcome: TrainingOutcome, output: Path) -> None:
    output.mkdir(parents=True)
    _save_score_plots(outcome.oof_frame, "oof_score", output)
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(8, 4.5))
    values = [item.mean_weighted_auc for item in outcome.candidates]
    errors = [item.standard_error_weighted_auc for item in outcome.candidates]
    axis.errorbar(range(len(values)), values, yerr=errors, fmt="o")
    axis.set(xlabel="Candidate index", ylabel="Mean weighted OOF AUC")
    figure.tight_layout()
    figure.savefig(output / "candidate_auc.png", dpi=160)
    plt.close(figure)


def _save_test_plots(test: pd.DataFrame, output: Path) -> None:
    output.mkdir(parents=True)
    _save_score_plots(test, "xgb_score", output)
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(6, 5))
    axis.scatter(test["m4l"], test["xgb_score"], s=5, alpha=0.25)
    axis.set(xlabel=r"$m_{4\ell}$ [GeV]", ylabel="XGBoost score")
    figure.tight_layout()
    figure.savefig(output / "score_vs_m4l.png", dpi=160)
    plt.close(figure)


def _save_score_plots(frame: pd.DataFrame, score: str, output: Path) -> None:
    import matplotlib.pyplot as plt

    weights = np.abs(frame["physical_weight"].to_numpy(dtype=float))
    fpr, tpr, _ = roc_curve(frame["label"], frame[score], sample_weight=weights)
    figure, axis = plt.subplots(figsize=(6, 5))
    axis.plot(fpr, tpr)
    axis.plot([0, 1], [0, 1], "--", color="0.6")
    axis.set(xlabel="Background efficiency", ylabel="Signal efficiency")
    figure.tight_layout()
    figure.savefig(output / "roc_curve.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(7, 4.5))
    for label, name, color in ((0, "ZZ*", "tab:blue"), (1, "Higgs", "tab:red")):
        axis.hist(
            frame.loc[frame["label"] == label, score],
            bins=np.linspace(0, 1, 31),
            density=True,
            histtype="step",
            color=color,
            label=name,
        )
    axis.set(xlabel="XGBoost score", ylabel="Normalized events")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output / "score_distribution.png", dpi=160)
    plt.close(figure)


def _manifest(
    *,
    role: str,
    input_path: Path,
    output: Path,
    extra: Mapping[str, object],
) -> dict[str, object]:
    outputs: dict[str, object] = {}
    for path in sorted(output.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        relative = str(path.relative_to(output)).replace("\\", "/")
        record = _source_record(path)
        record["path"] = relative
        outputs[relative] = record
    return {
        "schema_version": "1.0",
        "status": "complete",
        "role": role,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "software": software_versions(),
        "input": _source_record(input_path),
        "outputs": outputs,
        **dict(extra),
    }


def _source_record(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": str(path),
        "size_bytes": len(payload),
        "sha256": sha256(payload).hexdigest(),
    }


def _load_training_manifest(model_dir: str | Path) -> tuple[Path, dict[str, object]]:
    root = Path(model_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("model-dir must be a regular directory")
    manifest_path = _regular_file(root / "manifest.json", "training manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("role") != TRAIN_ROLE or manifest.get("status") != "complete":
        raise ValueError("model-dir is not a complete flexible training run")
    model_path = _regular_file(root / "model.json", "training model")
    recorded = manifest.get("outputs", {}).get("model.json", {})
    if recorded.get("sha256") != _source_record(model_path)["sha256"]:
        raise ValueError("training model hash does not match manifest")
    return root, manifest


def _manifest_features(manifest: Mapping[str, object]) -> tuple[str, ...]:
    profile = manifest.get("feature_profile")
    if profile not in FEATURE_PROFILES:
        raise ValueError("training manifest has invalid feature_profile")
    raw = manifest.get("features")
    if not isinstance(raw, list) or not raw or any(not isinstance(v, str) for v in raw):
        raise ValueError("training manifest has invalid features")
    if len(set(raw)) != len(raw):
        raise ValueError("training manifest features must be unique")
    registered = FEATURE_PROFILES[str(profile)]
    selected = tuple(raw)
    if selected != tuple(name for name in registered if name in selected):
        raise ValueError("training manifest features are not an ordered profile subset")
    return selected


def _validate_prediction_columns(frame: pd.DataFrame, features: Sequence[str]) -> None:
    missing = sorted(set(features) - set(frame.columns))
    if missing:
        raise ValueError(f"prediction input is missing model features: {missing}")
    _validate_finite_features(frame, features)


def _validate_finite_features(frame: pd.DataFrame, features: Sequence[str]) -> None:
    values = frame.loc[:, features].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("model features contain NaN or infinity")


def _validate_test_frame(frame: pd.DataFrame, features: Sequence[str]) -> None:
    _validate_finite_features(frame, features)
    values = frame.loc[:, ["physical_weight", "m4l"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("test weights or mass contain NaN or infinity")
    for label in (0, 1):
        weights = np.abs(
            frame.loc[frame["label"] == label, "physical_weight"].to_numpy(dtype=float)
        )
        if weights.sum() <= 0:
            raise ValueError("each test class must have positive absolute physical weight")


def _regular_file(path: str | Path, name: str) -> Path:
    resolved = Path(path)
    if resolved.is_symlink() or not resolved.is_file():
        raise ValueError(f"{name} must be a regular file: {resolved}")
    return resolved


def _assert_source_unchanged(
    path: Path, expected: Mapping[str, object], name: str
) -> None:
    current = _source_record(_regular_file(path, name))
    if (
        current["size_bytes"] != expected["size_bytes"]
        or current["sha256"] != expected["sha256"]
    ):
        raise RuntimeError(f"{name} changed during the operation")


def _validate_output_target(target: Path, project_root: Path) -> None:
    current = target
    while True:
        if current.is_symlink():
            raise ValueError("output directory and parents may not be symlinks")
        if current == current.parent:
            break
        current = current.parent
    resolved = target.resolve()
    if resolved == project_root:
        raise ValueError(f"output directory is protected: {target}")
    protected_trees = [
        project_root / "src",
        project_root / "scripts",
        project_root / "config",
        project_root / "data",
        project_root / "tests",
    ]
    if any(
        resolved == item.resolve() or item.resolve() in resolved.parents
        for item in protected_trees
    ):
        raise ValueError(f"output directory is protected: {target}")


def _validate_overwrite_target(target: Path) -> None:
    if target.is_symlink() or not target.is_dir():
        raise ValueError("overwrite target must be a regular directory")
    manifest_path = target / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("overwrite requires a recognized generic experiment manifest")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("overwrite manifest is invalid") from error
    if (
        manifest.get("schema_version") != "1.0"
        or manifest.get("status") != "complete"
        or manifest.get("role") not in GENERIC_ROLES
    ):
        raise ValueError("overwrite refuses non-generic or frozen output directories")


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
