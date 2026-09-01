import json

import numpy as np
import pandas as pd
import pytest

from src.provenance import SampleSummaryInput, build_data_summary, write_json


def cutflow(sample_name, kind, *, read, selected):
    return {
        "sample_name": sample_name,
        "kind": kind,
        "stages": {
            "read": {"count": read},
            "selected": {"count": selected},
        },
    }


def data_input(frame=None, *, read=4, selected=3):
    if frame is None:
        frame = pd.DataFrame(
            {
                "runNumber": [10, 10, 10],
                "eventNumber": [1, 1, 2],
            }
        )
    return SampleSummaryInput(
        sample_name="data16_periodA",
        kind="data",
        frame=frame,
        cutflow=cutflow("data16_periodA", "data", read=read, selected=selected),
        period="data16_periodA",
    )


def mc_input(frame=None, *, read=5, selected=3):
    if frame is None:
        frame = pd.DataFrame(
            {
                "channelNumber": [345060, 345060, 345060],
                "physical_weight": [2.0, -0.5, 0.0],
            }
        )
    return SampleSummaryInput(
        sample_name="higgs_345060",
        kind="mc",
        frame=frame,
        cutflow=cutflow("higgs_345060", "mc", read=read, selected=selected),
        expected_dsids=(345060,),
        label=1,
    )


def test_summary_separates_data_from_mc_and_counts_unique_events():
    payload = build_data_summary([mc_input(), data_input()])

    assert payload["schema_version"] == "1.0"
    assert list(payload) == ["schema_version", "data", "mc"]
    assert list(payload["data"]) == ["data16_periodA"]
    assert list(payload["mc"]) == ["higgs_345060"]
    assert payload["data"]["data16_periodA"] == {
        "period": "data16_periodA",
        "read_events": 4,
        "selected_events": 3,
        "unique_run_event_pairs": 2,
        "duplicate_run_event_pairs": 1,
    }
    assert not ({"rows", "labels", "weight_summary"} & payload.keys())
    assert not (
        {
            "dsids",
            "label",
            "signed_sum_physical_weights",
            "absolute_sum_physical_weights",
            "negative_weight_events",
            "negative_weight_fraction",
        }
        & payload["data"]["data16_periodA"].keys()
    )


def test_mc_summary_uses_only_selected_physical_weights():
    entry = build_data_summary([mc_input()])["mc"]["higgs_345060"]

    assert entry == {
        "dsids": [345060],
        "label": 1,
        "read_events": 5,
        "selected_events": 3,
        "signed_sum_physical_weights": 1.5,
        "absolute_sum_physical_weights": 2.5,
        "negative_weight_events": 1,
        "negative_weight_fraction": pytest.approx(1 / 3),
    }


def test_empty_selected_mc_has_zero_negative_fraction():
    frame = pd.DataFrame(
        {
            "channelNumber": pd.Series(dtype="int64"),
            "physical_weight": pd.Series(dtype="float64"),
        }
    )
    entry = build_data_summary([mc_input(frame, read=2, selected=0)])["mc"][
        "higgs_345060"
    ]

    assert entry["selected_events"] == 0
    assert entry["negative_weight_fraction"] == 0.0


@pytest.mark.parametrize("column", ["runNumber", "eventNumber"])
def test_data_requires_event_identity_columns(column):
    frame = pd.DataFrame({"runNumber": [1], "eventNumber": [2]}).drop(
        columns=column
    )

    with pytest.raises(ValueError, match=column):
        build_data_summary([data_input(frame, read=1, selected=1)])


def test_mc_requires_physical_weight_and_expected_dsids():
    missing_weight = pd.DataFrame({"channelNumber": [345060]})
    no_dsids = mc_input(
        pd.DataFrame({"channelNumber": [345060], "physical_weight": [1.0]}),
        read=1,
        selected=1,
    )
    no_dsids = SampleSummaryInput(
        sample_name=no_dsids.sample_name,
        kind=no_dsids.kind,
        frame=no_dsids.frame,
        cutflow=no_dsids.cutflow,
        expected_dsids=(),
        label=no_dsids.label,
    )

    with pytest.raises(ValueError, match="physical_weight"):
        build_data_summary([mc_input(missing_weight, read=1, selected=1)])
    with pytest.raises(ValueError, match="expected_dsids"):
        build_data_summary([no_dsids])


