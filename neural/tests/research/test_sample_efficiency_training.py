import copy
import hashlib
import json

import pytest
import torch

from src.research.artifacts import ResearchRun, read_run
from src.research.discriminants import digest, predict_discriminant
from src.research.protocol import canonical
from src.research.errors import ResearchError, ResearchStateError
from src.research.sample_efficiency_training import (
    _ids,
    predict_subset_discriminant,
    publish_subset_discriminant,
    read_subset_discriminant_run,
)
from src.research.training_subsets import load_training_subset

from sample_efficiency_support import build_sample_efficiency_fixture


@pytest.fixture(autouse=True)
def single_thread():
    old = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


def test_selection_partial_and_full_are_canonical_and_low_statistics_stops(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path)
    partial = load_training_subset(subsets, prepared=prepared, freeze_run=freeze, base=base,
                                   overlay=overlay, fraction=0.5, draw=100)
    full = load_training_subset(subsets, prepared=prepared, freeze_run=freeze, base=base,
                                overlay=overlay, fraction=1.0, draw=101)
    assert partial["sample_draw_seed"] == partial["sample_draw_seed_or_full"] == 100
    assert full["sample_draw_seed"] is None and full["sample_draw_seed_or_full"] == "full"
    assert full["sample_fraction_target"] == 1.0
    assert partial["compact_candidate"]["representation_id"] == "compact:AB"

    low_root = tmp_path / "low-fixture"
    low_root.mkdir()
    low = build_sample_efficiency_fixture(low_root, fractions=(0.01, 1.0), minimum_groups=2)
    with pytest.raises(ResearchStateError) as error:
        load_training_subset(low[4], prepared=low[1], freeze_run=low[2], base=low[0],
                             overlay=low[3], fraction=0.01, draw=100)
    assert error.value.status == "training_subset_insufficient_statistics"


def test_v2_publisher_reader_filters_train_and_binds_three_upstreams(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path)
    loaded = publish_subset_discriminant(tmp_path / "model", allowed_root=tmp_path,
        prepared=prepared, freeze_run=freeze, subset_run=subsets, base=base, overlay=overlay,
        fraction=0.5, draw=100, representation_id="decay7", network_seed=42)
    model = loaded.model
    selection = load_training_subset(subsets, prepared=prepared, freeze_run=freeze, base=base,
                                     overlay=overlay, fraction=0.5, draw=100)
    assert model["schema_version"] == "research-discriminant-v2"
    assert model["scaler"]["fitting_rows"] == selection["summary_total"]["row_count"]
    assert model["training_summary_total"] == selection["summary_total"]
    assert model["network_seed"] == model["seed"] == 42
    assert {item["stage"] for item in loaded.run.manifest["upstreams"]} == {
        "prepare", "compact-freeze", "training-subsets"}
    reread = read_subset_discriminant_run(loaded.run, prepared=prepared, freeze_run=freeze,
        subset_run=subsets, base=base, overlay=overlay, fraction=0.5, draw=100,
        representation_id="decay7", network_seed=42)
    assert reread.model == model and reread.lineage["model_id"] == model["model_id"]


def test_three_representations_share_pairing_but_not_experiment_identity(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path)
    models = []
    for representation in overlay["representations"]:
        loaded = publish_subset_discriminant(tmp_path / ("model-" + representation.replace(":", "-")),
            allowed_root=tmp_path, prepared=prepared, freeze_run=freeze, subset_run=subsets,
            base=base, overlay=overlay, fraction=0.5, draw=100,
            representation_id=representation, network_seed=42)
        models.append(loaded.model)
    assert len({model["pairing_id"] for model in models}) == 1
    assert len({model["experiment_cell_id"] for model in models}) == 3
    assert [model["candidate"] for model in models] == ["M2", "M3", "M3"]
    assert models[1]["groups"] == ["A", "B"]


def test_reader_rejects_semantically_tampered_resigned_v2_model(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path)
    good = publish_subset_discriminant(tmp_path / "good", allowed_root=tmp_path,
        prepared=prepared, freeze_run=freeze, subset_run=subsets, base=base, overlay=overlay,
        fraction=0.5, draw=100, representation_id="decay7", network_seed=42)
    bad_model = copy.deepcopy(good.model)
    bad_model["trainable_parameter_count"] += 1
    bad_model["model_id"] = digest({key: value for key, value in bad_model.items() if key != "model_id"})
    root = tmp_path / "resigned"
    with ResearchRun(root, allowed_root=tmp_path, stage="sample-efficiency-train", dataset=base["dataset"],
                     protocol=base.to_dict(), upstreams=[prepared, freeze, subsets]) as run:
        run.write_json("sample-efficiency-protocol.json", overlay.to_dict())
        run.write_json("model.json", bad_model)
    bad = read_run(root, dataset=base["dataset"], protocol=base.to_dict(),
                   stages=("sample-efficiency-train",))
    with pytest.raises(ResearchError) as error:
        read_subset_discriminant_run(bad, prepared=prepared, freeze_run=freeze, subset_run=subsets,
            base=base, overlay=overlay, fraction=0.5, draw=100,
            representation_id="decay7", network_seed=42)
    assert error.value.status == "training_subset_binding_mismatch"


