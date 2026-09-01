import json
import math

import pytest

from src.pipeline import prepare_sample, write_cutflow
from src.selection import CutflowAccumulator, SelectionConfig, SelectionResult
from src.weights import MCNormalization


def result_through(*stages):
    accepted = bool(stages and stages[-1] == "selected")
    return SelectionResult(
        accepted=accepted,
        passed_stages=tuple(stages),
        failed_stage=None if accepted else "lepton_pt",
        candidate=None,
    )


def test_mc_cutflow_accumulates_signed_and_absolute_yields():
    cutflow = CutflowAccumulator(sample_name="higgs_345060", is_data=False)
    first = result_through("exactly_four_leptons", "allowed_lepton_types")
    second = result_through("exactly_four_leptons")

    cutflow.record_read(2.0)
    cutflow.record_selection(first, 2.0)
    cutflow.record_read(-0.5)
    cutflow.record_selection(second, -0.5)
    output = cutflow.to_dict()

    assert output["kind"] == "mc"
    assert output["stages"]["read"] == {
        "count": 2,
        "efficiency_previous": 1.0,
        "efficiency_read": 1.0,
        "signed_weighted_yield": 1.5,
        "absolute_weighted_yield": 2.5,
    }
    assert output["stages"]["exactly_four_leptons"]["count"] == 2
    assert output["stages"]["allowed_lepton_types"]["count"] == 1
    assert output["stages"]["allowed_lepton_types"]["signed_weighted_yield"] == 2.0


def test_data_cutflow_omits_weighted_yields():
    cutflow = CutflowAccumulator(sample_name="data16_periodA", is_data=True)
    result = result_through("exactly_four_leptons")

    cutflow.record_read()
    cutflow.record_selection(result)
    output = cutflow.to_dict()

    assert output["kind"] == "data"
    assert "signed_weighted_yield" not in output["stages"]["read"]
    assert "absolute_weighted_yield" not in output["stages"]["read"]


def test_cutflow_efficiencies_and_zero_denominators():
    empty = CutflowAccumulator(sample_name="empty", is_data=True).to_dict()
    assert empty["stages"]["read"]["efficiency_read"] == 0.0
    assert empty["stages"]["exactly_four_leptons"]["efficiency_previous"] == 0.0

    cutflow = CutflowAccumulator(sample_name="data", is_data=True)
    cutflow.record_read()
    cutflow.record_read()
    cutflow.record_selection(result_through("exactly_four_leptons"))
    output = cutflow.to_dict()
    assert output["stages"]["exactly_four_leptons"]["efficiency_previous"] == 0.5
    assert output["stages"]["exactly_four_leptons"]["efficiency_read"] == 0.5


def test_cutflow_rejects_skipped_or_reordered_stages():
    cutflow = CutflowAccumulator(sample_name="bad", is_data=True)
    cutflow.record_read()
    bad = result_through("exactly_four_leptons", "lepton_pt")

    with pytest.raises(ValueError, match="ordered prefix"):
        cutflow.record_selection(bad)


def test_cutflow_requires_weights_only_for_mc():
    mc = CutflowAccumulator(sample_name="mc", is_data=False)
    data = CutflowAccumulator(sample_name="data", is_data=True)

    with pytest.raises(ValueError, match="MC physical weight"):
        mc.record_read()
    with pytest.raises(ValueError, match="data physical weight"):
        data.record_read(1.0)


def selection_config():
    return SelectionConfig.from_mapping(
        {
            "require_exactly_four_leptons": True,
            "allowed_lepton_types": [11, 13],
            "lepton_pt_thresholds_gev": [20.0, 15.0, 10.0, 7.0],
            "electron_max_abs_eta": 2.47,
            "muon_max_abs_eta": 2.7,
            "require_zero_charge": True,
            "min_all_sfos_mass_gev": 5.0,
            "z1_mass_window_gev": [50.0, 106.0],
            "z2_mass": {
                "min_mode": "fixed",
                "fixed_min_gev": 12.0,
                "max_gev": 115.0,
                "sliding": {
                    "low_m4l_gev": 140.0,
                    "high_m4l_gev": 190.0,
                    "low_min_gev": 12.0,
                    "high_min_gev": 50.0,
                },
            },
            "m4l_window_gev": [105.0, 160.0],
        }
    )


def raw_event(*, event_number, passing=True, is_data=False, mc_weight=1.0):
    pt = [45.0, 45.0, 15.0, 15.0] if passing else [19.0, 15.0, 10.0, 7.0]
    event = {
        "lep_n": 4,
        "lep_pt": pt,
        "lep_eta": [0.0, 0.0, 0.0, 0.0],
        "lep_phi": [0.0, math.pi, math.pi / 2, -math.pi / 2],
        "lep_e": [45.0, 45.0, 15.0, 15.0],
        "lep_charge": [1, -1, 1, -1],
        "lep_type": [11, 11, 13, 13],
        "eventNumber": event_number,
        "runNumber": 1,
        "channelNumber": 0 if is_data else 42,
    }
    if not is_data:
        event.update(
            mcWeight=mc_weight,
            xsec=2.0,
            kfac=1.0,
            filteff=1.0,
            sum_of_weights=100.0,
        )
    return event


