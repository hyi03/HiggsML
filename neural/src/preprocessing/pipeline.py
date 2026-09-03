from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from tqdm.auto import tqdm

from src.artifacts.manifest import peak_memory_bytes, sha256_file, software_record, write_json
from src.artifacts.transaction import RunTransaction
from src.config import InputBindingError, PreprocessProtocol, PreprocessRunConfig, SampleProtocol, load_preprocess_protocol, load_preprocess_run_config
from src.domain.angular5 import build_angular5
from src.domain.features import build_candidate_features
from src.domain.selection import CutflowAccumulator, SelectionConfig, STAGES, select_event
from src.domain.splitting import event_split
from src.domain.weights import physical_event_weight, training_weights

from .outputs import canonical_csv_bytes, write_canonical_table
from .root_reader import iter_events


INTEGER_COLUMNS = {"label", "source_entry", "runNumber", "eventNumber", "channelNumber"}
STRING_COLUMNS = {"split", "source_sample"}


def _selection(protocol: PreprocessProtocol) -> SelectionConfig:
    return SelectionConfig.from_mapping(protocol.selection)


def _normalization(event: dict[str, Any], sample: SampleProtocol, previous: dict[str, float] | None) -> dict[str, float]:
    if sample.normalization is not None:
        return {key: float(value) for key, value in sample.normalization.items()}
    current = {"xsec_pb": float(event["xsec"]), "k_factor": float(event["kfac"]), "filter_efficiency": float(event["filteff"]), "sum_of_weights": float(event["sum_of_weights"])}
    if previous is not None:
        for key in current:
            if not np.isclose(current[key], previous[key], rtol=1e-12, atol=0.0):
                raise InputBindingError(f"{key} changed within {sample.source_sample}")
    return current


def prepare_table(
    protocol: PreprocessProtocol,
    config: PreprocessRunConfig,
    *,
    verify_hashes: bool = True,
    show_progress: bool = False,
):
    selection = _selection(protocol)
    frames: list[pd.DataFrame] = []
    cutflows: dict[str, Any] = {}
    summaries: dict[str, Any] = {}
    inputs: list[dict[str, Any]] = []
    for key, sample in protocol.samples.items():
        path = config.sample_paths[key]
        actual_hash = sha256_file(path)
        if verify_hashes and actual_hash != sample.sha256:
            raise InputBindingError(f"SHA-256 mismatch for {sample.source_sample}")
        accumulator = CutflowAccumulator(sample.source_sample)
        normalization: dict[str, float] | None = None
        rows = []
        observed_channels = set()
        try:
            events = iter_events(
                path, sample, config.chunk_size_events, verify_entry_count=verify_hashes
            )
            with tqdm(
                total=sample.expected_entry_count,
                desc=f"preprocess {sample.source_sample}",
                unit="event",
                dynamic_ncols=True,
                disable=not show_progress,
            ) as progress:
                for event in events:
                    progress.update(1)
                    observed_channels.add(int(event["channelNumber"]))
                    normalization = _normalization(event, sample, normalization)
                    weight = physical_event_weight(mc_weight=float(event["mcWeight"]), luminosity_pb=protocol.luminosity_pb, **normalization)
                    accumulator.record(None, weight)
                    result = select_event(event, selection, sample.momentum_unit)
                    accumulator.record(result, weight)
                    if not result.accepted:
                        continue
                    if result.candidate is None:
                        raise InputBindingError("selected event has no candidate")
                    row = build_candidate_features(event, result.candidate)
                    row.update(build_angular5(result.candidate))
                    row.update(label=sample.label, split=event_split(event["eventNumber"], event["channelNumber"]), physical_weight=weight, source_sample=sample.source_sample, source_entry=int(event["source_entry"]))
                    rows.append(row)
        except InputBindingError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise InputBindingError(f"invalid event for {sample.source_sample}") from error
        if observed_channels != {sample.dsid}:
            raise InputBindingError(f"channelNumber mismatch for {sample.source_sample}: {sorted(observed_channels)}")
        if not rows:
            raise InputBindingError(f"no selected events for {sample.source_sample}")
        frame = pd.DataFrame(rows)
        frame["train_weight"] = training_weights(frame["physical_weight"])
        frame = frame.loc[:, protocol.output_columns]
        frames.append(frame)
        cutflows[sample.source_sample] = accumulator.to_dict()
        split_counts = {name: int((frame["split"] == name).sum()) for name in ("train", "validation", "test")}
        summaries[sample.source_sample] = {"dsid": sample.dsid, "label": sample.label, "read_count": accumulator.counts["read"], "selected_count": len(frame), "split_counts": split_counts, "negative_weight_events": int((frame["physical_weight"] < 0).sum()), "sum_physical_weight": float(frame["physical_weight"].sum()), "sum_abs_physical_weight": float(frame["physical_weight"].abs().sum())}
        inputs.append({"source_sample": sample.source_sample, "dsid": sample.dsid, "logical_path": str(path), "sha256": actual_hash, "size_bytes": path.stat().st_size, "tree_name": sample.tree_name, "input_profile": sample.input_profile, "momentum_unit": sample.momentum_unit, "entry_count": accumulator.counts["read"]})
    combined = pd.concat(frames, ignore_index=True)
    if combined.duplicated(["source_sample", "source_entry"]).any():
        raise InputBindingError("canonical identity is not unique")
    return combined, cutflows, summaries, inputs


