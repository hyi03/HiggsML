from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .features import FEATURES, build_candidate_features
from .input_profiles import resolve_input_profile
from .io import iter_events, validate_channel_numbers
from .selection import CutflowAccumulator, select_event
from .split import event_split
from .weights import MCNormalization, physical_event_weight, training_weights


CUTFLOW_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class PreparedSample:
    frame: pd.DataFrame
    cutflow: dict[str, Any]
    normalization: MCNormalization | None = None


def prepare_sample(
    path,
    *,
    sample_name,
    selection,
    tree_name,
    momentum_unit,
    is_data,
    label=None,
    expected_channels=(),
    luminosity_pb=10000.0,
    entry_stop=None,
    chunk_size_events=50_000,
    input_profile="release22",
    normalization_override=None,
):
    rows = []
    profile = resolve_input_profile(input_profile)
    cutflow = CutflowAccumulator(
        sample_name=sample_name,
        is_data=is_data,
        stages=selection.stages,
    )
    normalization = normalization_override
    observed_channels = set()
    for event in iter_events(
        path,
        tree_name,
        is_data=is_data,
        entry_stop=entry_stop,
        chunk_size_events=chunk_size_events,
        profile=profile,
        extra_canonical_branches=selection.required_canonical_branches,
    ):
        weight = None
        if not is_data:
            observed_channels.add(int(event["channelNumber"]))
            if normalization is None:
                normalization = MCNormalization.from_event(event)
            weight = physical_event_weight(
                event,
                luminosity_pb,
                normalization=normalization,
                require_event_normalization=profile.normalization_in_events,
            )
        cutflow.record_read(weight)
        result = select_event(event, selection, momentum_unit)
        cutflow.record_selection(result, weight)
        if result.accepted:
            assert result.candidate is not None
            row = build_candidate_features(event, result.candidate)
            if not is_data and normalization_override is not None:
                assert normalization is not None
                row.update(
                    xsec=normalization.xsec_pb,
                    kfac=normalization.k_factor,
                    filteff=normalization.filter_efficiency,
                    sum_of_weights=normalization.sum_of_weights,
                )
            if weight is not None:
                row["physical_weight"] = weight
            rows.append(row)

    if not is_data:
        if normalization is None:
            raise ValueError(f"{sample_name}: no MC events were read from {path}")
        validate_channel_numbers(observed_channels, expected_channels, sample_name)

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError(
            f"{sample_name}: no events passed selection from {path}; "
            f"cutflow={cutflow.to_dict()['stages']}"
        )

    if is_data:
        frame["label"] = -1
        frame["physical_weight"] = 1.0
        frame["train_weight"] = 1.0
        frame["split"] = "data"
    else:
        frame["label"] = int(label)
        frame["train_weight"] = training_weights(frame["physical_weight"])
        frame["split"] = [
            event_split(event, channel)
            for event, channel in zip(frame["eventNumber"], frame["channelNumber"])
        ]
    if not np.isfinite(frame[FEATURES].to_numpy(dtype=float)).all():
        raise ValueError("model features contain NaN or infinity")
    return PreparedSample(
        frame=frame,
        cutflow=cutflow.to_dict(),
        normalization=normalization,
    )


def build_cutflow(
    samples: Mapping[str, CutflowAccumulator | Mapping[str, Any]],
    *,
    z2_min_mode: str,
) -> dict[str, Any]:
    sample_output = {}
    for name in sorted(samples):
        value = samples[name]
        sample_output[name] = (
            value.to_dict() if isinstance(value, CutflowAccumulator) else dict(value)
        )
    return {
        "schema_version": CUTFLOW_SCHEMA_VERSION,
        "selection": {"z2_min_mode": str(z2_min_mode)},
        "samples": sample_output,
    }


def write_cutflow(
    samples: Mapping[str, CutflowAccumulator | Mapping[str, Any]],
    *,
    z2_min_mode: str,
    path: str | Path,
) -> None:
    payload = build_cutflow(samples, z2_min_mode=z2_min_mode)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
