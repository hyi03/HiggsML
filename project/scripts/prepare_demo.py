from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.input_profiles import resolve_input_profile
from src.pipeline import CUTFLOW_SCHEMA_VERSION, build_cutflow, prepare_sample
from src.preparation import (
    resolve_output_layout,
    resolve_read_policy,
    write_preparation_outputs,
)
from src.provenance import (
    MCNormalizationInput,
    SampleSummaryInput,
    build_data_summary,
    build_run_manifest,
)
from src.selection import SelectionConfig
from src.weights import MCNormalization


_NORMALIZATION_KEYS = {
    "source",
    "xsec_pb",
    "k_factor",
    "filter_efficiency",
    "sum_of_weights",
}


def _resolve_sample_configuration(
    sample: dict,
    *,
    defaults: dict,
    is_data: bool,
) -> dict:
    profile_name = sample.get("input_profile", defaults["input_profile"])
    profile = resolve_input_profile(profile_name)
    profile_override = "input_profile" in sample
    tree_name = sample.get(
        "tree_name", profile.tree_name if profile_override else defaults["tree_name"]
    )
    momentum_unit = sample.get(
        "momentum_unit",
        profile.momentum_unit if profile_override else defaults["momentum_unit"],
    )
    if tree_name is None:
        tree_name = profile.tree_name
    if momentum_unit is None:
        momentum_unit = profile.momentum_unit
    if not isinstance(tree_name, str) or not tree_name:
        raise ValueError("tree_name must be a non-empty string")
    if momentum_unit not in {"MeV", "GeV"}:
        raise ValueError("momentum_unit must be MeV or GeV")

    raw_normalization = sample.get("normalization")
    if is_data:
        if raw_normalization is not None:
            raise ValueError("data samples may not specify external normalization")
        normalization = None
        normalization_source = None
    elif raw_normalization is None:
        if not profile.normalization_in_events:
            raise ValueError(
                f"{profile.name}: MC samples require official metadata normalization"
            )
        normalization = None
        normalization_source = "root"
    else:
        if not isinstance(raw_normalization, dict):
            raise ValueError("normalization must be a mapping")
        source = raw_normalization.get("source")
        if source != "official_metadata":
            raise ValueError(f"unknown normalization source: {source}")
        if set(raw_normalization) != _NORMALIZATION_KEYS:
            raise ValueError("normalization keys must be exactly official metadata fields")
        if profile.normalization_in_events:
            raise ValueError("root event normalization conflicts with override")
        normalization = MCNormalization(
            raw_normalization["xsec_pb"],
            raw_normalization["k_factor"],
            raw_normalization["filter_efficiency"],
            raw_normalization["sum_of_weights"],
        )
        normalization_source = "official_metadata"
    return {
        "input_profile": profile.name,
        "tree_name": tree_name,
        "momentum_unit": momentum_unit,
        "normalization_override": normalization,
        "normalization_source": normalization_source,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Higgs, ZZ*, and data samples")
    parser.add_argument("--config", default="config/demo.yaml")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--run-dir")
    args = parser.parse_args()
    config_path = Path(args.config)
    config_bytes = config_path.read_bytes()
    config = yaml.safe_load(config_bytes)
    read_policy = resolve_read_policy(config, full_override=args.full)
    samples = config["samples"]
    selection = SelectionConfig.from_mapping(config["selection"])
    defaults = {
        "input_profile": config.get("input_profile", "release22"),
        "tree_name": config.get("tree_name"),
        "momentum_unit": config.get("momentum_unit"),
    }
    resolved_samples = {
        name: _resolve_sample_configuration(
            samples[name], defaults=defaults, is_data=name == "data"
        )
        for name in ("higgs", "zz", "data")
    }
    project_root = Path(__file__).resolve().parents[1]
    layout = resolve_output_layout(
        project_root=project_root,
        working_directory=Path.cwd(),
        read_policy=read_policy,
        run_dir=args.run_dir,
        output_dir=args.output_dir,
    )
    common = {
        "entry_stop": read_policy.entry_stop,
        "chunk_size_events": read_policy.chunk_size_events,
    }
    luminosity = float(config["luminosity_pb"])

    frames = []
    cutflows = {}
    summary_inputs = []
    mc_normalizations = []
    input_paths = {}
    for name in ("higgs", "zz"):
        sample = samples[name]
        sample_config = resolved_samples[name]
        channel_suffix = "-".join(str(value) for value in sample["channel_numbers"])
        sample_name = f"{name}_{channel_suffix}"
        prepared = prepare_sample(
            sample["path"],
            **common,
            input_profile=sample_config["input_profile"],
            tree_name=sample_config["tree_name"],
            momentum_unit=sample_config["momentum_unit"],
            normalization_override=sample_config["normalization_override"],
            sample_name=sample_name,
            selection=selection,
            is_data=False,
            label=sample["label"],
            expected_channels=sample["channel_numbers"],
            luminosity_pb=luminosity,
        )
        read_count = prepared.cutflow["stages"]["read"]["count"]
        selected_count = prepared.cutflow["stages"]["selected"]["count"]
        print(
            f"prepared {sample_name}: {read_count} read, "
            f"{selected_count} selected"
        )
        if prepared.normalization is None:
            raise ValueError(f"{sample_name}: MC normalization is missing")
        frames.append(prepared.frame)
        cutflows[sample_name] = prepared.cutflow
        summary_inputs.append(
            SampleSummaryInput(
                sample_name=sample_name,
                kind="mc",
                frame=prepared.frame,
                cutflow=prepared.cutflow,
                expected_dsids=tuple(sample["channel_numbers"]),
                label=int(sample["label"]),
            )
        )
        mc_normalizations.append(
            MCNormalizationInput(
                sample_name=sample_name,
                normalization=prepared.normalization,
                dsids=tuple(sample["channel_numbers"]),
                luminosity_pb=luminosity,
            )
        )
        input_paths[sample_name] = sample["path"]
    mc = pd.concat(frames, ignore_index=True)
    data_name = samples["data"]["period"]
    prepared_data = prepare_sample(
        samples["data"]["path"],
        **common,
        input_profile=resolved_samples["data"]["input_profile"],
        tree_name=resolved_samples["data"]["tree_name"],
        momentum_unit=resolved_samples["data"]["momentum_unit"],
        normalization_override=resolved_samples["data"]["normalization_override"],
        sample_name=data_name,
        selection=selection,
        is_data=True,
    )
    read_count = prepared_data.cutflow["stages"]["read"]["count"]
    selected_count = prepared_data.cutflow["stages"]["selected"]["count"]
    print(f"prepared {data_name}: {read_count} read, {selected_count} selected")
    data = prepared_data.frame
    data["period"] = samples["data"]["period"]
    cutflows[data_name] = prepared_data.cutflow
    summary_inputs.append(
        SampleSummaryInput(
            sample_name=data_name,
            kind="data",
            frame=data,
            cutflow=prepared_data.cutflow,
            period=samples["data"]["period"],
        )
    )
    input_paths[data_name] = samples["data"]["path"]

    cutflow_payload = build_cutflow(
        cutflows,
        z2_min_mode=selection.z2_min_mode,
    )
    summary_payload = build_data_summary(summary_inputs)
    processing = {
        "read_policy": read_policy.as_dict(),
        "random_seed": config.get("random_seed"),
        "tree_name": config.get("tree_name"),
        "momentum_unit": config.get("momentum_unit"),
        "selection": (
            config["selection"]
            if selection.lepton_quality.enabled
            else {"z2_min_mode": selection.z2_min_mode}
        ),
    }
    sample_processing = {
        name: {
            key: resolved_samples[name][key]
            for key in (
                "input_profile",
                "tree_name",
                "momentum_unit",
                "normalization_source",
            )
        }
        for name in ("higgs", "zz", "data")
    }
    sample_processing = {
        (f"{name}_{'-'.join(str(value) for value in samples[name]['channel_numbers'])}"
         if name != "data" else samples["data"]["period"]): value
        for name, value in sample_processing.items()
    }
    has_per_sample_provenance = selection.lepton_quality.enabled or any(
        "input_profile" in config
        or any(
            key in sample
            for key in ("input_profile", "tree_name", "momentum_unit", "normalization")
        )
        for sample in samples.values()
    )
    manifest_payload = build_run_manifest(
        config_path=config_path,
        config_snapshot_path=layout.config_snapshot,
        input_paths=input_paths,
        processing=processing,
        sample_processing=(sample_processing if has_per_sample_provenance else None),
        mc_normalizations=mc_normalizations,
        output_locations=layout.manifest_locations(),
        git_cwd=project_root,
        cutflow_schema_version=CUTFLOW_SCHEMA_VERSION,
    )
    write_preparation_outputs(
        layout,
        config_source=config_path,
        config_bytes=config_bytes,
        mc_frame=mc,
        data_frame=data,
        cutflow_payload=cutflow_payload,
        summary_payload=summary_payload,
        manifest_payload=manifest_payload,
    )
    print(f"prepared {len(mc)} MC events and {len(data)} data events")


if __name__ == "__main__":
    main()
