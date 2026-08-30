"""MC-only Angular5 enrichment and manifest-last publication."""

from __future__ import annotations

from contextlib import contextmanager
import csv
from dataclasses import dataclass
import gzip
import hashlib
import io
import json
from math import pi
import os
from pathlib import Path
import stat
import tempfile
from types import MappingProxyType
from typing import Any, BinaryIO, Iterator, Mapping

import numpy as np
import pandas as pd

from . import full_training_run as _safety
from .angular5 import ANGULAR5_FEATURES, build_angular5
from .angular5_enrichment_run import (
    Angular5OutputLayout,
    Angular5Sources,
    assert_angular5_sources_unchanged,
)
from .features import build_candidate_features
from .input_profiles import resolve_input_profile
from .io import iter_events, validate_channel_numbers
from .selection import SelectionConfig, select_event
from .split import event_split
from .weights import (
    MCNormalization,
    physical_event_weight,
    training_weights,
)


EVENT_KEY = ("runNumber", "eventNumber", "channelNumber")
IDENTITY_NAME = "identity_validation.json"
SUMMARY_NAME = "angular5_summary.json"
TABLE_NAME = "mc_events_angular5.csv.gz"
MANIFEST_NAME = "run_manifest.json"


_OUTCOME_TOKEN = object()


@dataclass(frozen=True, init=False)
class EnrichmentOutcome:
    _authoritative_payload: bytes
    _table_payload: bytes
    _identity_validation: Mapping[str, Any]
    _summary: Mapping[str, Any]
    _source_binding: tuple[tuple[Any, ...], ...]

    def __new__(
        cls,
        token: object = None,
        authoritative_payload: bytes | None = None,
        table_payload: bytes | None = None,
        identity_validation: Mapping[str, Any] | None = None,
        summary: Mapping[str, Any] | None = None,
        source_binding: tuple[tuple[Any, ...], ...] | None = None,
    ):
        if (
            token is not _OUTCOME_TOKEN
            or authoritative_payload is None
            or table_payload is None
            or identity_validation is None
            or summary is None
            or source_binding is None
        ):
            raise TypeError("EnrichmentOutcome is returned by enrich_angular5_mc")
        return super().__new__(cls)

    def __init__(
        self,
        token: object,
        authoritative_payload: bytes,
        table_payload: bytes,
        identity_validation: Mapping[str, Any],
        summary: Mapping[str, Any],
        source_binding: tuple[tuple[Any, ...], ...],
    ) -> None:
        object.__setattr__(self, "_authoritative_payload", authoritative_payload)
        object.__setattr__(self, "_table_payload", table_payload)
        object.__setattr__(self, "_identity_validation", identity_validation)
        object.__setattr__(self, "_summary", summary)
        object.__setattr__(self, "_source_binding", source_binding)

    @property
    def frame(self) -> pd.DataFrame:
        """Return an isolated parse of the immutable final gzip payload."""
        return _parse_gzip_csv(self._table_payload, name="enriched Angular5 table")

    @property
    def identity_validation(self) -> Mapping[str, Any]:
        return self._identity_validation

    @property
    def summary(self) -> Mapping[str, Any]:
        return self._summary


_RECEIPT_TOKEN = object()


@dataclass(frozen=True, init=False)
class Angular5ArtifactReceipt:
    _run_identity: tuple[int, int]
    _records: Mapping[str, Mapping[str, Any]]
    _identities: Mapping[str, tuple[int, int]]

    def __new__(
        cls,
        token: object = None,
        run_identity: tuple[int, int] | None = None,
        records: Mapping[str, Mapping[str, Any]] | None = None,
        identities: Mapping[str, tuple[int, int]] | None = None,
    ):
        if (
            token is not _RECEIPT_TOKEN
            or run_identity is None
            or records is None
            or identities is None
        ):
            raise TypeError(
                "Angular5ArtifactReceipt is returned by write_angular5_artifacts"
            )
        return super().__new__(cls)

    def __init__(
        self,
        token: object,
        run_identity: tuple[int, int],
        records: Mapping[str, Mapping[str, Any]],
        identities: Mapping[str, tuple[int, int]],
    ) -> None:
        object.__setattr__(self, "_run_identity", run_identity)
        object.__setattr__(self, "_records", records)
        object.__setattr__(self, "_identities", identities)


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _deep_freeze(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _deep_thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _deep_thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_deep_thaw(item) for item in value]
    return value


