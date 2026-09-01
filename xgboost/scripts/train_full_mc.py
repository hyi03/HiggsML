from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from src.features import FEATURES
from src.full_training_evaluation import build_working_points, evaluate_full_training
from src.full_training_model import (
    cross_validate_candidates,
    effective_parameters,
    final_tree_count,
    fit_final_model,
    score_model,
)
from src.full_training_plots import save_full_training_plots
from src.full_training_policy import (
    identity_collision_summary,
    load_training_policy,
    validate_mc_frame,
)
from src.full_training_run import (
    PLOT_NAMES,
    assert_input_hashes_unchanged,
    claim_training_output,
    load_training_mc_frame,
    publish_training_manifest,
    record_training_failure,
    resolve_training_input,
    resolve_training_output,
    write_training_artifacts,
)
from src.provenance import software_versions


_AUDIT_COLUMNS = (
    "channelNumber",
    "eventNumber",
    "split",
    "label",
    "physical_weight",
    "m4l",
    "mZ1",
    "mZ2",
    "pt4l",
)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Train the isolated Task 4B full-MC classifier"
    )
    parser.add_argument("--input-run", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    config_bytes = config_path.read_bytes()
    policy = load_training_policy(config_path)
    project_root = Path(__file__).resolve().parents[1]
    working_directory = Path.cwd()
    resolve_training_output(
        project_root=project_root,
        working_directory=working_directory,
        input_run=args.input_run,
        run_dir=args.run_dir,
    )
    training_input = resolve_training_input(args.input_run)
    layout = resolve_training_output(
        project_root=project_root,
        working_directory=working_directory,
        input_run=training_input.input_run,
        run_dir=args.run_dir,
    )
    layout = claim_training_output(layout)
    try:
        frame = load_training_mc_frame(training_input)
        validate_mc_frame(frame)
        if len(frame) != training_input.expected_rows:
            raise ValueError(
                "Task 4A summary selected event count does not match MC rows"
            )

        selection = cross_validate_candidates(frame, policy)
        selected_tree_count = final_tree_count(selection.selected)
        oof = _oof_frame(frame, selection)
        working_points = build_working_points(oof, policy.working_points)
        parameters = effective_parameters(selection, policy, final=True)

        model = fit_final_model(frame, selection, policy)
        development = frame.loc[frame["split"] != "test"]
        final_development = _scored_frame(model, development)
        test_rows = frame.loc[frame["split"] == "test"]
        test = _scored_frame(model, test_rows)

        selection_metadata = {
            "candidate": selection.selected.candidate.name,
            "final_tree_count": selected_tree_count,
        }
        metrics = evaluate_full_training(
            oof,
            final_development,
            test,
            working_points,
            policy,
            selection=selection_metadata,
        )
        plot_artifacts = _plot_bytes(
            oof,
            test,
            selection.candidates,
            model,
            working_points,
            policy,
        )

        receipt = write_training_artifacts(
            layout,
            config_source=config_path,
            config_bytes=config_bytes,
            model=_artifact_model(model),
            json_artifacts={
                "weight_summary.json": _weight_summary(frame),
                "metrics.json": metrics,
                "working_points.json": working_points,
            },
            artifact_tables={"cv_results.csv": _cv_table(selection.candidates)},
            prediction_frames={
                "oof_scores.csv.gz": oof,
                "test_scores.csv.gz": test,
            },
            plot_artifacts=plot_artifacts,
        )

        if config_path.read_bytes() != config_bytes:
            raise RuntimeError("training config changed during training")
        assert_input_hashes_unchanged(training_input)
        warnings = _warnings(metrics)
        summary = _summary_text(
            selection=selection,
            final_tree_count_value=selected_tree_count,
            metrics=metrics,
            working_points=working_points,
            warnings=warnings,
            output_path=layout.run_dir,
        )
        publish_training_manifest(
            layout,
            training_input,
            receipt=receipt,
            software=software_versions(),
            effective_parameters=parameters,
            features=FEATURES,
            sampling_fractions={"higgs": 1.0, "zz": 1.0},
            weight_policy={
                "training": "class-balanced normalized absolute physical weight",
                "evaluation": "absolute physical weight",
                "physical_yields": "signed physical weight",
                "recomputed_for_each_fitting_subset": True,
            },
            fold_policy={
                "folds": policy.folds,
                "assignment": "blake2b(channelNumber,eventNumber)",
                "development_splits": ["train", "validation"],
                "independent_test_split": "test",
            },
            selected_model={
                **selection_metadata,
                "mean_weighted_auc": selection.selected.mean_weighted_auc,
                "standard_error_weighted_auc": (
                    selection.selected.standard_error_weighted_auc
                ),
            },
            working_points=working_points,
            warnings=warnings,
        )
    except Exception as error:
        record_training_failure(layout, error)
        raise

    _display_summary(summary)


def _summary_text(
    *,
    selection,
    final_tree_count_value: int,
    metrics: dict[str, object],
    working_points,
    warnings: dict[str, object],
    output_path: Path,
) -> str:
    lines = [
        f"selected candidate: {selection.selected.candidate.name}",
        f"final tree count: {final_tree_count_value}",
        f"OOF AUC: {metrics['development_oof']['weighted_auc']:.6f}",
        f"test AUC: {metrics['test']['weighted_auc']:.6f}",
    ]
    lines.extend(
        f"{name} threshold: {working_points[name]['threshold']:.12g}"
        for name in ("loose", "medium", "tight")
    )
    lines.extend(
        [
            f"warning status: {str(warnings['warning']).lower()}",
            f"output path: {output_path}",
        ]
    )
    return "\n".join(lines)


def _display_summary(summary: str) -> None:
    try:
        print(summary)
    except (BrokenPipeError, OSError, ValueError):
        pass


def _positive_scores(model: object, frame: pd.DataFrame) -> np.ndarray:
    return score_model(model, frame)


def _artifact_model(model: object) -> object:
    get_booster = getattr(model, "get_booster", None)
    return get_booster() if callable(get_booster) else model


def _audit_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[:, _AUDIT_COLUMNS].copy()


def _oof_frame(frame: pd.DataFrame, selection) -> pd.DataFrame:
    development = frame.loc[selection.oof_scores.index]
    output = _audit_frame(development)
    output["development_fold"] = selection.development_folds.loc[
        output.index
    ].astype(int)
    output["oof_score"] = selection.oof_scores.loc[output.index].to_numpy(dtype=float)
    return output


def _scored_frame(model: object, frame: pd.DataFrame) -> pd.DataFrame:
    output = _audit_frame(frame)
    output["score"] = _positive_scores(model, frame)
    return output


def _cv_table(results) -> pd.DataFrame:
    rows = []
    for result in results:
        for metric in sorted(result.folds, key=lambda value: value.fold):
            rows.append(
                {
                    "candidate": result.candidate.name,
                    "max_depth": result.candidate.max_depth,
                    "min_child_weight": result.candidate.min_child_weight,
                    "fold": metric.fold,
                    "weighted_auc": metric.weighted_auc,
                    "unweighted_auc": metric.unweighted_auc,
                    "best_iteration": metric.best_iteration,
                    "mean_weighted_auc": result.mean_weighted_auc,
                    "standard_error_weighted_auc": (
                        result.standard_error_weighted_auc
                    ),
                }
            )
    return pd.DataFrame(rows)


def _weight_summary(frame: pd.DataFrame) -> dict[str, object]:
    splits: dict[str, object] = {}
    for split in ("train", "validation", "test"):
        split_frame = frame.loc[frame["split"] == split]
        by_class: dict[str, object] = {}
        for label, name in ((0, "zz"), (1, "higgs")):
            weights = split_frame.loc[
                split_frame["label"] == label, "physical_weight"
            ].to_numpy(dtype=float)
            by_class[name] = {
                "label": label,
                "rows": int(len(weights)),
                "signed_physical_weight": float(weights.sum()),
                "absolute_physical_weight": float(np.abs(weights).sum()),
                "negative_weight_rows": int(np.count_nonzero(weights < 0.0)),
            }
        splits[split] = by_class
    return {
        "schema_version": "1.0",
        "rows": int(len(frame)),
        "sampling_fractions": {"higgs": 1.0, "zz": 1.0},
        "identity_collisions": identity_collision_summary(frame),
        "splits": splits,
    }


def _plot_bytes(
    oof,
    test,
    cv_results,
    model,
    working_points,
    policy,
):
    with tempfile.TemporaryDirectory(prefix="task4b-mc-plots-") as temporary:
        output_dir = Path(temporary)
        save_full_training_plots(
            oof,
            test,
            cv_results,
            model,
            working_points,
            policy,
            output_dir,
        )
        return {name: (output_dir / name).read_bytes() for name in PLOT_NAMES}


def _warnings(metrics: dict[str, object]) -> dict[str, object]:
    overfitting = metrics["overfitting"]
    sculpting = metrics["mass_sculpting"]
    return {
        "warning": bool(overfitting["warning"] or sculpting["warning"]),
        "overfitting": {
            "warning": bool(overfitting["warning"]),
            "warning_reasons": list(overfitting["warning_reasons"]),
        },
        "mass_sculpting": {
            "warning": bool(sculpting["warning"]),
            "warning_reasons": list(sculpting["warning_reasons"]),
        },
    }


if __name__ == "__main__":
    main()
