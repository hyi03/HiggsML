from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from src import pipeline as legacy_pipeline
from src.config import load_preprocessing_protocol
from src.domain.angular5 import ANGULAR5_FEATURES, build_angular5
from src.domain.selection import SelectionConfig, select_event
from src.domain.weights import MCNormalization
from src.preprocessing import pipeline as migrated_pipeline


PROJECT = Path(__file__).resolve().parents[2]
RTOL = 1e-12
ATOL = 1e-12


def _event() -> dict[str, object]:
    return {
        "lep_n": 4,
        "lep_pt": [45.0, 45.0, 15.0, 15.0],
        "lep_eta": [0.0, 0.0, 0.0, 0.0],
        "lep_phi": [0.0, math.pi, math.pi / 2, -math.pi / 2],
        "lep_e": [45.0, 45.0, 15.0, 15.0],
        "lep_charge": [1, -1, 1, -1],
        "lep_type": [11, 11, 13, 13],
        "trigE": True,
        "trigM": False,
        "lep_isTrigMatched": [True] * 4,
        "lep_isTightID": [True] * 4,
        "lep_track_iso": [0.1] * 4,
        "lep_calo_iso": [0.1] * 4,
        "lep_d0sig": [0.1] * 4,
        "lep_z0": [0.1] * 4,
        "eventNumber": 60,
        "runNumber": 1,
        "channelNumber": 345060,
        "mcWeight": -2.0,
        "xsec": 0.5,
        "kfac": 1.0,
        "filteff": 1.0,
        "sum_of_weights": 100.0,
    }


def _zz_event() -> dict[str, object]:
    event = _event()
    event["lep_pt"] = [value * 1000.0 for value in event["lep_pt"]]
    event["lep_e"] = [value * 1000.0 for value in event["lep_e"]]
    event["channelNumber"] = 363490
    for name in ("xsec", "kfac", "filteff", "sum_of_weights"):
        event.pop(name)
    return event


def test_migrated_preprocess_matches_frozen_domain_weight_split_and_cutflow(
    monkeypatch,
) -> None:
    protocol = load_preprocessing_protocol(PROJECT / "config/preprocessing_protocol_v1.yaml")
    selection = SelectionConfig.from_mapping(protocol.raw["selection"])
    event = _event()
    monkeypatch.setattr(
        legacy_pipeline, "iter_events", lambda *args, **kwargs: iter([event.copy()])
    )
    monkeypatch.setattr(
        migrated_pipeline,
        "iter_mc_events",
        lambda *args, **kwargs: iter([event.copy()]),
    )

    legacy = legacy_pipeline.prepare_sample(
        "unused.root",
        sample_name="higgs_345060",
        selection=selection,
        tree_name="analysis",
        momentum_unit="GeV",
        is_data=False,
        label=1,
        expected_channels=(345060,),
        input_profile="release22",
    )
    migrated = migrated_pipeline.prepare_mc_sample(
        "unused.root",
        name="higgs",
        sample=protocol.raw["samples"]["higgs"],
        selection=selection,
        chunk_size_events=3,
    )

    common = [
        *legacy_pipeline.FEATURES,
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
    ]
    pd.testing.assert_frame_equal(
        migrated.frame[common],
        legacy.frame[common],
        check_exact=True,
        check_dtype=False,
    )
    result = select_event(event, selection, "GeV")
    assert result.candidate is not None
    expected_angles = build_angular5(result.candidate)
    np.testing.assert_allclose(
        migrated.frame.loc[0, list(ANGULAR5_FEATURES)].to_numpy(dtype=float),
        [expected_angles[name] for name in ANGULAR5_FEATURES],
        rtol=RTOL,
        atol=ATOL,
    )
    assert migrated.cutflow == legacy.cutflow


def test_migrated_zz_official_metadata_matches_legacy_normalization_override(
    monkeypatch,
) -> None:
    protocol = load_preprocessing_protocol(PROJECT / "config/preprocessing_protocol_v1.yaml")
    selection = SelectionConfig.from_mapping(protocol.raw["selection"])
    sample = protocol.raw["samples"]["zz"]
    event = _zz_event()
    raw_normalization = sample["normalization"]
    normalization = MCNormalization(
        raw_normalization["xsec_pb"],
        raw_normalization["k_factor"],
        raw_normalization["filter_efficiency"],
        raw_normalization["sum_of_weights"],
    )
    monkeypatch.setattr(
        legacy_pipeline, "iter_events", lambda *args, **kwargs: iter([event.copy()])
    )
    monkeypatch.setattr(
        migrated_pipeline,
        "iter_mc_events",
        lambda *args, **kwargs: iter([event.copy()]),
    )

    legacy = legacy_pipeline.prepare_sample(
        "unused.root",
        sample_name="zz_363490",
        selection=selection,
        tree_name="mini",
        momentum_unit="MeV",
        is_data=False,
        label=0,
        expected_channels=(363490,),
        input_profile="open_data_2020",
        normalization_override=normalization,
    )
    migrated = migrated_pipeline.prepare_mc_sample(
        "unused.root",
        name="zz",
        sample=sample,
        selection=selection,
        chunk_size_events=3,
    )

    common = [
        *legacy_pipeline.FEATURES,
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
    ]
    pd.testing.assert_frame_equal(
        migrated.frame[common],
        legacy.frame[common],
        check_exact=True,
        check_dtype=False,
    )
    assert migrated.cutflow == legacy.cutflow