def test_prepare_sample_applies_selection_and_returns_mc_cutflow(monkeypatch):
    events = [
        raw_event(event_number=1, passing=True),
        raw_event(event_number=2, passing=False, mc_weight=-0.5),
    ]
    monkeypatch.setattr("src.pipeline.iter_events", lambda *args, **kwargs: iter(events))

    prepared = prepare_sample(
        "unused.root",
        sample_name="higgs_42",
        selection=selection_config(),
        tree_name="analysis",
        momentum_unit="GeV",
        is_data=False,
        label=1,
        expected_channels=[42],
        luminosity_pb=1000.0,
    )

    assert len(prepared.frame) == 1
    assert prepared.cutflow["stages"]["read"]["count"] == 2
    assert prepared.cutflow["stages"]["lepton_pt"]["count"] == 1
    assert prepared.cutflow["stages"]["selected"]["count"] == len(prepared.frame)
    assert prepared.cutflow["stages"]["read"]["signed_weighted_yield"] == 10.0
    assert set(prepared.frame["split"]) <= {"train", "validation", "test"}
    assert (prepared.frame["label"] == 1).all()


def test_prepare_sample_returns_one_validated_mc_normalization(monkeypatch):
    events = [
        raw_event(event_number=1, passing=True),
        raw_event(event_number=2, passing=False, mc_weight=-0.5),
    ]
    calls = []

    def fake_iter_events(*args, **kwargs):
        calls.append(kwargs)
        return iter(events)

    monkeypatch.setattr("src.pipeline.iter_events", fake_iter_events)

    prepared = prepare_sample(
        "unused.root",
        sample_name="higgs_42",
        selection=selection_config(),
        tree_name="analysis",
        momentum_unit="GeV",
        is_data=False,
        label=1,
        expected_channels=[42],
        luminosity_pb=1000.0,
        chunk_size_events=17,
    )

    assert prepared.normalization == MCNormalization(2.0, 1.0, 1.0, 100.0)
    assert calls[0]["chunk_size_events"] == 17
    assert prepared.cutflow["stages"]["read"]["signed_weighted_yield"] == 10.0


def test_prepare_sample_rejects_normalization_change_in_rejected_event(monkeypatch):
    events = [
        raw_event(event_number=1, passing=True),
        raw_event(event_number=2, passing=False),
    ]
    events[1]["sum_of_weights"] = 101.0
    monkeypatch.setattr("src.pipeline.iter_events", lambda *args, **kwargs: iter(events))

    with pytest.raises(ValueError, match="sum_of_weights changed"):
        prepare_sample(
            "unused.root",
            sample_name="higgs_42",
            selection=selection_config(),
            tree_name="analysis",
            momentum_unit="GeV",
            is_data=False,
            label=1,
            expected_channels=[42],
        )


def test_prepare_sample_checks_channel_number_before_selection(monkeypatch):
    event = raw_event(event_number=1, passing=False)
    event["channelNumber"] = 999
    monkeypatch.setattr("src.pipeline.iter_events", lambda *args, **kwargs: iter([event]))

    with pytest.raises(ValueError, match="999"):
        prepare_sample(
            "unused.root",
            sample_name="higgs_42",
            selection=selection_config(),
            tree_name="analysis",
            momentum_unit="GeV",
            is_data=False,
            label=1,
            expected_channels=[42],
        )


def test_prepare_sample_data_has_no_mc_normalization(monkeypatch):
    event = raw_event(event_number=1, passing=True, is_data=True)
    monkeypatch.setattr("src.pipeline.iter_events", lambda *args, **kwargs: iter([event]))

    prepared = prepare_sample(
        "unused.root",
        sample_name="data16_periodA",
        selection=selection_config(),
        tree_name="analysis",
        momentum_unit="GeV",
        is_data=True,
    )

    assert prepared.normalization is None


def test_prepare_sample_rejects_mc_with_zero_read_events(monkeypatch):
    monkeypatch.setattr("src.pipeline.iter_events", lambda *args, **kwargs: iter(()))

    with pytest.raises(ValueError, match="no MC events were read"):
        prepare_sample(
            "unused.root",
            sample_name="higgs_42",
            selection=selection_config(),
            tree_name="analysis",
            momentum_unit="GeV",
            is_data=False,
            label=1,
            expected_channels=[42],
        )


def test_prepare_sample_keeps_data_unweighted_in_cutflow(monkeypatch):
    events = [
        raw_event(event_number=1, passing=True, is_data=True),
        raw_event(event_number=2, passing=False, is_data=True),
    ]
    monkeypatch.setattr("src.pipeline.iter_events", lambda *args, **kwargs: iter(events))

    prepared = prepare_sample(
        "unused.root",
        sample_name="data16_periodA",
        selection=selection_config(),
        tree_name="analysis",
        momentum_unit="GeV",
        is_data=True,
    )

    assert len(prepared.frame) == 1
    assert (prepared.frame["label"] == -1).all()
    assert (prepared.frame["split"] == "data").all()
    assert "signed_weighted_yield" not in prepared.cutflow["stages"]["read"]


def test_write_cutflow_is_deterministic(tmp_path):
    samples = {
        "zz_42": CutflowAccumulator(sample_name="zz_42", is_data=False),
        "data16_periodA": CutflowAccumulator(
            sample_name="data16_periodA", is_data=True
        ),
    }
    samples["zz_42"].record_read(2.0)
    samples["data16_periodA"].record_read()
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    write_cutflow(samples, z2_min_mode="fixed", path=first)
    write_cutflow(samples, z2_min_mode="fixed", path=second)

    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes().endswith(b"\n")
    payload = json.loads(first.read_text())
    assert payload["schema_version"] == "1.0"
    assert list(payload["samples"]) == ["data16_periodA", "zz_42"]
    assert "signed_weighted_yield" not in payload["samples"]["data16_periodA"]["stages"]["read"]
