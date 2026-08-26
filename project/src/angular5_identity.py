"""Pure, literal-preserving bootstrap of stable MC source identities."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import gzip
import io
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd


SOURCE_IDENTITY = ("source_sample", "source_entry")
LEGACY_EVENT_KEY = ("runNumber", "eventNumber", "channelNumber")
SAMPLE_CHANNELS = MappingProxyType(
    {"higgs_345060": 345060, "zz_363490": 363490}
)


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _deep_freeze(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _parse_gzip_csv(payload: bytes, *, name: str) -> pd.DataFrame:
    if not isinstance(payload, bytes):
        raise TypeError(f"{name} payload must be bytes")
    try:
        return pd.read_csv(io.BytesIO(payload), compression="gzip")
    except (EOFError, OSError, UnicodeDecodeError, pd.errors.ParserError) as error:
        raise ValueError(f"{name} is not a valid gzip CSV") from error


def _assert_old_columns_exact(
    authoritative: pd.DataFrame, reconstructed: pd.DataFrame
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
            raise ValueError(f"source identity old-column mismatch: {name}") from error


def _split_line_ending(line: bytes) -> tuple[bytes, bytes]:
    if line.endswith(b"\r\n"):
        return line[:-2], b"\r\n"
    if line.endswith(b"\n"):
        return line[:-1], b"\n"
    if line.endswith(b"\r"):
        return line[:-1], b"\r"
    return line, b""


def _parse_single_record(line: bytes, *, field_count: int) -> list[str]:
    try:
        decoded = line.decode("utf-8")
        records = list(csv.reader([decoded], strict=True))
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError("authoritative MC CSV has an unsupported record") from error
    if len(records) != 1 or len(records[0]) != field_count:
        raise ValueError("authoritative MC CSV record width changed")
    return records[0]


def _csv_tokens(values: tuple[str, int]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="")
    writer.writerow(values)
    return stream.getvalue().encode("utf-8")


def _append_identity_tokens(
    authoritative_payload: bytes,
    authoritative: pd.DataFrame,
    identities: list[tuple[str, int]],
) -> bytes:
    try:
        raw = gzip.decompress(authoritative_payload)
    except (EOFError, OSError) as error:
        raise ValueError("authoritative MC table is not valid gzip") from error
    lines = raw.splitlines(keepends=True)
    if len(lines) != len(authoritative) + 1:
        raise ValueError(
            "authoritative MC CSV must contain one physical line per parsed row"
        )
    field_count = len(authoritative.columns)
    header, header_ending = _split_line_ending(lines[0])
    if _parse_single_record(header, field_count=field_count) != list(
        authoritative.columns
    ):
        raise ValueError("authoritative MC CSV header disagrees with parsed columns")

    output = bytearray(header)
    output.extend(b",source_sample,source_entry")
    output.extend(header_ending)
    for line, identity in zip(lines[1:], identities, strict=True):
        content, ending = _split_line_ending(line)
        _parse_single_record(content, field_count=field_count)
        output.extend(content)
        output.extend(b",")
        output.extend(_csv_tokens(identity))
        output.extend(ending)
    return gzip.compress(bytes(output), mtime=0)


_OUTCOME_TOKEN = object()


@dataclass(frozen=True, init=False)
class IdentityOutcome:
    _table_payload: bytes
    _evidence: Mapping[str, Any]

    def __new__(
        cls,
        token: object = None,
        table_payload: bytes | None = None,
        evidence: Mapping[str, Any] | None = None,
    ):
        if token is not _OUTCOME_TOKEN or table_payload is None or evidence is None:
            raise TypeError(
                "IdentityOutcome is returned by build_source_identity_baseline"
            )
        return super().__new__(cls)

    def __init__(
        self, token: object, table_payload: bytes, evidence: Mapping[str, Any]
    ) -> None:
        object.__setattr__(self, "_table_payload", table_payload)
        object.__setattr__(self, "_evidence", evidence)

    @property
    def table_payload(self) -> bytes:
        return self._table_payload

    @property
    def frame(self) -> pd.DataFrame:
        return _parse_gzip_csv(self._table_payload, name="source-identity table")

    @property
    def evidence(self) -> Mapping[str, Any]:
        return self._evidence


def _validated_sample(
    sample_name: str,
    reconstructed: pd.DataFrame,
    authoritative: pd.DataFrame,
) -> pd.DataFrame:
    if not isinstance(reconstructed, pd.DataFrame):
        raise TypeError(f"{sample_name} reconstructed value must be a DataFrame")
    expected_columns = list(authoritative.columns) + list(SOURCE_IDENTITY)
    if reconstructed.columns.tolist() != expected_columns:
        raise ValueError(f"{sample_name} reconstructed schema mismatch")
    if len(reconstructed) != len(authoritative):
        raise ValueError(f"{sample_name} row count mismatch")
    if reconstructed["source_sample"].isna().any() or not reconstructed[
        "source_sample"
    ].eq(sample_name).all():
        raise ValueError(f"{sample_name} contains an invalid source_sample")
    entries = reconstructed["source_entry"]
    if (
        entries.isna().any()
        or not pd.api.types.is_integer_dtype(entries.dtype)
        or pd.api.types.is_bool_dtype(entries.dtype)
        or (entries < 0).any()
    ):
        raise ValueError(f"{sample_name} contains an invalid source_entry")

    parsed_old = pd.read_csv(
        io.StringIO(reconstructed[list(authoritative.columns)].to_csv(index=False))
    )
    _assert_old_columns_exact(authoritative, parsed_old)
    return reconstructed.reset_index(drop=True)


def build_source_identity_baseline(
    authoritative_gzip: bytes,
    reconstructed: Mapping[str, pd.DataFrame],
) -> IdentityOutcome:
    """Append stable ROOT provenance while preserving every old CSV token."""
    if not isinstance(reconstructed, Mapping) or set(reconstructed) != set(
        SAMPLE_CHANNELS
    ):
        raise ValueError("reconstructed must contain exactly the sealed MC samples")
    authoritative = _parse_gzip_csv(
        authoritative_gzip, name="authoritative MC table"
    )
    if authoritative.empty:
        raise ValueError("authoritative MC table is empty")
    if any(name in authoritative.columns for name in SOURCE_IDENTITY):
        raise ValueError("authoritative MC table already contains source identity")
    if "channelNumber" not in authoritative:
        raise ValueError("authoritative MC table is missing channelNumber")
    if authoritative["channelNumber"].isna().any() or not pd.api.types.is_integer_dtype(
        authoritative["channelNumber"].dtype
    ):
        raise ValueError("authoritative MC table has invalid channelNumber")
    unknown_channels = set(authoritative["channelNumber"].unique()) - set(
        SAMPLE_CHANNELS.values()
    )
    if unknown_channels:
        raise ValueError("authoritative MC table contains an unsealed channelNumber")

    identities: list[tuple[str, int] | None] = [None] * len(authoritative)
    reconstructed_rows = 0
    for sample_name, channel in SAMPLE_CHANNELS.items():
        positions = [
            int(index)
            for index, matches in enumerate(
                authoritative["channelNumber"].eq(channel).tolist()
            )
            if matches
        ]
        expected = authoritative.iloc[positions].reset_index(drop=True)
        sample = _validated_sample(sample_name, reconstructed[sample_name], expected)
        reconstructed_rows += len(sample)
        for position, entry in zip(
            positions, sample["source_entry"].tolist(), strict=True
        ):
            identities[position] = (sample_name, int(entry))

    if reconstructed_rows != len(authoritative) or any(
        identity is None for identity in identities
    ):
        raise ValueError("source identity row count mismatch")
    concrete_identities = [identity for identity in identities if identity is not None]
    if len(set(concrete_identities)) != len(concrete_identities):
        raise ValueError("reconstructed table contains duplicate source identity")

    table_payload = _append_identity_tokens(
        authoritative_gzip, authoritative, concrete_identities
    )
    final = _parse_gzip_csv(table_payload, name="final source-identity table")
    expected_columns = list(authoritative.columns) + list(SOURCE_IDENTITY)
    if final.columns.tolist() != expected_columns:
        raise ValueError("final source-identity column contract mismatch")
    _assert_old_columns_exact(authoritative, final[list(authoritative.columns)])
    if final[list(SOURCE_IDENTITY)].values.tolist() != [
        [sample, entry] for sample, entry in concrete_identities
    ]:
        raise ValueError("final source identity disagrees with reconstructed values")

    if all(name in authoritative for name in LEGACY_EVENT_KEY):
        duplicate_mask = authoritative.duplicated(
            list(LEGACY_EVENT_KEY), keep=False
        )
        duplicate_rows = int(duplicate_mask.sum())
        duplicate_groups = int(
            authoritative.loc[duplicate_mask, list(LEGACY_EVENT_KEY)]
            .drop_duplicates()
            .shape[0]
        )
    else:
        duplicate_rows = 0
        duplicate_groups = 0
    evidence = _deep_freeze(
        {
            "schema_version": "1.0",
            "status": "validated",
            "join_key": list(SOURCE_IDENTITY),
            "authoritative_rows": len(authoritative),
            "reconstructed_rows": reconstructed_rows,
            "matched_rows": len(final),
            "authoritative_order_preserved": True,
            "complete_one_to_one_coverage": True,
            "old_columns": list(authoritative.columns),
            "old_columns_exact": True,
            "appended_columns": list(SOURCE_IDENTITY),
            "legacy_duplicate_groups": duplicate_groups,
            "legacy_duplicate_rows": duplicate_rows,
        }
    )
    return IdentityOutcome(_OUTCOME_TOKEN, table_payload, evidence)