def _source_binding(sources: Angular5Sources) -> tuple[tuple[Any, ...], ...]:
    records = tuple(
        (
            name,
            str(receipt.path),
            receipt.device,
            receipt.inode,
            receipt.size_bytes,
            receipt.sha256,
        )
        for name, receipt in sorted(sources.receipts.items())
    )
    return records + (
        ("config_bytes", hashlib.sha256(sources.config_bytes).hexdigest()),
    )


def _receipt_stat_matches(receipt, metadata: os.stat_result) -> bool:
    return (
        stat.S_ISREG(metadata.st_mode)
        and int(metadata.st_dev) == receipt.device
        and int(metadata.st_ino) == receipt.inode
        and int(metadata.st_size) == receipt.size_bytes
    )


def _after_receipt_descriptor_opened(name: str, path: Path) -> None:
    """Test seam after a receipt identity is bound to an open descriptor."""


def _open_receipt_descriptor(receipt) -> int:
    try:
        descriptor = os.open(
            receipt.path,
            os.O_RDONLY
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as error:
        raise RuntimeError(
            f"Angular5 bound source could not be opened: {receipt.name}"
        ) from error
    metadata = os.fstat(descriptor)
    if not _receipt_stat_matches(receipt, metadata):
        os.close(descriptor)
        raise RuntimeError(f"Angular5 bound source identity changed: {receipt.name}")
    _after_receipt_descriptor_opened(receipt.name, receipt.path)
    return descriptor


def _copy_verified_receipt(receipt, destination: BinaryIO) -> None:
    descriptor = _open_receipt_descriptor(receipt)
    try:
        initial = os.fstat(descriptor)
        digest = hashlib.sha256()
        total = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            destination.write(chunk)
            digest.update(chunk)
            total += len(chunk)
        final = os.fstat(descriptor)
        if (
            not _receipt_stat_matches(receipt, final)
            or (initial.st_mtime_ns, initial.st_ctime_ns)
            != (final.st_mtime_ns, final.st_ctime_ns)
            or total != receipt.size_bytes
            or digest.hexdigest() != receipt.sha256
        ):
            raise RuntimeError(
                f"Angular5 bound source changed during snapshot: {receipt.name}"
            )
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


def _normalization_override(sample: Mapping[str, Any]) -> MCNormalization | None:
    raw = sample.get("normalization")
    if raw is None:
        return None
    return MCNormalization(
        raw["xsec_pb"],
        raw["k_factor"],
        raw["filter_efficiency"],
        raw["sum_of_weights"],
    )


def _reconstruct_sample(
    sources: Angular5Sources,
    *,
    sample_key: str,
    selection: SelectionConfig,
    root_snapshot: BinaryIO,
) -> pd.DataFrame:
    sample = sources.config.samples[sample_key]
    profile = resolve_input_profile(sample["input_profile"])
    path = sources.receipts[f"{sample_key}_root"].path
    normalization = _normalization_override(sample)
    rows: list[dict[str, Any]] = []
    observed_channels: set[int] = set()
    for event in iter_events(
        root_snapshot,
        profile.tree_name,
        is_data=False,
        entry_stop=sources.config.entry_stop,
        chunk_size_events=sources.config.chunk_size_events,
        profile=profile,
        extra_canonical_branches=selection.required_canonical_branches,
    ):
        channel = int(event["channelNumber"])
        observed_channels.add(channel)
        if normalization is None:
            normalization = MCNormalization.from_event(event)
        weight = physical_event_weight(
            event,
            sources.config.luminosity_pb,
            normalization=normalization,
            require_event_normalization=profile.normalization_in_events,
        )
        selected = select_event(event, selection, profile.momentum_unit)
        if not selected.accepted:
            continue
        if selected.candidate is None:
            raise ValueError("selected Angular5 event has no reconstructed candidate")
        row = build_candidate_features(event, selected.candidate)
        if sample.get("normalization") is not None:
            row.update(
                xsec=normalization.xsec_pb,
                kfac=normalization.k_factor,
                filteff=normalization.filter_efficiency,
                sum_of_weights=normalization.sum_of_weights,
            )
        row["physical_weight"] = weight
        row.update(build_angular5(selected.candidate))
        rows.append(row)

    if normalization is None:
        raise ValueError(f"{sample_key}: no MC events were read from {path}")
    validate_channel_numbers(
        observed_channels,
        sample["channel_numbers"],
        f"{sample_key}_{'-'.join(str(value) for value in sample['channel_numbers'])}",
    )
    if not rows:
        raise ValueError(f"{sample_key}: no events passed the frozen selection")
    frame = pd.DataFrame(rows)
    frame["label"] = int(sample["label"])
    frame["train_weight"] = training_weights(frame["physical_weight"])
    frame["split"] = [
        event_split(event, channel)
        for event, channel in zip(frame["eventNumber"], frame["channelNumber"])
    ]
    return frame


def _validate_key(frame: pd.DataFrame, *, source: str) -> pd.MultiIndex:
    missing = [name for name in EVENT_KEY if name not in frame]
    if missing:
        raise ValueError(f"{source} table is missing event-key columns: {missing}")
    if frame[list(EVENT_KEY)].isna().any().any():
        raise ValueError(f"{source} table contains an invalid event key")
    for name in EVENT_KEY:
        dtype = frame[name].dtype
        if not pd.api.types.is_integer_dtype(dtype) or pd.api.types.is_bool_dtype(dtype):
            raise ValueError(f"{source} table contains an invalid event key")
    keys = pd.MultiIndex.from_frame(frame[list(EVENT_KEY)])
    if keys.has_duplicates:
        raise ValueError(f"{source} table contains duplicate event keys")
    return keys


def _assert_old_columns_exact(
    authoritative: pd.DataFrame,
    reconstructed: pd.DataFrame,
) -> None:
    for name in authoritative.columns:
        try:
            pd.testing.assert_series_equal(
                authoritative[name].reset_index(drop=True),
                reconstructed[name].reset_index(drop=True),
                check_dtype=False,
                check_exact=True,
                check_names=False,
            )
        except AssertionError as error:
            raise ValueError(f"Angular5 old-column mismatch: {name}") from error


def _validate_angles(frame: pd.DataFrame) -> dict[str, dict[str, float | bool]]:
    values = frame[list(ANGULAR5_FEATURES)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Angular5 values must be finite")
    if not ((values[:, :3] >= -1.0) & (values[:, :3] <= 1.0)).all():
        raise ValueError("Angular5 cosine is outside [-1, 1]")
    if not ((values[:, 3:] >= -pi) & (values[:, 3:] < pi)).all():
        raise ValueError("Angular5 signed angle is outside [-pi, pi)")
    return {
        name: {
            "minimum": float(frame[name].min()),
            "maximum": float(frame[name].max()),
            "finite_and_in_range": True,
        }
        for name in ANGULAR5_FEATURES
    }


def _split_line_ending(line: bytes) -> tuple[bytes, bytes]:
    if line.endswith(b"\r\n"):
        return line[:-2], b"\r\n"
    if line.endswith(b"\n"):
        return line[:-1], b"\n"
    if line.endswith(b"\r"):
        return line[:-1], b"\r"
    return line, b""


def _parse_single_csv_record(line: bytes, *, field_count: int) -> list[str]:
    try:
        text = line.decode("utf-8")
        records = list(csv.reader([text], strict=True))
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError("authoritative MC CSV has an unsupported lexical record") from error
    if len(records) != 1 or len(records[0]) != field_count:
        raise ValueError("authoritative MC CSV record width changed")
    return records[0]


def _append_angular5_preserving_authoritative_csv(
    authoritative_payload: bytes,
    authoritative: pd.DataFrame,
    angles: pd.DataFrame,
) -> bytes:
    """Append Angular5 tokens without regenerating any authoritative token."""
    if angles.columns.tolist() != list(ANGULAR5_FEATURES):
        raise ValueError("Angular5 append columns do not match the frozen order")
    if len(angles) != len(authoritative):
        raise ValueError("Angular5 append row count mismatch")
    _validate_angles(angles)
    try:
        raw = gzip.decompress(authoritative_payload)
    except (OSError, EOFError) as error:
        raise ValueError("authoritative MC table is not valid gzip") from error
    lines = raw.splitlines(keepends=True)
    if len(lines) != len(authoritative) + 1:
        raise ValueError(
            "authoritative MC CSV must contain one physical line per parsed row"
        )
    field_count = len(authoritative.columns)
    header_content, header_ending = _split_line_ending(lines[0])
    if _parse_single_csv_record(header_content, field_count=field_count) != list(
        authoritative.columns
    ):
        raise ValueError("authoritative MC CSV header disagrees with parsed columns")
    appended_header = ",".join(ANGULAR5_FEATURES).encode("ascii")
    output = bytearray(header_content)
    output.extend(b",")
    output.extend(appended_header)
    output.extend(header_ending)

    values = angles.to_numpy(dtype=float)
    for line, row in zip(lines[1:], values, strict=True):
        content, ending = _split_line_ending(line)
        _parse_single_csv_record(content, field_count=field_count)
        tokens = ",".join(format(float(value), ".17g") for value in row).encode(
            "ascii"
        )
        output.extend(content)
        output.extend(b",")
        output.extend(tokens)
        output.extend(ending)

    final_payload = gzip.compress(bytes(output), mtime=0)
    final = _parse_gzip_csv(final_payload, name="final Angular5 table")
    expected_columns = list(authoritative.columns) + list(ANGULAR5_FEATURES)
    if final.columns.tolist() != expected_columns:
        raise ValueError("final Angular5 table column contract mismatch")
    _assert_old_columns_exact(authoritative, final[list(authoritative.columns)])
    _validate_angles(final)
    return final_payload


def _source_records(sources: Angular5Sources) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "path": str(receipt.path),
            "device": receipt.device,
            "inode": receipt.inode,
            "size_bytes": receipt.size_bytes,
            "sha256": receipt.sha256,
        }
        for name, receipt in sources.receipts.items()
    }


