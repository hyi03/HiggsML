"""Behavior-equivalent MC-only Angular19 preprocessing pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..domain.angular5 import ANGULAR5_FEATURES, build_angular5
from ..domain.features import FEATURES, build_candidate_features
from ..domain.selection import CutflowAccumulator, SelectionConfig, select_event
from ..domain.split import event_split
from ..domain.weights import (
    MCNormalization,
    physical_event_weight,
    training_weights,
)
from .reader import iter_mc_events, validate_channel_numbers


LUMINOSITY_PB = 10_000.0
MODEL_FEATURES = (*tuple(FEATURES), *ANGULAR5_FEATURES)
METADATA_COLUMNS = (
    "m4l",
    "label",
    "split",
    "physical_weight",
    "train_weight",
    "channelNumber",
    "eventNumber",
    "runNumber",
    "mcWeight",
    "xsec",
    "kfac",
    "filteff",
    "sum_of_weights",
)
OUTPUT_COLUMNS = (*MODEL_FEATURES, *METADATA_COLUMNS)


@dataclass(frozen=True)
class PreparedMCSample:
    name: str
    frame: pd.DataFrame
    cutflow: Mapping[str, Any]
    normalization: MCNormalization


@dataclass(frozen=True)
class PreprocessedDataset:
    development: pd.DataFrame
    test: pd.DataFrame
    cutflow: Mapping[str, Any]
    summary: Mapping[str, Any]


def _normalization_from_protocol(sample: Mapping[str, Any]) -> MCNormalization | None:
    raw = sample.get("normalization")
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or raw.get("source") != "official_metadata":
        raise ValueError("external normalization must use official_metadata")
    return MCNormalization(
        raw["xsec_pb"],
        raw["k_factor"],
        raw["filter_efficiency"],
        raw["sum_of_weights"],
    )


def _audit_normalization(row: dict[str, Any], value: MCNormalization) -> None:
    row.update(
        xsec=value.xsec_pb,
        kfac=value.k_factor,
        filteff=value.filter_efficiency,
        sum_of_weights=value.sum_of_weights,
    )


def prepare_mc_sample(
    path: str,
    *,
    name: str,
    sample: Mapping[str, Any],
    selection: SelectionConfig,
    chunk_size_events: int,
) -> PreparedMCSample:
    expected_channels = tuple(int(value) for value in sample["channel_numbers"])
    label = int(sample["label"])
    profile = str(sample["input_profile"])
    tree_name = str(sample["tree_name"])
    momentum_unit = str(sample["momentum_unit"])
    normalization = _normalization_from_protocol(sample)
    cutflow = CutflowAccumulator(
        sample_name=f"{name}_{expected_channels[0]}",
        is_data=False,
        stages=selection.stages,
    )
    observed_channels: set[int] = set()
    rows: list[dict[str, Any]] = []

    for event in iter_mc_events(
        path,
        tree_name=tree_name,
        chunk_size_events=chunk_size_events,
        profile=profile,
        extra_canonical_branches=selection.required_canonical_branches,
    ):
        channel = int(event["channelNumber"])
        observed_channels.add(channel)
        if normalization is None:
            normalization = MCNormalization.from_event(event)
        weight = physical_event_weight(
            event,
            LUMINOSITY_PB,
            normalization=normalization,
            require_event_normalization=sample.get("normalization") is None,
        )
        cutflow.record_read(weight)
        result = select_event(event, selection, momentum_unit)
        cutflow.record_selection(result, weight)
        if not result.accepted:
            continue
        assert result.candidate is not None
        row = build_candidate_features(event, result.candidate)
        row.update(build_angular5(result.candidate))
        _audit_normalization(row, normalization)
        row["physical_weight"] = weight
        row["label"] = label
        rows.append(row)

    validate_channel_numbers(observed_channels, expected_channels, name)
    if normalization is None:
        raise ValueError(f"{name}: no MC events were read")
    if not rows:
        raise ValueError(f"{name}: no events passed selection")

    frame = pd.DataFrame(rows)
    frame["train_weight"] = training_weights(frame["physical_weight"])
    frame["split"] = [
        event_split(event, channel)
        for event, channel in zip(
            frame["eventNumber"], frame["channelNumber"], strict=True
        )
    ]
    missing = [name for name in OUTPUT_COLUMNS if name not in frame.columns]
    if missing:
        raise ValueError(f"{name}: output columns are missing: {missing}")
    frame = frame.loc[:, OUTPUT_COLUMNS].copy()
    if not np.isfinite(frame[list(MODEL_FEATURES)].to_numpy(dtype=float)).all():
        raise ValueError(f"{name}: model features contain NaN or infinity")
    return PreparedMCSample(
        name=name,
        frame=frame,
        cutflow=cutflow.to_dict(),
        normalization=normalization,
    )


def _sample_summary(sample: PreparedMCSample) -> dict[str, Any]:
    frame = sample.frame
    return {
        "channel_numbers": sorted(
            int(value) for value in frame["channelNumber"].unique().tolist()
        ),
        "label": int(frame["label"].iloc[0]),
        "selected_events": int(len(frame)),
        "split_counts": {
            name: int((frame["split"] == name).sum())
            for name in ("train", "validation", "test")
        },
        "signed_physical_weight_sum": float(frame["physical_weight"].sum()),
        "absolute_physical_weight_sum": float(frame["physical_weight"].abs().sum()),
        "normalization": {
            "xsec_pb": sample.normalization.xsec_pb,
            "k_factor": sample.normalization.k_factor,
            "filter_efficiency": sample.normalization.filter_efficiency,
            "sum_of_weights": sample.normalization.sum_of_weights,
        },
    }


def build_preprocessed_dataset(
    *,
    protocol: Mapping[str, Any],
    higgs_root: str,
    zz_root: str,
    chunk_size_events: int,
) -> PreprocessedDataset:
    selection = SelectionConfig.from_mapping(protocol["selection"])
    roots = {"higgs": higgs_root, "zz": zz_root}
    prepared = [
        prepare_mc_sample(
            roots[name],
            name=name,
            sample=protocol["samples"][name],
            selection=selection,
            chunk_size_events=chunk_size_events,
        )
        for name in ("higgs", "zz")
    ]
    combined = pd.concat([sample.frame for sample in prepared], ignore_index=True)
    duplicate = combined.duplicated(["channelNumber", "eventNumber"], keep=False)
    if duplicate.any():
        raise ValueError("duplicate canonical event identity")
    development = combined.loc[combined["split"].isin(("train", "validation"))].copy()
    test = combined.loc[combined["split"] == "test"].copy()
    if development.empty or test.empty:
        raise ValueError("development and test partitions must both be non-empty")
    development.reset_index(drop=True, inplace=True)
    test.reset_index(drop=True, inplace=True)
    return PreprocessedDataset(
        development=development,
        test=test,
        cutflow={
            "schema_version": "1.0",
            "samples": {
                str(sample.cutflow["sample_name"]): sample.cutflow
                for sample in prepared
            },
        },
        summary={
            "schema_version": "1.0",
            "samples": {
                str(sample.cutflow["sample_name"]): _sample_summary(sample)
                for sample in prepared
            },
            "development_events": int(len(development)),
            "test_events": int(len(test)),
            "total_events": int(len(combined)),
        },
    )