def test_prepared_feature_tamper_is_rejected_before_v2_training(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path)
    path = prepared.path / "events.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    identity, payload = lines[1].split("\t", 1)
    value = json.loads(payload)
    value["lep1_pt"] += 999.0
    lines[1] = identity + "\t" + json.dumps(value, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    with pytest.raises(ResearchError):
        publish_subset_discriminant(tmp_path / "tampered", allowed_root=tmp_path,
            prepared=prepared, freeze_run=freeze, subset_run=subsets, base=base, overlay=overlay,
            fraction=0.5, draw=100, representation_id="decay7", network_seed=42)


def test_predict_v2_rejects_resigned_semantic_change(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path)
    loaded = publish_subset_discriminant(tmp_path / "model", allowed_root=tmp_path,
        prepared=prepared, freeze_run=freeze, subset_run=subsets, base=base, overlay=overlay,
        fraction=0.5, draw=100, representation_id="decay7", network_seed=42)
    model = copy.deepcopy(loaded.model)
    model["sample_draw_seed_or_full"] = 101
    model["model_id"] = digest({key: value for key, value in model.items() if key != "model_id"})
    frame = __import__("src.research.data", fromlist=["load_research_data"]).load_research_data(
        prepared.file("events.jsonl"), base["dataset"], base)
    with pytest.raises(ResearchError) as error:
        predict_discriminant(model, frame.loc[frame.role == "validation"].copy())
    assert error.value.status == "training_subset_binding_mismatch"
    scores = predict_subset_discriminant(loaded, frame.loc[frame.role == "validation"].copy())
    assert len(scores) == len(frame.loc[frame.role == "validation"])


def test_reader_rejects_resigned_out_of_overlay_seed_and_missing_history(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path)
    good = publish_subset_discriminant(tmp_path / "good", allowed_root=tmp_path,
        prepared=prepared, freeze_run=freeze, subset_run=subsets, base=base, overlay=overlay,
        fraction=0.5, draw=100, representation_id="decay7", network_seed=42)
    for name, mutate, requested_seed in (
        ("seed", lambda model: model.update(seed=-1, network_seed=-1), -1),
        ("history", lambda model: model.pop("history_contract"), 42),
        ("nested", lambda model: model.update(scaler=[]), 42),
    ):
        model = copy.deepcopy(good.model)
        mutate(model)
        model["experiment_cell_id"], model["pairing_id"] = _ids(model)
        model["model_id"] = digest({key: value for key, value in model.items() if key != "model_id"})
        root = tmp_path / ("resigned-" + name)
        with ResearchRun(root, allowed_root=tmp_path, stage="sample-efficiency-train",
                         dataset=base["dataset"], protocol=base.to_dict(),
                         upstreams=[prepared, freeze, subsets]) as run:
            run.write_json("sample-efficiency-protocol.json", overlay.to_dict())
            run.write_json("model.json", model)
        with pytest.raises(ResearchError) as error:
            read_subset_discriminant_run(root, prepared=prepared, freeze_run=freeze,
                subset_run=subsets, base=base, overlay=overlay, fraction=0.5, draw=100,
                representation_id="decay7", network_seed=requested_seed)
        assert error.value.status == "training_subset_binding_mismatch"


def test_reader_rejects_resigned_duplicate_or_redirected_upstream(tmp_path):
    base, prepared, freeze, overlay, subsets = build_sample_efficiency_fixture(tmp_path)
    loaded = publish_subset_discriminant(tmp_path / "model", allowed_root=tmp_path,
        prepared=prepared, freeze_run=freeze, subset_run=subsets, base=base, overlay=overlay,
        fraction=0.5, draw=100, representation_id="decay7", network_seed=42)
    manifest_path = loaded.run.path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["upstreams"].append(copy.deepcopy(manifest["upstreams"][0]))
    identity = {key: value for key, value in manifest.items() if key != "artifact_id"}
    manifest["artifact_id"] = hashlib.sha256(canonical(identity)).hexdigest()
    manifest_path.write_bytes(canonical(manifest))
    with pytest.raises(ResearchError) as error:
        read_subset_discriminant_run(loaded.run.path, prepared=prepared, freeze_run=freeze,
            subset_run=subsets, base=base, overlay=overlay, fraction=0.5, draw=100,
            representation_id="decay7", network_seed=42)
    assert error.value.status == "training_subset_binding_mismatch"
