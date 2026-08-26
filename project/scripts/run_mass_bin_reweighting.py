"""Run the sealed MC-only mass-bin iterative reweighting study."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from src.full_training_run import load_training_mc_frame
from src.mass_bin_reweighting import ReweightingStudyOutcome, run_mass_bin_reweighting_study
from src.mass_bin_reweighting_plots import (
    build_iteration_tradeoff_png,
    build_selected_mass_sculpting_png,
    build_zz_efficiency_by_mass_png,
)
from src.mass_bin_reweighting_run import (
    assert_reweighting_execution_gate,
    assert_reweighting_sources_unchanged,
    claim_reweighting_output,
    policy_manifest_record,
    publish_reweighting_manifest,
    record_reweighting_failure,
    resolve_reweighting_output,
    resolve_reweighting_sources,
    summarize_mc_source_rows,
    write_reweighting_artifacts,
)
from src.provenance import software_versions


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run sealed MC-only mass-bin reweighting")
    parser.add_argument("--input-run", required=True)
    parser.add_argument("--reference-run", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    working_directory = Path.cwd()

    resolve_reweighting_output(
        project_root=project_root,
        working_directory=working_directory,
        input_run=Path(args.input_run),
        reference_run=Path(args.reference_run),
        run_dir=Path(args.run_dir),
    )
    sources = resolve_reweighting_sources(
        input_run=args.input_run,
        reference_run=args.reference_run,
        config_path=args.config,
    )
    layout = resolve_reweighting_output(
        project_root=project_root,
        working_directory=working_directory,
        input_run=sources.training_input.input_run,
        reference_run=sources.reference_run,
        ablation_run=sources.ablation_run,
        raw_zz_path=sources.raw_zz_path,
        reweighting_reference_run=sources.reweighting_reference_run,
        run_dir=Path(args.run_dir),
    )
    assert_reweighting_execution_gate(
        config=sources.config,
        project_root=project_root,
        layout=layout,
    )
    layout = claim_reweighting_output(layout)
    try:
        frame = _load_bound_mc_frame(sources)
        source_rows = summarize_mc_source_rows(frame, sources.training_input.expected_rows)
        outcome = run_mass_bin_reweighting_study(
            frame, sources.policy, sources.reweighting_policy,
            features=sources.config.features,
        )
        artifacts = build_reweighting_artifacts(outcome)
        receipt = write_reweighting_artifacts(
            layout,
            config_source=sources.records["study_config"].path,
            config_bytes=sources.config_bytes,
            features=sources.config.features,
            **artifacts,
        )
        assert_reweighting_sources_unchanged(sources)
        publish_reweighting_manifest(
            layout,
            receipt=receipt,
            sources=sources.records,
            source_row_counts=source_rows,
            decision=artifacts["selection"],
            policy=policy_manifest_record(sources.config),
            software=software_versions(),
        )
    except BaseException as error:
        record_reweighting_failure(layout, error)
        raise
    _display_summary(artifacts["selection"], layout.run_dir)
    return 0


def _load_bound_mc_frame(sources):
    if sources.config.schema_version == "1.2":
        expected = Path(sources.config.input_table_path or "").resolve()
        if (
            sources.config.features != (
                "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
                "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
                "cos_theta_star", "cos_theta_1", "cos_theta_2", "phi_decay_planes",
                "phi_production_plane",
            )
            or sources.training_input.mc_path.resolve() != expected
        ):
            raise ValueError("R3-ARM64 Angular5 input is not bound to the sealed profile")
    return load_training_mc_frame(sources.training_input)


def build_reweighting_artifacts(outcome: ReweightingStudyOutcome) -> dict[str, Any]:
    iteration_rows: list[dict[str, Any]] = []
    bin_tables: list[pd.DataFrame] = []
    multiplier_rows: list[dict[str, Any]] = []
    for evidence in outcome.iterations:
        row: dict[str, Any] = {
            "iteration": int(evidence.iteration),
            "candidate": evidence.candidate_name,
            "final_tree_count": int(evidence.final_tree_count),
            "weighted_oof_auc": float(evidence.weighted_oof_auc),
            "maximum_oof_zz_ks": max(float(value) for value in evidence.zz_ks_distances.values()),
            "eligible": bool(evidence.eligible),
            "eligibility_reasons": ",".join(evidence.eligibility_reasons),
        }
        for name in ("loose", "medium", "tight"):
            row[f"{name}_threshold"] = float(evidence.working_points[name]["threshold"])
            row[f"{name}_signal_efficiency"] = float(evidence.signal_efficiencies[name])
            row[f"{name}_achieved_zz_efficiency"] = float(evidence.achieved_zz_efficiencies[name])
            row[f"{name}_oof_zz_ks"] = float(evidence.zz_ks_distances[name])
        iteration_rows.append(row)
        table = pd.DataFrame(evidence.bin_efficiencies.copy(deep=True)).reset_index()
        table.insert(0, "iteration", int(evidence.iteration))
        bin_tables.append(table)
        for mass_bin, value in evidence.cumulative_multipliers.items():
            multiplier_rows.append({"iteration": int(evidence.iteration), "mass_bin": mass_bin, "multiplier": float(value)})

    iteration_results = pd.DataFrame(iteration_rows)
    if outcome.status == "insufficient_bin_statistics":
        iteration_results = pd.DataFrame(columns=["iteration", "weighted_oof_auc"])
        bin_efficiencies = pd.DataFrame(columns=["iteration", "mass_bin", "working_point", "efficiency"])
        weight_multipliers = pd.DataFrame(columns=["iteration", "mass_bin", "multiplier"])
    else:
        bin_efficiencies = pd.concat(bin_tables, ignore_index=True)
        weight_multipliers = pd.DataFrame(multiplier_rows)
    selected = outcome.selected_iteration is not None
    selection = {
        "schema_version": "1.0",
        "status": outcome.status,
        "selected_iteration": outcome.selected_iteration,
        "test_opened": selected,
        "selection_basis": "development_oof_only",
    }
    if outcome.status == "insufficient_bin_statistics":
        plots = {
            "iteration_tradeoff.png": _insufficient_statistics_png(
                "No development iteration executed",
                "Fixed-bin effective-count gate failed before model fitting",
            ),
            "zz_efficiency_by_mass.png": _insufficient_statistics_png(
                "No OOF ZZ-efficiency evidence",
                "Fixed bins were not merged or changed",
            ),
        }
    else:
        plots = {
            "iteration_tradeoff.png": build_iteration_tradeoff_png(outcome),
            "zz_efficiency_by_mass.png": build_zz_efficiency_by_mass_png(outcome),
        }
    result: dict[str, Any] = {
        "iteration_results": iteration_results,
        "bin_efficiencies": bin_efficiencies,
        "weight_multipliers": weight_multipliers,
        "selection": selection,
        "plot_artifacts": plots,
        "fixed_bin_statistics": (
            None
            if getattr(outcome, "fixed_bin_statistics", None) is None
            else pd.DataFrame(outcome.fixed_bin_statistics.copy(deep=True)).reset_index()
        ),
    }
    if selected:
        if outcome.model is None or outcome.selected_oof_scores is None or outcome.test_scores is None or outcome.test_metrics is None:
            raise ValueError("selected outcome is missing frozen test evidence")
        plots["selected_mass_sculpting.png"] = build_selected_mass_sculpting_png(outcome)
        model = outcome.model
        get_booster = getattr(model, "get_booster", None)
        result.update(
            model=get_booster() if callable(get_booster) else model,
            test_metrics={"schema_version": "1.0", **_plain_mapping(outcome.test_metrics)},
            selected_oof_scores=pd.DataFrame(outcome.selected_oof_scores.copy(deep=True)),
            test_scores=pd.DataFrame(outcome.test_scores.copy(deep=True)),
        )
    return result


def _plain_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: _plain_mapping(item) if isinstance(item, Mapping) else item
        for key, item in value.items()
    }


def _insufficient_statistics_png(title: str, detail: str) -> bytes:
    figure, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
    try:
        axis.axis("off")
        axis.text(0.5, 0.58, title, ha="center", va="center", fontsize=13)
        axis.text(0.5, 0.42, detail, ha="center", va="center", fontsize=10)
        axis.set_title("MC-only mass-bin reweighting terminal")
        buffer = BytesIO()
        figure.savefig(buffer, format="png", dpi=140)
        payload = buffer.getvalue()
        if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Matplotlib did not produce a PNG")
        return payload
    finally:
        plt.close(figure)


def _display_summary(selection, run_dir: Path) -> None:
    try:
        print(f"study status: {selection['status']}")
        print(f"selected iteration: {selection.get('selected_iteration')}")
        print(f"output path: {run_dir}")
    except (BrokenPipeError, OSError, ValueError):
        pass


if __name__ == "__main__":
    main()