def enrich_angular5_mc(sources: Angular5Sources) -> EnrichmentOutcome:
    """Rebuild selected MC angles and join them to the authoritative table."""
    if not isinstance(sources, Angular5Sources):
        raise TypeError("sources must be Angular5Sources")
    assert_angular5_sources_unchanged(sources)
    authoritative_payload = _read_receipt_snapshot(sources.receipts["task4a_mc"])
    authoritative = _parse_gzip_csv(
        authoritative_payload, name="authoritative MC table"
    )
    if authoritative.empty:
        raise ValueError("authoritative MC table is empty")
    authoritative_keys = _validate_key(authoritative, source="authoritative")

    selection = SelectionConfig.from_mapping(sources.config.selection)
    sample_frames = []
    for sample_key in ("higgs", "zz"):
        with _receipt_file_snapshot(
            sources.receipts[f"{sample_key}_root"]
        ) as root_snapshot:
            sample_frames.append(
                _reconstruct_sample(
                    sources,
                    sample_key=sample_key,
                    selection=selection,
                    root_snapshot=root_snapshot,
                )
            )
    reconstructed = pd.concat(sample_frames, ignore_index=True)
    reconstructed_keys = _validate_key(reconstructed, source="reconstructed")
    if len(authoritative) != len(reconstructed) or set(authoritative_keys) != set(
        reconstructed_keys
    ):
        raise ValueError("Angular5 event-key coverage mismatch")

    old_columns = tuple(authoritative.columns)
    rebuilt_old = tuple(
        name for name in reconstructed.columns if name not in ANGULAR5_FEATURES
    )
    if set(old_columns) != set(rebuilt_old) or len(old_columns) != len(rebuilt_old):
        raise ValueError("Angular5 reconstructed old-column schema mismatch")
    aligned = reconstructed.set_index(list(EVENT_KEY)).loc[authoritative_keys]
    aligned = aligned.reset_index()
    aligned = aligned[list(old_columns) + list(ANGULAR5_FEATURES)]
    # The frozen contract compares parsed CSV values.  Round-trip the freshly
    # reconstructed old columns through the same textual CSV boundary before
    # making the exact comparison; pandas' decimal parser is authoritative on
    # both sides of that boundary.
    parsed_reconstructed = pd.read_csv(
        io.StringIO(aligned[list(old_columns)].to_csv(index=False))
    )
    _assert_old_columns_exact(authoritative, parsed_reconstructed)

    angles = aligned[list(ANGULAR5_FEATURES)].reset_index(drop=True)
    table_payload = _append_angular5_preserving_authoritative_csv(
        authoritative_payload,
        authoritative,
        angles,
    )
    output = _parse_gzip_csv(table_payload, name="enriched Angular5 table")
    ranges = _validate_angles(output)
    assert_angular5_sources_unchanged(sources)

    identity = {
        "schema_version": "1.0",
        "status": "validated",
        "join_key": list(EVENT_KEY),
        "authoritative_rows": len(authoritative),
        "reconstructed_rows": len(reconstructed),
        "matched_rows": len(output),
        "authoritative_order_preserved": True,
        "unique_event_keys": True,
        "complete_one_to_one_coverage": True,
        "old_columns": list(old_columns),
        "old_columns_exact": True,
        "appended_columns": list(ANGULAR5_FEATURES),
    }
    summary = {
        "schema_version": "1.0",
        "status": "complete",
        "role": "MC-only Angular5 enrichment",
        "row_count": len(output),
        "sample_counts": {
            "higgs": int((output["label"] == 1).sum()),
            "zz": int((output["label"] == 0).sum()),
        },
        "angular5_ranges": ranges,
        "sources": _source_records(sources),
    }
    return EnrichmentOutcome(
        _OUTCOME_TOKEN,
        authoritative_payload,
        table_payload,
        _deep_freeze(identity),
        _deep_freeze(summary),
        _source_binding(sources),
    )


