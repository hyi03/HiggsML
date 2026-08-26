"""R3-ARM64 Angular5 enrichment joined exclusively on source identity."""

from __future__ import annotations

from contextlib import contextmanager
import csv
import gzip
import hashlib
import io
import os
import stat
import tempfile
from types import MappingProxyType
from typing import Any, BinaryIO, Iterator, Mapping

import numpy as np
import pandas as pd

from . import angular5_enrichment as _base
from . import full_training_run as _safety
from .angular5 import ANGULAR5_FEATURES, build_angular5
from .angular5_identity import _scan_csv_records
from .angular5_enrichment_r3_arm64_run import (
    Angular5R3Arm64Sources,
    assert_angular5_r3_arm64_sources_unchanged,
)
from .input_profiles import resolve_input_profile
from .io import iter_events, validate_channel_numbers
from .selection import SelectionConfig, select_event


SOURCE_IDENTITY = ("source_sample", "source_entry")
TABLE_NAME = "mc_events_angular5.csv.gz"
IDENTITY_NAME = "identity_validation.json"
SUMMARY_NAME = "angular5_summary.json"
MANIFEST_NAME = "run_manifest.json"


def _source_binding(sources: Angular5R3Arm64Sources) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (name, str(receipt.path), receipt.device, receipt.inode, receipt.size_bytes, receipt.sha256)
        for name, receipt in sorted(sources.receipts.items())
    ) + (("config_bytes", hashlib.sha256(sources.config_bytes).hexdigest()),)


def _receipt_stat_matches(receipt, metadata: os.stat_result) -> bool:
    return stat.S_ISREG(metadata.st_mode) and (int(metadata.st_dev), int(metadata.st_ino), int(metadata.st_size)) == (receipt.device, receipt.inode, receipt.size_bytes)


def _after_receipt_descriptor_opened(name: str, path) -> None:
    """Test seam after a receipt is bound to an open descriptor."""


