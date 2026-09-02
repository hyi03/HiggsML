"""Application service for one immutable Angular19 development run."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
from importlib import metadata
import io
from pathlib import Path
import platform
import subprocess
from typing import Any, Mapping

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from ..artifacts.manifest import canonical_json_bytes
from ..artifacts.transaction import RunTransaction
from ..config import XGBoostProtocol, load_xgboost_protocol
from .dataset import (
    DevelopmentInput,
    load_development_input,
    read_regular_bytes,
    validate_development_frame,
    verify_development_input,
)
from .evaluation import (
    OOF_COLUMNS,
    background_mass_ks,
    build_working_points,
    weighted_oof_auc,
)
from .folds import assign_development_folds, class_balanced_training_weights
from .model import (
    CandidateResult,
    FoldResult,
    best_iteration,
    default_model_factory,
    final_tree_count,
    model_json_bytes,
    model_parameters,
    positive_scores,
)
from .qualification import qualify


ModelFactory = Callable[..., Any]
ProgressFactory = Callable[..., object]


@dataclass(frozen=True)
class DevelopmentEvidence:
    candidates: tuple[CandidateResult, ...]
    selected: CandidateResult
    final_parameters: Mapping[str, object]
    oof_frame: pd.DataFrame
    working_points: Mapping[str, Mapping[str, object]]
    weighted_oof_auc: float
    background_mass_ks: Mapping[str, float | None]
    qualification: Mapping[str, object]


def build_development_evidence(
    frame: pd.DataFrame,
    protocol: XGBoostProtocol,
    *,
    model_factory: ModelFactory | None = None,
    show_progress: bool = False,
    progress_factory: ProgressFactory | None = None,
) -> DevelopmentEvidence:
    validate_development_frame(frame)
    features = protocol.features
    folds_count = int(protocol.common["folds"])
    folds = assign_development_folds(frame, folds_count)
    factory = model_factory or default_model_factory
    oof = pd.Series(np.nan, index=frame.index, dtype=float, name="oof_score")
    fold_results: list[FoldResult] = []
    parameters = model_parameters(protocol, final=False)
    for fold in range(folds_count):
        fitting = frame.loc[folds != fold]
        evaluation = frame.loc[folds == fold]
        if fitting.empty or evaluation.empty:
            raise ValueError(f"development fold {fold} has no fitting or evaluation rows")
        fitting_weights = class_balanced_training_weights(fitting)
        evaluation_weights = np.abs(evaluation["physical_weight"].to_numpy(dtype=float))
        progress = _fit_progress(
            int(protocol.common["n_estimators"]),
            f"Candidate 1/1 fold {fold + 1}/{folds_count}",
            leave=False,
            show_progress=show_progress,
            progress_factory=progress_factory,
        )
        classifier_parameters = dict(parameters)
        if progress is not None:
            classifier_parameters["callbacks"] = [progress]
        try:
            classifier = factory(**classifier_parameters)
            classifier.fit(
                fitting.loc[:, features],
                fitting["label"],
                sample_weight=fitting_weights,
                eval_set=[(evaluation.loc[:, features], evaluation["label"])],
                sample_weight_eval_set=[evaluation_weights],
                verbose=False,
            )
        finally:
            if progress is not None:
                progress.close()
        scores = positive_scores(classifier, evaluation, features)
        if oof.loc[evaluation.index].notna().any():
            raise RuntimeError("OOF predictions overlap")
        oof.loc[evaluation.index] = scores
        fold_results.append(
            FoldResult(
                fold=fold,
                weighted_auc=float(
                    roc_auc_score(evaluation["label"], scores, sample_weight=evaluation_weights)
                ),
                unweighted_auc=float(roc_auc_score(evaluation["label"], scores)),
                best_iteration=best_iteration(
                    classifier, int(protocol.common["n_estimators"])
                ),
            )
        )
    if oof.isna().any() or not np.isfinite(oof.to_numpy(dtype=float)).all():
        raise RuntimeError("OOF predictions must cover every development row with finite scores")
    weighted_fold_aucs = np.asarray([item.weighted_auc for item in fold_results], dtype=float)
    candidate = CandidateResult(
        index=0,
        parameters=dict(protocol.candidate),
        folds=tuple(fold_results),
        mean_weighted_auc=float(weighted_fold_aucs.mean()),
        standard_error_weighted_auc=float(
            weighted_fold_aucs.std(ddof=1) / np.sqrt(folds_count)
        ),
        oof_scores=oof.copy(),
    )
    selected = max((candidate,), key=lambda item: item.mean_weighted_auc)
    final_parameters = model_parameters(
        protocol, final=True, tree_count=final_tree_count(selected)
    )
    oof_frame = frame.loc[
        :, ["channelNumber", "eventNumber", "split", "label", "physical_weight", "m4l"]
    ].copy()
    oof_frame["development_fold"] = folds.astype(int)
    oof_frame["oof_score"] = selected.oof_scores
    oof_frame = oof_frame.loc[:, OOF_COLUMNS]
    points = build_working_points(oof_frame, protocol.working_points)
    auc = weighted_oof_auc(oof_frame)
    ks = background_mass_ks(oof_frame, points)
    qualification = qualify(
        oof_frame,
        auc,
        points,
        ks,
        protocol.qualification,
        expected_development=frame,
    )
    return DevelopmentEvidence(
        candidates=(candidate,),
        selected=selected,
        final_parameters=final_parameters,
        oof_frame=oof_frame,
        working_points=points,
        weighted_oof_auc=auc,
        background_mass_ks=ks,
        qualification=qualification,
    )


def fit_final_model(
    frame: pd.DataFrame,
    protocol: XGBoostProtocol,
    evidence: DevelopmentEvidence,
    *,
    model_factory: ModelFactory | None = None,
    show_progress: bool = False,
    progress_factory: ProgressFactory | None = None,
) -> Any:
    if not evidence.qualification["eligible"]:
        raise ValueError("final model cannot be fit for an ineligible development run")
    factory = model_factory or default_model_factory
    progress = _fit_progress(
        int(evidence.final_parameters["n_estimators"]),
        "Final model",
        leave=True,
        show_progress=show_progress,
        progress_factory=progress_factory,
    )
    parameters = dict(evidence.final_parameters)
    if progress is not None:
        parameters["callbacks"] = [progress]
    try:
        model = factory(**parameters)
        model.fit(
            frame.loc[:, protocol.features],
            frame["label"],
            sample_weight=class_balanced_training_weights(frame),
            verbose=False,
        )
    finally:
        if progress is not None:
            progress.close()
    return model


def _fit_progress(
    total_rounds: int,
    description: str,
    *,
    leave: bool,
    show_progress: bool,
    progress_factory: ProgressFactory | None,
):
    if not show_progress:
        return None
    from ..progress import TrainingProgress

    options: dict[str, object] = {}
    if progress_factory is not None:
        options["progress_factory"] = progress_factory
    return TrainingProgress(
        total_rounds, description=description, leave=leave, **options
    )


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _csv_bytes(frame: pd.DataFrame) -> tuple[bytes, bytes]:
    canonical = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return canonical, gzip.compress(canonical, compresslevel=9, mtime=0)


def _receipt(content: bytes, *, path: str, rows: int | None = None, columns=None) -> dict[str, object]:
    output: dict[str, object] = {
        "path": path,
        "sha256": _sha256(content),
        "size_bytes": len(content),
    }
    if rows is not None:
        output["rows"] = rows
    if columns is not None:
        output["columns"] = list(columns)
    return output


def _candidate_frame(evidence: DevelopmentEvidence) -> pd.DataFrame:
    rows = []
    for candidate in evidence.candidates:
        rows.append(
            {
                "candidate_index": candidate.index,
                **dict(candidate.parameters),
                "mean_weighted_auc": candidate.mean_weighted_auc,
                "standard_error_weighted_auc": candidate.standard_error_weighted_auc,
                "selected": candidate.index == evidence.selected.index,
            }
        )
    return pd.DataFrame(rows)


def _fold_frame(evidence: DevelopmentEvidence) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate_index": candidate.index,
                "fold": fold.fold,
                "weighted_auc": fold.weighted_auc,
                "unweighted_auc": fold.unweighted_auc,
                "best_iteration": fold.best_iteration,
            }
            for candidate in evidence.candidates
            for fold in candidate.folds
        ]
    )


def _git_identity(project_root: Path) -> dict[str, object]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project_root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], cwd=project_root, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("unable to bind development run to Git code identity") from exc
    return {"commit": commit, "worktree_dirty": dirty}


def _code_sha256(project_root: Path) -> str:
    digest = hashlib.sha256()
    sources = {
        project_root / "src" / "__init__.py",
        project_root / "src" / "config.py",
        project_root / "src" / "progress.py",
        project_root / "src" / "validation.py",
    }
    for package in ("artifacts", "cli", "domain", "preprocessing", "training"):
        sources.update((project_root / "src" / package).glob("*.py"))
    for path in sorted(sources, key=lambda item: item.as_posix()):
        relative = path.relative_to(project_root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _software_versions() -> dict[str, str]:
    distributions = {
        "matplotlib": "matplotlib", "numpy": "numpy", "pandas": "pandas", "pyyaml": "PyYAML",
        "scikit_learn": "scikit-learn", "xgboost": "xgboost",
    }
    versions = {"python": platform.python_version()}
    for name, distribution in distributions.items():
        try:
            versions[name] = metadata.version(distribution)
        except metadata.PackageNotFoundError as exc:
            raise RuntimeError(f"required distribution is not installed: {distribution}") from exc
    return versions


def _plot_bytes(evidence: DevelopmentEvidence) -> dict[str, bytes]:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    output: dict[str, bytes] = {}
    figure, axis = plt.subplots()
    for label, name in ((0, "ZZ"), (1, "Higgs")):
        values = evidence.oof_frame.loc[evidence.oof_frame["label"] == label, "oof_score"]
        axis.hist(values, bins=20, histtype="step", label=name)
    axis.set_xlabel("OOF score")
    axis.set_ylabel("Events")
    axis.legend()
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=120)
    plt.close(figure)
    output["plots/oof_scores.png"] = buffer.getvalue()
    return output


def _upstream_payload(binding: DevelopmentInput) -> dict[str, object]:
    manifest = binding.manifest
    development = manifest["outputs"]["development"]
    return {
        "path": str(binding.input_run),
        "manifest": {
            "path": "artifacts/manifest.json",
            "sha256": binding.manifest_sha256,
        },
        "protocol": dict(binding.upstream_protocol),
        "run_config": dict(binding.upstream_run_config),
        "development": {
            "path": development["path"],
            "sha256_compressed": development["sha256_compressed"],
            "sha256_canonical_csv": development["sha256_canonical_csv"],
        },
    }


def run_development(
    *,
    input_run: str | Path,
    protocol_path: str | Path,
    run_dir: str | Path,
    model_factory: ModelFactory | None = None,
    show_progress: bool = False,
    progress_factory: ProgressFactory | None = None,
) -> Mapping[str, object]:
    destination = Path(run_dir).absolute()
    if destination.parent.name != "runs":
        raise ValueError("run directory must be a direct child of a named runs root")
    project_root = Path(__file__).resolve().parents[2]
    with RunTransaction(destination, runs_root=destination.parent) as transaction:
        protocol_source = Path(protocol_path).absolute()
        protocol_bytes = read_regular_bytes(protocol_source, "XGBoost protocol")
        protocol = load_xgboost_protocol(protocol_source)
        binding = load_development_input(input_run)
        evidence = build_development_evidence(
            binding.frame,
            protocol,
            model_factory=model_factory,
            show_progress=show_progress,
            progress_factory=progress_factory,
        )
        model = (
            fit_final_model(
                binding.frame,
                protocol,
                evidence,
                model_factory=model_factory,
                show_progress=show_progress,
                progress_factory=progress_factory,
            )
            if evidence.qualification["eligible"]
            else None
        )

        candidate_canonical, _ = _csv_bytes(_candidate_frame(evidence))
        fold_canonical, _ = _csv_bytes(_fold_frame(evidence))
        oof_canonical, oof_compressed = _csv_bytes(evidence.oof_frame)
        qualification_bytes = canonical_json_bytes(evidence.qualification)
        points_bytes = canonical_json_bytes(evidence.working_points)
        transaction.write_bytes("config.yaml", protocol_bytes)
        transaction.write_bytes("artifacts/candidate_metrics.csv", candidate_canonical)
        transaction.write_bytes("artifacts/fold_metrics.csv", fold_canonical)
        transaction.write_bytes("artifacts/qualification.json", qualification_bytes)
        transaction.write_bytes("artifacts/working_points.json", points_bytes)
        transaction.write_bytes("predictions/oof_scores.csv.gz", oof_compressed)
        plot_outputs = _plot_bytes(evidence)
        for path, content in plot_outputs.items():
            transaction.write_bytes(path, content)
        model_bytes = None if model is None else model_json_bytes(model)
        if model_bytes is not None:
            transaction.write_bytes("model/model.json", model_bytes)

        verify_development_input(binding)
        if read_regular_bytes(protocol_source, "XGBoost protocol") != protocol_bytes:
            raise RuntimeError("XGBoost protocol changed during development")

        outputs: dict[str, object] = {
            "candidate_metrics": _receipt(
                candidate_canonical, path="artifacts/candidate_metrics.csv",
                rows=len(evidence.candidates), columns=_candidate_frame(evidence).columns,
            ),
            "fold_metrics": _receipt(
                fold_canonical, path="artifacts/fold_metrics.csv",
                rows=sum(len(item.folds) for item in evidence.candidates),
                columns=_fold_frame(evidence).columns,
            ),
            "qualification": _receipt(
                qualification_bytes, path="artifacts/qualification.json"
            ),
            "working_points": _receipt(
                points_bytes, path="artifacts/working_points.json"
            ),
            "oof_scores": {
                **_receipt(
                    oof_compressed, path="predictions/oof_scores.csv.gz",
                    rows=len(evidence.oof_frame), columns=OOF_COLUMNS,
                ),
                "sha256_compressed": _sha256(oof_compressed),
                "sha256_canonical_csv": _sha256(oof_canonical),
            },
            "plots": {
                path: _receipt(content, path=path) for path, content in plot_outputs.items()
            },
            "model": (
                None
                if model_bytes is None
                else _receipt(model_bytes, path="model/model.json")
            ),
        }
        manifest: dict[str, object] = {
            "schema_version": "1.0",
            "run_type": "xgboost_development",
            "status": evidence.qualification["status"],
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "test_opened": False,
            "protocol": {
                "path": str(protocol_source.resolve(strict=True)),
                "schema_version": protocol.raw["schema_version"],
                "sha256": _sha256(protocol_bytes),
            },
            "code": {**_git_identity(project_root), "sha256": _code_sha256(project_root)},
            "software": _software_versions(),
            "upstream_run": _upstream_payload(binding),
            "candidate": dict(protocol.candidate),
            "selected_candidate": evidence.selected.index,
            "final_parameters": dict(evidence.final_parameters),
            "working_points": evidence.working_points,
            "qualification": evidence.qualification,
            "outputs": outputs,
            "counts": {"development": len(binding.frame), "oof": len(evidence.oof_frame)},
            "schema": {
                "model_features": list(protocol.features),
                "input_columns": list(binding.frame.columns),
                "oof_columns": list(OOF_COLUMNS),
            },
        }
        transaction.publish_manifest(manifest, "artifacts/manifest.json")
        return manifest
