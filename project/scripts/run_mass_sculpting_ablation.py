"""Run the sealed, MC-only DSID 363490 feature-ablation study."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.full_training_run import load_training_mc_frame
from src.mass_sculpting_ablation import AblationOutcome, select_and_score_test
from src.mass_sculpting_ablation_plots import (
    plot_oof_profile_tradeoff,
    plot_selected_mass_sculpting,
)
from src.mass_sculpting_ablation_run import (
    assert_ablation_sources_unchanged,
    claim_ablation_output,
    publish_ablation_manifest,
    record_ablation_failure,
    resolve_ablation_output,
    resolve_ablation_sources,
    summarize_mc_source_rows,
    write_ablation_artifacts,
)
from src.provenance import software_versions


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the sealed MC-only mass-sculpting feature ablation"
    )
    parser.add_argument("--input-run", required=True)
    parser.add_argument("--reference-run", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parents[1]
    working_directory = Path.cwd()
    resolve_ablation_output(
        project_root=project_root,
        working_directory=working_directory,
        input_run=Path(args.input_run),
        reference_run=Path(args.reference_run),
        run_dir=Path(args.run_dir),
    )
    sources = resolve_ablation_sources(
        input_run=args.input_run,
        reference_run=args.reference_run,
        config_path=args.config,
    )
    layout = resolve_ablation_output(
        project_root=project_root,
        working_directory=working_directory,
        input_run=sources.training_input.input_run,
        reference_run=sources.reference_run,
        run_dir=Path(args.run_dir),
    )
    layout = claim_ablation_output(layout)
    try:
        frame = load_training_mc_frame(sources.training_input)
        source_row_counts = summarize_mc_source_rows(
            frame, sources.training_input.expected_rows
        )
        outcome = select_and_score_test(frame, sources.policy)
        artifacts = build_ablation_artifacts(
            outcome, sources.policy, sources.reference_summary
        )
        receipt = write_ablation_artifacts(
            layout,
            config_source=sources.records["study_config"].path,
            config_bytes=sources.config_bytes,
            **artifacts,
        )
        assert_ablation_sources_unchanged(sources)
        decision = artifacts["selection"]
        publish_ablation_manifest(
            layout,
            receipt=receipt,
            sources=sources.records,
            source_row_counts=source_row_counts,
            decision=decision,
            software=software_versions(),
        )
    except Exception as error:
        record_ablation_failure(layout, error)
        raise
    _display_summary(artifacts["selection"], layout.run_dir)
    return 0


def build_ablation_artifacts(
    outcome: AblationOutcome, policy, reference_summary: Mapping[str, Any]
) -> dict[str, Any]:
    reference_row = _reference_row(reference_summary)
    rows: list[dict[str, Any]] = [reference_row]
    plot_values: dict[str, dict[str, float]] = {
        "full14_reference": {
            "weighted_auc": float(reference_row["weighted_oof_auc"]),
            "maximum_ks": float(reference_row["maximum_oof_zz_ks"]),
        }
    }
    for name, result in outcome.development_results.items():
        maximum_ks = max(float(value) for value in result.zz_ks_distances.values())
        row: dict[str, Any] = {
            "profile": name,
            "features": ",".join(result.profile.features),
            "candidate": result.candidate_name,
            "final_tree_count": int(result.final_tree_count),
            "weighted_oof_auc": float(result.weighted_auc),
            "oof_score_mass_correlation": float(result.score_mass_correlation),
            "maximum_oof_zz_ks": maximum_ks,
            "eligible": len(result.eligibility_reasons) == 0,
            "eligibility_reasons": ",".join(result.eligibility_reasons),
        }
        for point in ("loose", "medium", "tight"):
            row[f"{point}_threshold"] = float(result.working_points[point]["threshold"])
            row[f"{point}_signal_efficiency"] = float(result.signal_efficiencies[point])
            row[f"{point}_target_zz_efficiency"] = float(
                result.target_background_efficiencies[point]
            )
            row[f"{point}_oof_zz_ks"] = float(result.zz_ks_distances[point])
        rows.append(row)
        plot_values[name] = {
            "weighted_auc": float(result.weighted_auc),
            "maximum_ks": maximum_ks,
        }
    profile_results = pd.DataFrame(rows)
    plot_artifacts = {
        "oof_profile_tradeoff.png": plot_oof_profile_tradeoff(plot_values)
    }
    if outcome.selected is None:
        return {
            "profile_results": profile_results,
            "selection": {
                "schema_version": "1.0",
                "status": "no_eligible_profile",
                "selected_profile": None,
                "auc_floor": 0.80,
                "ks_limit": 0.10,
            },
            "plot_artifacts": plot_artifacts,
        }
    if outcome.evidence is None or outcome.selected.oof_scores is None:
        raise ValueError("selected ablation outcome is missing score evidence")
    selected = outcome.selected
    evidence = outcome.evidence
    test_metrics = _test_metrics(evidence, selected.working_points)
    plot_artifacts["selected_mass_sculpting.png"] = plot_selected_mass_sculpting(
        selected.oof_scores,
        evidence.test_scores,
        selected.working_points,
        mass_bins_gev=policy.mass_bins_gev,
    )
    status = (
        "successful_simple_mitigation"
        if all(
            np.isfinite(float(value)) and float(value) <= 0.10
            for value in test_metrics["zz_ks_distances"].values()
        )
        else "test_nonreproduction"
    )
    selection = {
        "schema_version": "1.0",
        "status": status,
        "selected_profile": selected.profile.name,
        "auc_floor": 0.80,
        "ks_limit": 0.10,
        "selection_basis": "development_oof_only",
        "working_points_source": "selected_profile_oof_zz",
    }
    return {
        "profile_results": profile_results,
        "selection": selection,
        "plot_artifacts": plot_artifacts,
        "model": _artifact_model(evidence.model),
        "test_metrics": test_metrics,
        "selected_oof_scores": selected.oof_scores,
        "test_scores": evidence.test_scores,
    }


def _reference_row(summary: Mapping[str, Any]) -> dict[str, Any]:
    if summary.get("profile") != "full14_reference":
        raise ValueError("reference summary must describe full14_reference")
    points = summary.get("working_points")
    if not isinstance(points, Mapping) or set(points) != {"loose", "medium", "tight"}:
        raise ValueError("reference summary has incomplete working points")
    ks_values = [float(points[name]["zz_ks_distance"]) for name in ("loose", "medium", "tight")]
    row: dict[str, Any] = {
        "profile": "full14_reference",
        "features": ",".join(summary["features"]),
        "candidate": summary["candidate"],
        "final_tree_count": int(summary["final_tree_count"]),
        "weighted_oof_auc": float(summary["weighted_auc"]),
        "oof_score_mass_correlation": float(summary["score_mass_correlation"]),
        "maximum_oof_zz_ks": max(ks_values),
        "eligible": False,
        "eligibility_reasons": ",".join(summary["eligibility_reasons"]),
    }
    for name in ("loose", "medium", "tight"):
        point = points[name]
        row[f"{name}_threshold"] = float(point["threshold"])
        row[f"{name}_signal_efficiency"] = float(point["signal_efficiency"])
        row[f"{name}_target_zz_efficiency"] = float(
            point["target_background_efficiency"]
        )
        row[f"{name}_oof_zz_ks"] = float(point["zz_ks_distance"])
    return row


def _test_metrics(evidence, working_points: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    test = evidence.test_scores
    diagnostics = evidence.test_zz_diagnostics
    ks = {
        name: float(values["inclusive_to_selected_ks_distance"])
        for name, values in diagnostics["working_points"].items()
    }
    efficiencies: dict[str, dict[str, float]] = {}
    for name in ("loose", "medium", "tight"):
        threshold = float(working_points[name]["threshold"])
        efficiencies[name] = {
            "threshold": threshold,
            "signal_efficiency": _weighted_efficiency(test, 1, threshold),
            "zz_efficiency": _weighted_efficiency(test, 0, threshold),
        }
    zz = test.loc[test["label"] == 0]
    return {
        "schema_version": "1.0",
        "weighted_auc": float(evidence.test_weighted_auc),
        "zz_score_mass_correlation": _weighted_correlation(
            zz["score"].to_numpy(dtype=float),
            zz["m4l"].to_numpy(dtype=float),
            np.abs(zz["physical_weight"].to_numpy(dtype=float)),
        ),
        "zz_ks_distances": ks,
        "working_points": efficiencies,
    }


def _weighted_efficiency(frame: pd.DataFrame, label: int, threshold: float) -> float:
    rows = frame.loc[frame["label"] == label]
    weights = np.abs(rows["physical_weight"].to_numpy(dtype=float))
    total = float(weights.sum())
    if total <= 0.0:
        raise ValueError("test class has zero absolute physical weight")
    return float(weights[rows["score"].to_numpy(dtype=float) >= threshold].sum() / total)


def _weighted_correlation(x: np.ndarray, y: np.ndarray, weights: np.ndarray) -> float:
    total = float(weights.sum())
    if total <= 0.0:
        raise ValueError("ZZ test rows have zero absolute physical weight")
    mean_x = float(np.average(x, weights=weights))
    mean_y = float(np.average(y, weights=weights))
    covariance = float(np.average((x - mean_x) * (y - mean_y), weights=weights))
    variance_x = float(np.average((x - mean_x) ** 2, weights=weights))
    variance_y = float(np.average((y - mean_y) ** 2, weights=weights))
    if variance_x <= 0.0 or variance_y <= 0.0:
        raise ValueError("weighted correlation requires nonzero variance")
    return covariance / float(np.sqrt(variance_x * variance_y))


def _artifact_model(model: object) -> object:
    get_booster = getattr(model, "get_booster", None)
    return get_booster() if callable(get_booster) else model


def _display_summary(selection: Mapping[str, Any], run_dir: Path) -> None:
    try:
        print(f"study status: {selection['status']}")
        print(f"selected profile: {selection.get('selected_profile')}")
        print(f"output path: {run_dir}")
    except (BrokenPipeError, OSError, ValueError):
        pass


if __name__ == "__main__":
    main()
