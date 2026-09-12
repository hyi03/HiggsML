"""Pin the pre-subset runtime contracts; no experiment data is opened."""
import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from src.research.discriminants import ResearchClassifier, train_discriminant
from src.research.errors import ResearchError
from src.research.protocol import load_protocol, validate_protocol
from src.research.representations import representation_features
from src.research.workflow import _candidate_key


@pytest.mark.parametrize("filename,expected", [
    ("research_protocol_v1.json", "bddc5ba0efbdc0262dc71a5c4ecb6d3592323b5226453af3208189177c8b1f39"),
    ("research_protocol_v2.json", "54e98f7b8fbaeecbfd3b65f14d3145ee87e2a2fe031fcfb834536093ab574414"),
    ("research_protocol_exploratory_all_mc_v1.json", "1f6fddedd796d6a547672fb4651307bf92b4af52b90145e6ae08aaa42a224636"),
])
def test_existing_protocol_digests_and_unknown_fields(filename, expected):
    protocol = load_protocol(Path(__file__).resolve().parents[2] / "config" / filename)
    assert protocol.digest == expected
    broken = protocol.to_dict()
    broken["sample_fractions"] = [0.25, 0.5, 1.0]
    with pytest.raises(ResearchError):
        validate_protocol(broken, broken["dataset"])


@pytest.mark.parametrize("model,key", [
    ({"candidate": "M0c", "seed": 42}, "M0c:42"),
    ({"candidate": "M2", "seed": 43}, "M2:43"),
    ({"candidate": "M3", "seed": 44, "groups": None}, "M3:44"),
    ({"candidate": "M3", "seed": 45, "groups": ["A", "B"]}, "M3:45:groups=AB"),
    ({"candidate": "M6", "seed": 46, "target_lambda": 0.1}, "M6:46:lambda=0.1"),
])
def test_legacy_candidate_keys_have_no_inferred_subset(model, key):
    assert _candidate_key(model) == key
    with_extra_context = dict(model, sample_fraction=0.25, sample_draw_seed=100)
    assert _candidate_key(with_extra_context) == key  # new cells require their own M3 key service


@pytest.mark.parametrize("representation,groups,dimension,expected", [
    ("decay7", None, 8, 7169), ("engineered19", ["A", "B"], 13, 7489),
    ("engineered19", None, 20, 7937),
])
def test_current_network_parameter_counts(representation, groups, dimension, expected):
    assert len(representation_features(representation, groups=groups)) == dimension
    assert sum(p.numel() for p in ResearchClassifier(dimension).parameters() if p.requires_grad) == expected
    assert expected == 64 * dimension + 6657


def test_current_train_statistics_are_local_and_validation_is_complete(monkeypatch):
    count = 48
    data = pd.DataFrame({
        "m4l": np.tile(np.linspace(105.1, 139.9, count), 2),
        "role": ["train"] * count + ["validation"] * count,
        "label": np.tile(np.arange(count) % 2, 2),
        "physical_weight": np.tile(np.array([1., -2., 3., -4.]), count // 2),
        "dataset": "atlas2020_4lep",
        "event_group_id": [f"synthetic-{i}" for i in range(2 * count)],
    })
    # Large validation weights/masses must not leak into fitting statistics.
    data.loc[data.role == "validation", "physical_weight"] *= 100
    data.loc[data.role == "validation", "m4l"] += 100
    import src.research.discriminants as discriminants
    original_auc = discriminants.roc_auc_score
    evaluation_lengths = []

    def observed_auc(y, prediction, **kwargs):
        evaluation_lengths.append(len(y))
        return original_auc(y, prediction, **kwargs)

    monkeypatch.setattr(discriminants, "roc_auc_score", observed_auc)
    before = copy.deepcopy(data)
    threads = torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        model = train_discriminant(data, load_protocol(), candidate="M0c")
    finally:
        torch.set_num_threads(threads)
    train = data[data.role == "train"]
    assert model["schema_version"] == "research-discriminant-v1"
    assert model["scaler"]["fitting_rows"] == count
    assert model["scaler"]["mean"] == pytest.approx([train.m4l.mean()])
    assert model["optimizer_class_absolute_weight_means"] == pytest.approx([
        train.loc[train.label == label, "physical_weight"].abs().mean() for label in (0, 1)])
    assert max(model["mass_bin_boundaries"]) < 140
    assert model["ordered_inputs"] == ["m4l"]
    assert set(evaluation_lengths) == {count}
    assert len(evaluation_lengths) == len(model["history"]) + 1
    assert "training_subset_id" not in model
    pd.testing.assert_frame_equal(data, before)