def execute_preprocess(
    *,
    protocol_path: str | Path,
    run_config_path: str | Path,
    run_dir: str | Path,
    allowed_root: str | Path,
    show_progress: bool = False,
) -> None:
    protocol = load_preprocess_protocol(protocol_path)
    config = load_preprocess_run_config(run_config_path)
    started = time.perf_counter()
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with RunTransaction(run_dir, allowed_root=allowed_root) as transaction:
        frame, cutflows, summaries, inputs = prepare_table(
            protocol, config, show_progress=show_progress
        )
        processed, artifacts = transaction.path / "processed", transaction.path / "artifacts"
        processed.mkdir(); artifacts.mkdir()
        snapshot = {"protocol_sha256": hashlib.sha256(protocol.payload).hexdigest(), "run_config_sha256": hashlib.sha256(config.payload).hexdigest(), "protocol": protocol.raw, "run_config": yaml.safe_load(config.payload)}
        config_bytes = yaml.safe_dump(snapshot, sort_keys=False).encode("utf-8")
        (transaction.path / "config.yaml").write_bytes(config_bytes)
        csv_payload = canonical_csv_bytes(
            frame,
            protocol.output_columns,
            integer_columns=INTEGER_COLUMNS,
            string_columns=STRING_COLUMNS,
            string_enums={
                "split": {"train", "validation", "test"},
                "source_sample": {sample.source_sample for sample in protocol.samples.values()},
            },
        )
        table = write_canonical_table(processed / "mc_events.csv.gz", csv_payload, row_count=len(frame))
        cutflow_receipt = write_json(artifacts / "cutflow.json", {"schema_version": "1.0", "selection": {"protocol_id": protocol.protocol_id, "z2_min_mode": protocol.selection["z2_min_mode"], "ordered_stages": list(STAGES)}, "samples": cutflows})
        total_splits = {name: sum(item["split_counts"][name] for item in summaries.values()) for name in ("train", "validation", "test")}
        legacy_sizes = frame.groupby(
            ["runNumber", "eventNumber", "channelNumber"], sort=False
        ).size()
        legacy_duplicates = legacy_sizes[legacy_sizes > 1]
        summary = {"schema_version": "1.0", "status": "success", "protocol_id": protocol.protocol_id, "samples": summaries, "totals": {"read_count": sum(item["read_count"] for item in summaries.values()), "selected_count": len(frame), "split_counts": total_splits}, "identity": {"fields": ["source_sample", "source_entry"], "unique": True, "duplicate_count": 0, "legacy_duplicate_groups": int(len(legacy_duplicates)), "legacy_duplicate_rows": int(legacy_duplicates.sum())}, "columns": {"ordered_names": list(protocol.output_columns), "row_count": len(frame)}}
        summary_receipt = write_json(artifacts / "mc_summary.json", summary)
        for item, sample in zip(inputs, protocol.samples.values()):
            if sha256_file(item["logical_path"]) != sample.sha256:
                raise InputBindingError(f"input changed before publication: {sample.source_sample}")
        outputs = [
            {"path": "config.yaml", "sha256": hashlib.sha256(config_bytes).hexdigest(), "size_bytes": len(config_bytes), "row_count": None, "canonical_content_sha256": None},
            {"path": "processed/mc_events.csv.gz", "sha256": table.sha256, "size_bytes": table.size_bytes, "row_count": len(frame), "canonical_content_sha256": table.canonical_content_sha256},
            {**cutflow_receipt, "path": "artifacts/cutflow.json", "row_count": None, "canonical_content_sha256": None},
            {**summary_receipt, "path": "artifacts/mc_summary.json", "row_count": None, "canonical_content_sha256": None},
        ]
        software = software_record()
        manifest = {"schema_version": "1.0", "status": "success", "run_type": "preprocess", "protocol_id": protocol.protocol_id, "started_at_utc": started_utc, "completed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "inputs": inputs, "configuration": {"protocol_path": str(protocol_path), "protocol_sha256": hashlib.sha256(protocol.payload).hexdigest(), "run_config_path": str(run_config_path), "run_config_sha256": hashlib.sha256(config.payload).hexdigest(), "chunk_size_events": config.chunk_size_events, "full_read": True}, "outputs": outputs, "schema": {"ordered_columns": list(protocol.output_columns), "dtypes": {name: str(frame[name].dtype) for name in protocol.output_columns}}, "counts": {"per_sample": summaries, "totals": summary["totals"]}, "software": {key: value for key, value in software.items() if key != "platform"}, "platform": software["platform"], "determinism": {"row_order": "higgs_then_zz_source_entry", "csv_float_format": ".17g", "gzip_mtime": 0}, "performance": {"wall_seconds": time.perf_counter() - started, "peak_memory_bytes": peak_memory_bytes()}}
        write_json(artifacts / "manifest.json", manifest)