def test_mc_requires_channel_number_and_label():
    missing_channel = pd.DataFrame({"physical_weight": [1.0]})
    sample = mc_input(
        pd.DataFrame(
            {"channelNumber": [345060], "physical_weight": [1.0]}
        ),
        read=1,
        selected=1,
    )
    missing_label = SampleSummaryInput(
        sample_name=sample.sample_name,
        kind=sample.kind,
        frame=sample.frame,
        cutflow=sample.cutflow,
        expected_dsids=sample.expected_dsids,
        label=None,
    )

    with pytest.raises(ValueError, match="channelNumber"):
        build_data_summary([mc_input(missing_channel, read=1, selected=1)])
    with pytest.raises(ValueError, match="label"):
        build_data_summary([missing_label])


@pytest.mark.parametrize("weight", [np.nan, np.inf, -np.inf])
def test_mc_rejects_nonfinite_physical_weights(weight):
    frame = pd.DataFrame(
        {"channelNumber": [345060], "physical_weight": [weight]}
    )

    with pytest.raises(ValueError, match="finite"):
        build_data_summary([mc_input(frame, read=1, selected=1)])


def test_mc_rejects_unexpected_observed_dsid():
    frame = pd.DataFrame(
        {"channelNumber": [999999], "physical_weight": [1.0]}
    )

    with pytest.raises(ValueError, match="unconfigured DSID"):
        build_data_summary([mc_input(frame, read=1, selected=1)])


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"sample_name": "wrong"}, "sample_name"),
        ({"kind": "data"}, "kind"),
    ],
)
def test_summary_rejects_cutflow_metadata_mismatch(change, message):
    sample = mc_input()
    broken = dict(sample.cutflow)
    broken.update(change)
    sample = SampleSummaryInput(
        sample_name=sample.sample_name,
        kind=sample.kind,
        frame=sample.frame,
        cutflow=broken,
        expected_dsids=sample.expected_dsids,
        label=sample.label,
    )

    with pytest.raises(ValueError, match=message):
        build_data_summary([sample])


@pytest.mark.parametrize("stage", ["read", "selected"])
def test_summary_requires_named_cutflow_stages(stage):
    sample = data_input()
    broken = dict(sample.cutflow)
    broken["stages"] = dict(broken["stages"])
    del broken["stages"][stage]
    sample = SampleSummaryInput(
        sample_name=sample.sample_name,
        kind=sample.kind,
        frame=sample.frame,
        cutflow=broken,
        period=sample.period,
    )

    with pytest.raises(ValueError, match=stage):
        build_data_summary([sample])


def test_summary_rejects_selected_count_mismatch_and_invalid_counts():
    with pytest.raises(ValueError, match="selected.*frame"):
        build_data_summary([data_input(read=4, selected=2)])
    with pytest.raises(ValueError, match="read_events"):
        build_data_summary([data_input(read=2, selected=3)])


@pytest.mark.parametrize("count", [-1, True, 1.5])
def test_summary_rejects_non_integer_or_negative_cutflow_counts(count):
    with pytest.raises(ValueError, match="non-negative integer"):
        build_data_summary([data_input(read=count, selected=3)])


def test_summary_rejects_duplicate_names_and_unknown_kind():
    with pytest.raises(ValueError, match="duplicate sample_name"):
        build_data_summary([data_input(), data_input()])

    sample = data_input()
    unknown = SampleSummaryInput(
        sample_name=sample.sample_name,
        kind="unknown",  # type: ignore[arg-type]
        frame=sample.frame,
        cutflow=sample.cutflow,
        period=sample.period,
    )
    with pytest.raises(ValueError, match="kind"):
        build_data_summary([unknown])


def test_write_json_is_stable_and_creates_parent_directories(tmp_path):
    payload = build_data_summary([mc_input(), data_input()])
    first = tmp_path / "one" / "summary.json"
    second = tmp_path / "two" / "summary.json"

    write_json(payload, first)
    write_json(payload, second)

    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes().endswith(b"\n")
    assert json.loads(first.read_text(encoding="utf-8")) == payload
