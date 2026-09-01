from __future__ import annotations

import gzip
import io

import pandas as pd
import pytest

from src.angular5_identity import IdentityOutcome, build_source_identity_baseline


OLD_HEADER = (
    b"runNumber,eventNumber,channelNumber,value,label,physical_weight,split\r\n"
)
OLD_ROWS = (
    b"284500,102001,345060,0.10000000000000001,1,1.2345678901234567,train\r\n",
    b"284500,1136001,345060,0.20000000000000001,1,-2.3456789012345678,train\r\n",
    b"284500,202,363490,9.8765432109876543,0,3.4567890123456789,validation\r\n",
)


def authoritative_payload() -> bytes:
    return gzip.compress(OLD_HEADER + b"".join(OLD_ROWS), mtime=0)


def reconstructed_frames() -> dict[str, pd.DataFrame]:
    authoritative = pd.read_csv(io.BytesIO(authoritative_payload()), compression="gzip")
    higgs = authoritative.loc[authoritative["channelNumber"] == 345060].copy()
    higgs["source_sample"] = "higgs_345060"
    higgs["source_entry"] = [17, 29]
    zz = authoritative.loc[authoritative["channelNumber"] == 363490].copy()
    zz["source_sample"] = "zz_363490"
    zz["source_entry"] = [4]
    return {
        "higgs_345060": higgs.reset_index(drop=True),
        "zz_363490": zz.reset_index(drop=True),
    }


def test_identity_baseline_preserves_old_tokens_and_appends_stable_identity():
    payload = authoritative_payload()

    outcome = build_source_identity_baseline(payload, reconstructed_frames())
    output = outcome.frame

    assert output.columns[-2:].tolist() == ["source_sample", "source_entry"]
    assert output[["source_sample", "source_entry"]].values.tolist() == [
        ["higgs_345060", 17],
        ["higgs_345060", 29],
        ["zz_363490", 4],
    ]
    old_lines = gzip.decompress(payload).splitlines()
    final_lines = gzip.decompress(outcome.table_payload).splitlines()
    assert final_lines[0] == old_lines[0] + b",source_sample,source_entry"
    for old, final in zip(old_lines[1:], final_lines[1:], strict=True):
        assert final.startswith(old + b",")

    reparsed = pd.read_csv(io.BytesIO(outcome.table_payload), compression="gzip")
    original = pd.read_csv(io.BytesIO(payload), compression="gzip")
    pd.testing.assert_frame_equal(
        reparsed[list(original.columns)], original, check_dtype=False, check_exact=True
    )


def test_identity_baseline_preserves_quoted_newline_inside_csv_record():
    multiline = OLD_ROWS[0].replace(b",train\r\n", b',"train\nnote"\r\n')
    payload = gzip.compress(
        OLD_HEADER + multiline + OLD_ROWS[1] + OLD_ROWS[2], mtime=0
    )
    authoritative = pd.read_csv(io.BytesIO(payload), compression="gzip")
    higgs = authoritative.loc[authoritative["channelNumber"] == 345060].copy()
    higgs["source_sample"] = "higgs_345060"
    higgs["source_entry"] = [17, 29]
    zz = authoritative.loc[authoritative["channelNumber"] == 363490].copy()
    zz["source_sample"] = "zz_363490"
    zz["source_entry"] = [4]

    outcome = build_source_identity_baseline(
        payload,
        {
            "higgs_345060": higgs.reset_index(drop=True),
            "zz_363490": zz.reset_index(drop=True),
        },
    )

    final_raw = gzip.decompress(outcome.table_payload)
    assert multiline[:-2] + b",higgs_345060,17\r\n" in final_raw
    assert outcome.frame.loc[0, "split"] == "train\nnote"