def _validate_outcome_payload(
    outcome: EnrichmentOutcome, sources: Angular5Sources
) -> pd.DataFrame:
    if outcome._source_binding != _source_binding(sources):
        raise ValueError("Angular5 outcome does not belong to the bound sources")
    authoritative = _parse_gzip_csv(
        outcome._authoritative_payload,
        name="bound authoritative MC table",
    )
    final = _parse_gzip_csv(
        outcome._table_payload,
        name="bound enriched Angular5 table",
    )
    expected_columns = list(authoritative.columns) + list(ANGULAR5_FEATURES)
    if final.columns.tolist() != expected_columns:
        raise ValueError("bound Angular5 payload column contract mismatch")
    _assert_old_columns_exact(authoritative, final[list(authoritative.columns)])
    _validate_angles(final)
    identity = outcome.identity_validation
    if (
        tuple(identity["old_columns"]) != tuple(authoritative.columns)
        or tuple(identity["appended_columns"]) != ANGULAR5_FEATURES
        or int(identity["matched_rows"]) != len(final)
        or identity["old_columns_exact"] is not True
    ):
        raise ValueError("bound Angular5 identity evidence disagrees with final payload")
    return final


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            _deep_thaw(payload),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _pending_output_record(
    path: Path, payload: bytes, *, row_count: int | None = None
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": str(path),
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    if row_count is not None:
        record["row_count"] = row_count
    return record


def _before_no_clobber_promote(destination: Path) -> None:
    """Test seam immediately before a no-clobber artifact promotion."""


def _before_final_source_revalidation() -> None:
    """Test seam immediately before the manifest's final source check."""


def _stage_bytes(descriptor: int, final_name: str, payload: bytes) -> str:
    return _safety._stage_bytes(descriptor, final_name, payload)


def _promote_no_clobber(
    descriptor: int,
    parent: Path,
    staged: str,
    final_name: str,
    *,
    immediate_check=None,
) -> None:
    destination = parent / final_name
    _before_no_clobber_promote(destination)
    if immediate_check is not None:
        immediate_check()
    try:
        os.link(
            staged,
            final_name,
            src_dir_fd=descriptor,
            dst_dir_fd=descriptor,
            follow_symlinks=False,
        )
    except FileExistsError as error:
        raise FileExistsError(f"output entry already exists: {destination}") from error
    finally:
        _safety._cleanup_staged(descriptor, staged)


def _atomic_publish_bytes(
    descriptor: int, parent: Path, final_name: str, payload: bytes
) -> None:
    staged = _stage_bytes(descriptor, final_name, payload)
    _promote_no_clobber(descriptor, parent, staged, final_name)


def _close_descriptors(descriptors: Mapping[str, int] | None) -> None:
    if descriptors is not None:
        for descriptor in reversed(tuple(descriptors.values())):
            os.close(descriptor)


def _open_claimed(layout: Angular5OutputLayout) -> dict[str, int]:
    expected = layout.directory_identities
    if expected is None:
        raise RuntimeError("Angular5 output directory has not been claimed")
    descriptors: dict[str, int] = {}
    try:
        root = _safety._open_absolute_directory_no_follow(layout.run_dir)
        descriptors["."] = root
        if _safety._identity(root) != expected.get("."):
            raise ValueError("Angular5 run ownership changed")
        for name in ("processed", "artifacts"):
            child = os.open(name, _safety._directory_flags(), dir_fd=root)
            descriptors[name] = child
            if _safety._identity(child) != expected.get(name):
                raise ValueError(f"Angular5 child ownership changed: {name}")
        return descriptors
    except Exception:
        _close_descriptors(descriptors)
        raise


def _assert_layout(
    descriptors: Mapping[str, int],
    *,
    state: str,
    terminal_lock: bool = False,
    ignored_artifacts: frozenset[str] = frozenset(),
) -> None:
    root_expected = {"processed", "artifacts"}
    if state != "empty":
        root_expected.add("config.yaml")
    if terminal_lock:
        root_expected.add(".terminal.lock")
    if set(os.listdir(descriptors["."])) != root_expected:
        raise FileExistsError("Angular5 run root contract mismatch")
    processed_expected = set() if state == "empty" else {TABLE_NAME}
    artifacts_expected = {
        "empty": set(),
        "artifacts": {IDENTITY_NAME, SUMMARY_NAME},
        "complete": {IDENTITY_NAME, SUMMARY_NAME, MANIFEST_NAME},
    }[state]
    artifacts_actual = set(os.listdir(descriptors["artifacts"])) - set(
        ignored_artifacts
    )
    if set(os.listdir(descriptors["processed"])) != processed_expected:
        raise FileExistsError("Angular5 processed output contract mismatch")
    if artifacts_actual != artifacts_expected:
        raise FileExistsError("Angular5 artifact output contract mismatch")


def _read_regular(
    descriptor: int, name: str
) -> tuple[bytes, tuple[int, int]]:
    try:
        source = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=descriptor,
        )
    except OSError as error:
        raise ValueError(f"Angular5 output is missing or unsafe: {name}") from error
    try:
        metadata = os.fstat(source)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"Angular5 output is not a regular file: {name}")
        chunks: list[bytes] = []
        while chunk := os.read(source, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks), (metadata.st_dev, metadata.st_ino)
    finally:
        os.close(source)