def _open_receipt_descriptor(receipt) -> int:
    try:
        descriptor = os.open(receipt.path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise RuntimeError(f"R3 Angular5 bound source could not be opened: {receipt.name}") from error
    if not _receipt_stat_matches(receipt, os.fstat(descriptor)):
        os.close(descriptor)
        raise RuntimeError(f"R3 Angular5 bound source identity changed: {receipt.name}")
    _after_receipt_descriptor_opened(receipt.name, receipt.path)
    return descriptor


def _copy_verified_receipt(receipt, destination: BinaryIO) -> None:
    descriptor = _open_receipt_descriptor(receipt)
    try:
        initial = os.fstat(descriptor)
        digest, total = hashlib.sha256(), 0
        while chunk := os.read(descriptor, 1024 * 1024):
            destination.write(chunk)
            digest.update(chunk)
            total += len(chunk)
        final = os.fstat(descriptor)
        if (not _receipt_stat_matches(receipt, final) or (initial.st_mtime_ns, initial.st_ctime_ns) != (final.st_mtime_ns, final.st_ctime_ns) or total != receipt.size_bytes or digest.hexdigest() != receipt.sha256):
            raise RuntimeError(f"R3 Angular5 bound source changed during snapshot: {receipt.name}")
        destination.flush()
        destination.seek(0)
    finally:
        os.close(descriptor)


def _read_receipt_snapshot(receipt) -> bytes:
    with io.BytesIO() as snapshot:
        _copy_verified_receipt(receipt, snapshot)
        return snapshot.getvalue()


@contextmanager
def _receipt_file_snapshot(receipt) -> Iterator[BinaryIO]:
    with tempfile.TemporaryFile(mode="w+b") as snapshot:
        _copy_verified_receipt(receipt, snapshot)
        yield snapshot


def _parse_gzip_csv(payload: bytes, *, name: str) -> pd.DataFrame:
    try:
        frame = pd.read_csv(io.BytesIO(payload), compression="gzip")
    except Exception as error:
        raise ValueError(f"{name} is not a valid gzip CSV") from error
    if frame.columns.has_duplicates:
        raise ValueError(f"{name} contains duplicate columns")
    return frame


def _reconstruct_angles(sources: Angular5R3Arm64Sources, *, sample_key: str, selection: SelectionConfig, root_snapshot: BinaryIO) -> pd.DataFrame:
    sample = sources.config.samples[sample_key]
    profile = resolve_input_profile(sample["input_profile"])
    rows: list[dict[str, Any]] = []
    observed_channels: set[int] = set()
    for event in iter_events(root_snapshot, profile.tree_name, is_data=False, entry_stop=sources.config.entry_stop, chunk_size_events=sources.config.chunk_size_events, profile=profile, extra_canonical_branches=selection.required_canonical_branches, include_source_entry=True):
        observed_channels.add(int(event["channelNumber"]))
        selected = select_event(event, selection, profile.momentum_unit)
        if not selected.accepted:
            continue
        if selected.candidate is None:
            raise ValueError("selected R3 Angular5 event has no reconstructed candidate")
        rows.append({"source_sample": sample["source_sample"], "source_entry": int(event["source_entry"]), **build_angular5(selected.candidate)})
    validate_channel_numbers(observed_channels, sample["channel_numbers"], sample["source_sample"])
    if not rows:
        raise ValueError(f"{sample_key}: no events passed the frozen selection")
    return pd.DataFrame(rows)


def _validate_identity(frame: pd.DataFrame, *, source: str) -> pd.MultiIndex:
    if any(name not in frame for name in SOURCE_IDENTITY):
        raise ValueError(f"{source} table is missing source identity")
    if frame[list(SOURCE_IDENTITY)].isna().any().any():
        raise ValueError(f"{source} table contains invalid source identity")
    entries = frame["source_entry"]
    if not pd.api.types.is_integer_dtype(entries.dtype) or pd.api.types.is_bool_dtype(entries.dtype) or (entries < 0).any():
        raise ValueError(f"{source} table contains invalid source identity")
    if not frame["source_sample"].isin(("higgs_345060", "zz_363490")).all():
        raise ValueError(f"{source} table contains invalid source identity")
    index = pd.MultiIndex.from_frame(frame[list(SOURCE_IDENTITY)])
    if index.has_duplicates:
        raise ValueError(f"{source} table contains duplicate source identity")
    return index


def _split_line_ending(line: bytes) -> tuple[bytes, bytes]:
    if line.endswith(b"\r\n"):
        return line[:-2], b"\r\n"
    if line.endswith(b"\n"):
        return line[:-1], b"\n"
    if line.endswith(b"\r"):
        return line[:-1], b"\r"
    return line, b""


def _parse_record(line: bytes, *, field_count: int) -> list[str]:
    try:
        record = list(csv.reader([line.decode("utf-8")], strict=True))
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError("identity CSV has an unsupported lexical record") from error
    if len(record) != 1 or len(record[0]) != field_count:
        raise ValueError("identity CSV record width changed")
    return record[0]


def _append_angular5_preserving_identity_csv(authoritative_payload: bytes, authoritative: pd.DataFrame, angles: pd.DataFrame) -> bytes:
    if angles.columns.tolist() != list(ANGULAR5_FEATURES) or len(angles) != len(authoritative):
        raise ValueError("Angular5 append column or row contract changed")
    _base._validate_angles(angles)
    try:
        records = _scan_csv_records(gzip.decompress(authoritative_payload))
    except (OSError, EOFError) as error:
        raise ValueError("identity table is not valid gzip") from error
    if len(records) != len(authoritative) + 1:
        raise ValueError("identity CSV record count mismatch")
    count = len(authoritative.columns)
    header, ending = _split_line_ending(records[0])
    if _parse_record(header, field_count=count) != list(authoritative.columns):
        raise ValueError("identity CSV header disagrees with parsed columns")
    output = bytearray(header + b"," + ",".join(ANGULAR5_FEATURES).encode("ascii") + ending)
    for record, values in zip(records[1:], angles.to_numpy(dtype=float), strict=True):
        content, ending = _split_line_ending(record)
        _parse_record(content, field_count=count)
        output.extend(content + b"," + ",".join(format(float(value), ".17g") for value in values).encode("ascii") + ending)
    payload = gzip.compress(bytes(output), mtime=0)
    final = _parse_gzip_csv(payload, name="enriched Angular5 table")
    if final.columns.tolist() != list(authoritative.columns) + list(ANGULAR5_FEATURES):
        raise ValueError("final Angular5 table column contract mismatch")
    for name in authoritative:
        try:
            pd.testing.assert_series_equal(authoritative[name].reset_index(drop=True), final[name].reset_index(drop=True), check_dtype=False, check_exact=True, check_names=False)
        except AssertionError as error:
            raise ValueError(f"identity old-column mismatch: {name}") from error
    return payload


def _legacy_duplicate_evidence(frame: pd.DataFrame) -> tuple[int, int, list[dict[str, Any]]]:
    legacy = ["runNumber", "eventNumber", "channelNumber"]
    if any(name not in frame for name in legacy):
        return 0, 0, []
    duplicated = frame.duplicated(legacy, keep=False)
    details = []
    for values, group in frame.loc[duplicated].groupby(legacy, sort=False):
        details.append({"legacy_key": dict(zip(legacy, (int(value) for value in values), strict=True)), "canonical_identities": [{name: value for name, value in zip(SOURCE_IDENTITY, row, strict=True)} for row in group[list(SOURCE_IDENTITY)].itertuples(index=False, name=None)]})
    return len(details), int(duplicated.sum()), details


def enrich_angular5_r3_arm64_mc(sources: Angular5R3Arm64Sources) -> _base.EnrichmentOutcome:
    if not isinstance(sources, Angular5R3Arm64Sources):
        raise TypeError("sources must be Angular5R3Arm64Sources")
    assert_angular5_r3_arm64_sources_unchanged(sources)
    authoritative_payload = _read_receipt_snapshot(sources.receipts["identity_table"])
    authoritative = _parse_gzip_csv(authoritative_payload, name="authoritative identity table")
    if authoritative.empty or authoritative.columns[-2:].tolist() != list(SOURCE_IDENTITY):
        raise ValueError("authoritative identity table has an invalid source identity schema")
    authoritative_index = _validate_identity(authoritative, source="authoritative")
    selection = SelectionConfig.from_mapping(sources.config.selection)
    frames = []
    for sample in ("higgs", "zz"):
        with _receipt_file_snapshot(sources.receipts[f"{sample}_root"]) as snapshot:
            frames.append(_reconstruct_angles(sources, sample_key=sample, selection=selection, root_snapshot=snapshot))
    reconstructed = pd.concat(frames, ignore_index=True)
    reconstructed_index = _validate_identity(reconstructed, source="reconstructed")
    if len(authoritative) != len(reconstructed) or set(authoritative_index) != set(reconstructed_index):
        raise ValueError("source identity coverage mismatch")
    aligned = reconstructed.set_index(list(SOURCE_IDENTITY)).loc[authoritative_index].reset_index()
    angles = aligned[list(ANGULAR5_FEATURES)]
    table_payload = _append_angular5_preserving_identity_csv(authoritative_payload, authoritative, angles)
    final = _parse_gzip_csv(table_payload, name="enriched Angular5 table")
    ranges = _base._validate_angles(final)
    groups, rows, details = _legacy_duplicate_evidence(authoritative)
    assert_angular5_r3_arm64_sources_unchanged(sources)
    identity = {"schema_version": "1.0", "status": "validated", "join_key": list(SOURCE_IDENTITY), "authoritative_rows": len(authoritative), "reconstructed_rows": len(reconstructed), "matched_rows": len(final), "authoritative_order_preserved": True, "complete_one_to_one_coverage": True, "old_columns": list(authoritative.columns), "old_columns_exact": True, "appended_columns": list(ANGULAR5_FEATURES), "legacy_duplicate_groups": groups, "legacy_duplicate_rows": rows, "legacy_duplicate_details": details}
    summary = {"schema_version": "1.0", "status": "complete", "role": "MC-only R3-ARM64 Angular5 enrichment", "row_count": len(final), "sample_counts": {name: int((final["source_sample"] == value).sum()) for name, value in (("higgs", "higgs_345060"), ("zz", "zz_363490"))}, "angular5_ranges": ranges}
    return _base.EnrichmentOutcome(_base._OUTCOME_TOKEN, authoritative_payload, table_payload, _base._deep_freeze(identity), _base._deep_freeze(summary), _source_binding(sources))


def _source_records(sources: Angular5R3Arm64Sources) -> dict[str, dict[str, Any]]:
    return {name: {"path": str(receipt.path), "device": receipt.device, "inode": receipt.inode, "size_bytes": receipt.size_bytes, "sha256": receipt.sha256} for name, receipt in sources.receipts.items()}


def _validate_outcome(outcome: _base.EnrichmentOutcome, sources: Angular5R3Arm64Sources) -> pd.DataFrame:
    if not isinstance(outcome, _base.EnrichmentOutcome) or outcome._source_binding != _source_binding(sources):
        raise ValueError("R3 Angular5 outcome does not belong to bound sources")
    final = _parse_gzip_csv(outcome._table_payload, name="bound enriched Angular5 table")
    if final.columns[-5:].tolist() != list(ANGULAR5_FEATURES):
        raise ValueError("R3 Angular5 outcome column contract mismatch")
    _validate_identity(final, source="bound enriched")
    _base._validate_angles(final)
    return final


def write_angular5_r3_arm64_artifacts(layout, *, sources: Angular5R3Arm64Sources, outcome: _base.EnrichmentOutcome) -> _base.Angular5ArtifactReceipt:
    descriptors = None
    try:
        descriptors = _base._open_claimed(layout)
        root = descriptors["."]
        if _safety._entry_exists(root, ".terminal.failed") or _safety._entry_exists(root, "failure.json"):
            raise RuntimeError("cannot write a failed R3 Angular5 run")
        _base._assert_layout(descriptors, state="empty")
        final = _validate_outcome(outcome, sources)
        serialized = {"config.yaml": sources.config_bytes, TABLE_NAME: outcome._table_payload, IDENTITY_NAME: _base._json_bytes(outcome.identity_validation)}
        summary = _base._deep_thaw(outcome.summary)
        summary["sources"] = _source_records(sources)
        summary["output_receipts"] = {"config.yaml": _base._pending_output_record(layout.config_snapshot, serialized["config.yaml"]), f"processed/{TABLE_NAME}": _base._pending_output_record(layout.processed_dir / TABLE_NAME, serialized[TABLE_NAME], row_count=len(final)), f"artifacts/{IDENTITY_NAME}": _base._pending_output_record(layout.artifacts_dir / IDENTITY_NAME, serialized[IDENTITY_NAME])}
        serialized[SUMMARY_NAME] = _base._json_bytes(summary)
        assert_angular5_r3_arm64_sources_unchanged(sources)
        _base._atomic_publish_bytes(root, layout.run_dir, "config.yaml", serialized["config.yaml"])
        _base._atomic_publish_bytes(descriptors["processed"], layout.processed_dir, TABLE_NAME, serialized[TABLE_NAME])
        for name in (IDENTITY_NAME, SUMMARY_NAME):
            _base._atomic_publish_bytes(descriptors["artifacts"], layout.artifacts_dir, name, serialized[name])
        _base._assert_layout(descriptors, state="artifacts")
        records, identities = _base._output_records(layout, descriptors)
        frozen = MappingProxyType({name: MappingProxyType(dict(record)) for name, record in records.items()})
        return _base.Angular5ArtifactReceipt(_base._RECEIPT_TOKEN, layout.directory_identities["."], frozen, MappingProxyType(identities))
    except BaseException as error:
        _base.record_angular5_failure(layout, error)
        raise
    finally:
        _base._close_descriptors(descriptors)


def publish_angular5_r3_arm64_manifest(layout, *, sources: Angular5R3Arm64Sources, receipt: _base.Angular5ArtifactReceipt, software: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, _base.Angular5ArtifactReceipt) or layout.directory_identities is None or receipt._run_identity != layout.directory_identities.get("."):
        raise ValueError("R3 Angular5 artifact receipt does not belong to this run")
    descriptors, staged, locked = None, None, False
    try:
        descriptors = _base._open_claimed(layout)
        root = descriptors["."]
        _safety._terminal_lock_acquire(root)
        locked = True
        if _safety._entry_exists(root, ".terminal.failed") or _safety._entry_exists(root, "failure.json"):
            raise RuntimeError("cannot publish a failed R3 Angular5 run")
        _base._assert_layout(descriptors, state="artifacts", terminal_lock=True)
        records, identities = _base._output_records(layout, descriptors)
        if records != dict(receipt._records) or identities != dict(receipt._identities):
            raise RuntimeError("R3 Angular5 output changed before manifest publication")
        manifest = {"schema_version": "1.0", "status": "complete", "role": "MC-only R3-ARM64 Angular5 enrichment", "join_key": list(SOURCE_IDENTITY), "appended_columns": list(ANGULAR5_FEATURES), "software": dict(software), "inputs": _source_records(sources), "outputs": records}
        staged = _base._stage_bytes(descriptors["artifacts"], MANIFEST_NAME, _base._json_bytes(manifest))
        def final_check() -> None:
            assert_angular5_r3_arm64_sources_unchanged(sources)
            current_records, current_identities = _base._output_records(layout, descriptors)
            if current_records != records or current_identities != identities:
                raise RuntimeError("R3 Angular5 output changed before manifest publication")
        _base._promote_no_clobber(descriptors["artifacts"], layout.artifacts_dir, staged, MANIFEST_NAME, immediate_check=final_check)
        staged = None
        _base._assert_layout(descriptors, state="complete", terminal_lock=True)
        return manifest
    except BaseException as error:
        if descriptors is not None:
            _safety._cleanup_staged(descriptors["artifacts"], staged)
        _base.record_angular5_failure(layout, error)
        raise
    finally:
        if descriptors is not None:
            _safety._cleanup_staged(descriptors["artifacts"], staged)
            if locked:
                _safety._terminal_lock_release(descriptors["."])
        _base._close_descriptors(descriptors)