def test_identity_outcome_is_opaque_isolated_and_deeply_immutable():
    with pytest.raises(TypeError, match="returned by build_source_identity_baseline"):
        IdentityOutcome()

    outcome = build_source_identity_baseline(
        authoritative_payload(), reconstructed_frames()
    )
    first = outcome.frame
    first.loc[0, "source_entry"] = 999

    assert outcome.frame.loc[0, "source_entry"] == 17
    with pytest.raises(TypeError):
        outcome.evidence["status"] = "changed"
    with pytest.raises(AttributeError):
        outcome.evidence["old_columns"].append("changed")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("reorder", "old-column mismatch"),
        ("old_value", "old-column mismatch"),
        ("missing", "row count mismatch"),
        ("extra", "row count mismatch"),
        ("duplicate_identity", "duplicate source identity"),
        ("wrong_sample", "invalid source_sample"),
        ("noninteger_entry", "invalid source_entry"),
    ],
)
def test_identity_baseline_rejects_misalignment_and_invalid_identity(
    mutation, message
):
    reconstructed = reconstructed_frames()
    higgs = reconstructed["higgs_345060"]
    if mutation == "reorder":
        reconstructed["higgs_345060"] = higgs.iloc[::-1].reset_index(drop=True)
    elif mutation == "old_value":
        higgs.loc[0, "value"] = 123.0
    elif mutation == "missing":
        reconstructed["higgs_345060"] = higgs.iloc[:1].copy()
    elif mutation == "extra":
        reconstructed["higgs_345060"] = pd.concat(
            [higgs, higgs.iloc[[0]]], ignore_index=True
        )
        reconstructed["higgs_345060"].loc[2, "source_entry"] = 99
    elif mutation == "duplicate_identity":
        higgs["source_entry"] = [17, 17]
    elif mutation == "wrong_sample":
        higgs.loc[0, "source_sample"] = "higgs.root"
    elif mutation == "noninteger_entry":
        higgs["source_entry"] = [17.5, 29.0]

    with pytest.raises(ValueError, match=message):
        build_source_identity_baseline(authoritative_payload(), reconstructed)


@pytest.mark.parametrize(
    "reconstructed",
    [
        {"higgs_345060": reconstructed_frames()["higgs_345060"]},
        {
            **reconstructed_frames(),
            "data16_periodA": reconstructed_frames()["zz_363490"],
        },
    ],
)
def test_identity_baseline_requires_exact_mc_sample_mapping(reconstructed):
    with pytest.raises(ValueError, match="exactly the sealed MC samples"):
        build_source_identity_baseline(authoritative_payload(), reconstructed)


def test_identity_baseline_rejects_missing_or_extra_authoritative_rows():
    reconstructed = reconstructed_frames()
    extra_authoritative = gzip.compress(
        OLD_HEADER + b"".join(OLD_ROWS) + OLD_ROWS[-1], mtime=0
    )

    with pytest.raises(ValueError, match="row count mismatch"):
        build_source_identity_baseline(extra_authoritative, reconstructed)


def test_identity_baseline_reports_legacy_duplicates_without_rejecting_them():
    duplicate_rows = (
        OLD_ROWS[0],
        OLD_ROWS[0].replace(b"0.10000000000000001", b"0.30000000000000001"),
        OLD_ROWS[2],
    )
    payload = gzip.compress(OLD_HEADER + b"".join(duplicate_rows), mtime=0)
    frames = reconstructed_frames()
    parsed = pd.read_csv(io.BytesIO(payload), compression="gzip")
    higgs = parsed.loc[parsed["channelNumber"] == 345060].copy()
    higgs["source_sample"] = "higgs_345060"
    higgs["source_entry"] = [17, 29]
    zz = parsed.loc[parsed["channelNumber"] == 363490].copy()
    zz["source_sample"] = "zz_363490"
    zz["source_entry"] = [4]

    outcome = build_source_identity_baseline(
        payload,
        {
            "higgs_345060": higgs.reset_index(drop=True),
            "zz_363490": zz.reset_index(drop=True),
        },
    )

    assert outcome.evidence["legacy_duplicate_groups"] == 1
    assert outcome.evidence["legacy_duplicate_rows"] == 2
    detail = outcome.evidence["legacy_duplicate_details"][0]
    assert dict(detail["legacy_key"]) == {
        "runNumber": 284500,
        "eventNumber": 102001,
        "channelNumber": 345060,
    }
    assert [dict(identity) for identity in detail["canonical_identities"]] == [
        {"source_sample": "higgs_345060", "source_entry": 17},
        {"source_sample": "higgs_345060", "source_entry": 29},
    ]