def _output_records(
    layout: Angular5OutputLayout,
    descriptors: Mapping[str, int],
) -> tuple[dict[str, dict[str, Any]], dict[str, tuple[int, int]]]:
    mapping = {
        "config.yaml": (".", "config.yaml", False),
        f"processed/{TABLE_NAME}": ("processed", TABLE_NAME, True),
        f"artifacts/{IDENTITY_NAME}": ("artifacts", IDENTITY_NAME, False),
        f"artifacts/{SUMMARY_NAME}": ("artifacts", SUMMARY_NAME, False),
    }
    records: dict[str, dict[str, Any]] = {}
    identities: dict[str, tuple[int, int]] = {}
    for relative, (directory, name, csv_rows) in mapping.items():
        payload, identity = _read_regular(descriptors[directory], name)
        record: dict[str, Any] = {
            "path": str(layout.run_dir / relative),
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        if csv_rows:
            try:
                record["row_count"] = len(
                    pd.read_csv(io.BytesIO(payload), compression="gzip")
                )
            except Exception as error:
                raise ValueError("published Angular5 CSV is invalid") from error
        records[relative] = record
        identities[relative] = identity
    return records, identities


def _open_verified_root(layout: Angular5OutputLayout) -> int:
    if layout.directory_identities is None:
        raise RuntimeError("Angular5 output directory has not been claimed")
    root = _safety._open_absolute_directory_no_follow(layout.run_dir)
    if _safety._identity(root) != layout.directory_identities.get("."):
        os.close(root)
        raise ValueError("Angular5 run ownership changed")
    return root


def _manifest_present(root: int) -> bool:
    try:
        artifacts = os.open("artifacts", _safety._directory_flags(), dir_fd=root)
    except OSError:
        return False
    try:
        return _safety._entry_exists(artifacts, MANIFEST_NAME)
    finally:
        os.close(artifacts)


def _install_failure_locked(
    root: int, run_dir: Path, error: BaseException
) -> None:
    if _manifest_present(root):
        return
    try:
        os.mkdir(".terminal.failed", dir_fd=root)
    except FileExistsError:
        pass
    if _safety._entry_exists(root, "failure.json"):
        return
    try:
        _atomic_publish_bytes(
            root,
            run_dir,
            "failure.json",
            _json_bytes(
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "message": str(error),
                }
            ),
        )
    except BaseException:
        pass


def record_angular5_failure(
    layout: Angular5OutputLayout, error: BaseException
) -> None:
    """Best-effort terminal failure transition for an already-claimed run."""
    try:
        root = _open_verified_root(layout)
    except BaseException:
        return
    locked = False
    try:
        _safety._terminal_lock_acquire(root)
        locked = True
        _install_failure_locked(root, layout.run_dir, error)
    except BaseException:
        pass
    finally:
        if locked:
            _safety._terminal_lock_release(root)
        os.close(root)


def write_angular5_artifacts(
    layout: Angular5OutputLayout,
    *,
    sources: Angular5Sources,
    outcome: EnrichmentOutcome,
) -> Angular5ArtifactReceipt:
    """Publish the four approved non-manifest artifacts without clobbering."""
    if not isinstance(outcome, EnrichmentOutcome):
        raise TypeError("outcome must be EnrichmentOutcome")
    descriptors: dict[str, int] | None = None
    try:
        descriptors = _open_claimed(layout)
        root = descriptors["."]
        if _safety._entry_exists(root, ".terminal.failed") or _safety._entry_exists(
            root, "failure.json"
        ):
            raise RuntimeError("cannot write a failed Angular5 run")
        _assert_layout(descriptors, state="empty")
        final_frame = _validate_outcome_payload(outcome, sources)
        table_payload = outcome._table_payload
        serialized: dict[str, bytes] = {
            "config.yaml": sources.config_bytes,
            TABLE_NAME: table_payload,
            IDENTITY_NAME: _json_bytes(outcome.identity_validation),
        }
        summary = _deep_thaw(outcome.summary)
        summary["output_receipts"] = {
            "config.yaml": _pending_output_record(
                layout.config_snapshot, serialized["config.yaml"]
            ),
            f"processed/{TABLE_NAME}": _pending_output_record(
                layout.processed_dir / TABLE_NAME,
                serialized[TABLE_NAME],
                row_count=len(final_frame),
            ),
            f"artifacts/{IDENTITY_NAME}": _pending_output_record(
                layout.artifacts_dir / IDENTITY_NAME,
                serialized[IDENTITY_NAME],
            ),
        }
        serialized[SUMMARY_NAME] = _json_bytes(summary)
        assert_angular5_sources_unchanged(sources)
        _atomic_publish_bytes(
            root, layout.run_dir, "config.yaml", serialized["config.yaml"]
        )
        _atomic_publish_bytes(
            descriptors["processed"],
            layout.processed_dir,
            TABLE_NAME,
            serialized[TABLE_NAME],
        )
        for name in (IDENTITY_NAME, SUMMARY_NAME):
            _atomic_publish_bytes(
                descriptors["artifacts"],
                layout.artifacts_dir,
                name,
                serialized[name],
            )
        _assert_layout(descriptors, state="artifacts")
        records, identities = _output_records(layout, descriptors)
        frozen_records = MappingProxyType(
            {
                name: MappingProxyType(dict(record))
                for name, record in records.items()
            }
        )
        return Angular5ArtifactReceipt(
            _RECEIPT_TOKEN,
            layout.directory_identities["."],
            frozen_records,
            MappingProxyType(identities),
        )
    except BaseException as error:
        record_angular5_failure(layout, error)
        raise
    finally:
        _close_descriptors(descriptors)


def publish_angular5_manifest(
    layout: Angular5OutputLayout,
    *,
    sources: Angular5Sources,
    receipt: Angular5ArtifactReceipt,
    software: Mapping[str, Any],
) -> dict[str, Any]:
    """Promote the complete manifest last after final source/output checks."""
    if not isinstance(receipt, Angular5ArtifactReceipt):
        raise TypeError("publisher requires an Angular5ArtifactReceipt")
    if (
        layout.directory_identities is None
        or receipt._run_identity != layout.directory_identities.get(".")
    ):
        raise ValueError("Angular5 artifact receipt does not belong to this run")
    descriptors: dict[str, int] | None = None
    locked = False
    staged: str | None = None
    try:
        descriptors = _open_claimed(layout)
        root = descriptors["."]
        _safety._terminal_lock_acquire(root)
        locked = True
        if _safety._entry_exists(root, ".terminal.failed") or _safety._entry_exists(
            root, "failure.json"
        ):
            raise RuntimeError("cannot publish a failed Angular5 run")
        _assert_layout(descriptors, state="artifacts", terminal_lock=True)
        records, identities = _output_records(layout, descriptors)
        if records != dict(receipt._records) or identities != dict(receipt._identities):
            raise RuntimeError("Angular5 output changed before manifest publication")
        manifest = {
            "schema_version": "1.0",
            "status": "complete",
            "role": "MC-only Angular5 enrichment",
            "join_key": list(EVENT_KEY),
            "appended_columns": list(ANGULAR5_FEATURES),
            "software": dict(software),
            "inputs": _source_records(sources),
            "outputs": records,
        }
        serialized = _json_bytes(manifest)
        staged = _stage_bytes(descriptors["artifacts"], MANIFEST_NAME, serialized)
        _before_final_source_revalidation()

        def final_check() -> None:
            assert_angular5_sources_unchanged(sources)
            current_records, current_identities = _output_records(layout, descriptors)
            if current_records != records or current_identities != identities:
                raise RuntimeError("Angular5 output changed before manifest publication")
            current = _open_claimed(layout)
            _close_descriptors(current)

        _promote_no_clobber(
            descriptors["artifacts"],
            layout.artifacts_dir,
            staged,
            MANIFEST_NAME,
            immediate_check=final_check,
        )
        staged = None
        _assert_layout(descriptors, state="complete", terminal_lock=True)
        return manifest
    except BaseException as error:
        if descriptors is not None:
            _safety._cleanup_staged(descriptors["artifacts"], staged)
            staged = None
            if locked:
                _install_failure_locked(descriptors["."], layout.run_dir, error)
            else:
                record_angular5_failure(layout, error)
        else:
            record_angular5_failure(layout, error)
        raise
    finally:
        if descriptors is not None:
            _safety._cleanup_staged(descriptors["artifacts"], staged)
            if locked:
                _safety._terminal_lock_release(descriptors["."])
        _close_descriptors(descriptors)
