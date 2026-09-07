from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from src.config import InputBindingError, TestOpeningRefused as OpeningRefused, load_preprocess_protocol, PreprocessRunConfig
from src.training import development as app
from src.training.config import load_training_protocol
from src.training.development_reader import read_development_input
from src.training.test_opening import _load_binding, _evaluate, execute_test_opening
from src.training.trainer import train_fold, train_fixed_epochs
from tests.development_fixtures import write_synthetic_preprocess_run
from tests.integration.test_development_run import _candidate

PROJECT = Path(__file__).resolve().parents[2]
PROTOCOL = PROJECT / "config/adversarial_mlp_protocol_inclusive.yaml"


def preprocess_synthetic_roots(tmp_path, monkeypatch, dataset):
    """Exercise the real ROOT-to-partition pipeline with synthetic bound bytes."""
    import awkward as ak
    import uproot
    from src.artifacts.manifest import sha256_file
    from src.preprocessing import pipeline
    from tests.integration.test_preprocess_micro_root import _write_inputs, _canonical_events
    # Reuse only synthetic event identities; never open any repository run/data.
    _, identities = write_synthetic_preprocess_run(tmp_path / "identity-fixture", dataset=dataset)
    higgs, zz = _write_inputs(tmp_path, dataset)
    protocol = load_preprocess_protocol(PROJECT / "config/preprocess_protocol_inclusive.yaml", dataset=dataset)
    samples = {}
    for role, path in (("higgs", higgs), ("zz", zz)):
        sample = protocol.samples[role]
        rows = identities.loc[identities.label == sample.label]
        count = len(rows)
        original = _canonical_events(sample.dsid, mev=sample.momentum_unit == "MeV")
        events = {}
        for name, values in original.items():
            if isinstance(values, ak.Array):
                events[name] = ak.Array([ak.to_list(values[0])] * count)
            else:
                events[name] = [values[0]] * count
        # Boost the two SFOS pairs in opposite directions: broad m4l while
        # preserving each pair's mass and all other physical selection rules.
        rapidities = np.linspace(.01, 2., count)
        eta = [[float(y), float(y), float(-y), float(-y)] for y in rapidities]
        events["lep_eta"] = ak.Array(eta)
        scale = 1000. if sample.momentum_unit == "MeV" else 1.
        events["lep_e"] = ak.Array([[float(pt * np.cosh(y) * scale) for pt in (40., 35., 30., 25.)] for y in rapidities])
        events["eventNumber"] = rows.eventNumber.to_list()
        events["mcWeight"] = [-1. if index % 7 == 0 else 1. for index in range(count)]
        events.update(xsec=[28.3] * count, kfac=[1.717] * count, filteff=[.000124] * count, sum_of_weights=[45231012.] * count)
        with uproot.recreate(path) as root:
            root[sample.tree_name] = {branch: events[name] for name, branch in sample.branches.items()}
        samples[role] = replace(sample, sha256=sha256_file(path), expected_entry_count=count)
    protocol = replace(protocol, samples=samples)
    config = tmp_path / "preprocess.yaml"
    config.write_text("schema_version: '2.0'\ndata_root: .\nresources: {chunk_size_events: 31}\n")
    run = tmp_path / "runs/preprocess"
    with monkeypatch.context() as context:
        context.setattr(pipeline, "load_preprocess_protocol", lambda *a, **k: protocol)
        pipeline.execute_preprocess(dataset=dataset, protocol_path=PROJECT / "config/preprocess_protocol_inclusive.yaml",
            run_config_path=config, run_dir=run, allowed_root=tmp_path / "runs")
    frame = pd.concat([pd.read_csv(run / f"processed/{partition}_events.csv.gz") for partition in ("development", "test")], ignore_index=True)
    assert "train_weight" not in frame and frame.m4l.max() > 160
    return run, frame


def fast_real_training(monkeypatch):
    """Run real optimization; synthetic eligibility isolates artifact/test mechanics."""
    calls = []

    def short_fold(fold, protocol, **kwargs):
        raw = deepcopy(protocol.raw)
        raw["optimization"]["maximum_epochs"] = 2
        calls.append((kwargs["target_lambda"], fold.fold_index, deepcopy(fold.scientific_state)))
        return train_fold(fold, replace(protocol, raw=raw), **kwargs)

    monkeypatch.setattr(app, "train_fold", short_fold)
    monkeypatch.setattr(app, "evaluate_candidate", lambda frame, protocol: _candidate(float(frame.target_lambda.iloc[0]), eligible_lambda=0.0))
    return calls


@pytest.mark.parametrize("dataset", ["atlas2020_4lep", "atlas2025_exactly4lep"])
def test_inclusive_development_and_test_with_real_optimizer(tmp_path, monkeypatch, dataset):
    root = tmp_path / "runs"
    preprocess, frame = preprocess_synthetic_roots(tmp_path, monkeypatch, dataset)
    calls = fast_real_training(monkeypatch)
    development = root / "development"
    result = app.execute_development(dataset=dataset, input_run=preprocess, protocol_path=PROTOCOL, run_dir=development, allowed_root=root)
    assert result.status == "eligible"
    assert len(calls) == 25
    for index in range(5):
        assert all(state == calls[index][2] for _, fold, state in calls if fold == index)
    manifest = json.loads((development / "artifacts/manifest.json").read_bytes())
    assert manifest["schema_version"] == "development-manifest-v3"
    assert "metric_weight" in manifest["schema"]["oof_columns"]
    assert "train_weight" not in manifest["schema"]["oof_columns"]
    scientific = json.loads((development / "artifacts/scientific_state.json").read_bytes())
    oof = pd.read_csv(development / "predictions/oof_scores.csv.gz")
    assert np.array_equal(oof.metric_weight, np.abs(oof.physical_weight))
    assert len(oof) == len(frame.loc[frame.split != "test"]) * 5
    binding = _load_binding(development, allowed_root=root, dataset=dataset)
    assert binding.scientific_state == scientific
    test_result = execute_test_opening(dataset=dataset, development_run=development, run_dir=root / "evaluation", allowed_root=root)
    assert test_result.status in {"test_reproduced", "test_nonreproduction"}
    assert test_result.metrics["mass_diagnostics"]["binning"] == scientific["report_binning"]
    assert all(v is False for v in test_result.metrics["boundaries"].values())
    test_scores = pd.read_csv(root / "evaluation/predictions/test_scores.csv.gz")
    assert "train_weight" not in test_scores
    assert len(test_scores) == int((frame.split == "test").sum())
    with pytest.raises(OpeningRefused, match="debug"):
        _load_binding(development, allowed_root=root, dataset=dataset, debug=True)
    other = "atlas2025_exactly4lep" if dataset == "atlas2020_4lep" else "atlas2020_4lep"
    with pytest.raises(InputBindingError):
        _load_binding(development, allowed_root=root, dataset=other)
    # Even a refreshed model file receipt cannot replace its bound scientific state.
    from src.artifacts.manifest import write_canonical_json, sha256_file
    model_path = development / "model/model.pt"
    manifest_path = development / "artifacts/manifest.json"
    original_model, original_manifest = model_path.read_bytes(), manifest_path.read_bytes()
    with torch.serialization.safe_globals([torch.torch_version.TorchVersion]):
        payload = torch.load(model_path, weights_only=True)
    payload["scientific_state"]["weight_normalization"]["class_means"]["0"] *= 2
    torch.save(payload, model_path)
    for record in manifest["outputs"]:
        if record["path"] == "model/model.pt":
            record.update(sha256=sha256_file(model_path), size_bytes=model_path.stat().st_size)
    write_canonical_json(manifest_path, manifest)
    with pytest.raises(InputBindingError, match="scientific state"):
        _load_binding(development, allowed_root=root, dataset=dataset)
    model_path.write_bytes(original_model)
    manifest_path.write_bytes(original_manifest)
    # Binding remains valid without opening test; scoring must verify actual bytes.
    table = preprocess / "processed/test_events.csv.gz"
    table.write_bytes(table.read_bytes() + b"changed")
    rebound = _load_binding(development, allowed_root=root, dataset=dataset)
    with pytest.raises(InputBindingError, match="test partition hash"):
        _evaluate(rebound)


def test_inclusive_statistics_terminal_precedes_training_and_test(tmp_path, monkeypatch):
    preprocess, _ = write_synthetic_preprocess_run(tmp_path, inclusive=True, poison_test_feature=True,
        frame_override=lambda f: f.assign(m4l=125.0))
    monkeypatch.setattr(app, "train_fold", lambda *a, **k: pytest.fail("optimizer must not start"))
    run = tmp_path / "insufficient"
    result = app.execute_development(dataset="atlas2020_4lep", input_run=preprocess, protocol_path=PROTOCOL, run_dir=run, allowed_root=tmp_path)
    assert result.status == "insufficient_statistics"
    assert not (run / "model").exists()
    manifest = json.loads((run / "artifacts/manifest.json").read_bytes())
    assert manifest["boundaries"] == {"held_out_test_opened": False, "training_performed": False}
    with pytest.raises(OpeningRefused, match="insufficient_statistics"):
        _load_binding(run, allowed_root=tmp_path, dataset="atlas2020_4lep")


def test_inclusive_reader_requires_correct_lineage_and_does_not_open_test(tmp_path):
    preprocess, _ = write_synthetic_preprocess_run(tmp_path, inclusive=True, poison_test_feature=True)
    protocol = load_training_protocol(PROTOCOL)
    kwargs = dict(dataset="atlas2020_4lep", allowed_root=tmp_path, protocol_sha256=protocol.sha256)
    first = read_development_input(preprocess, inclusive=True, **kwargs)
    table = preprocess / "processed/test_events.csv.gz"
    table.write_bytes(b"unreadable test bytes")
    second = read_development_input(preprocess, inclusive=True, **kwargs)
    pd.testing.assert_frame_equal(first.development.frame, second.development.frame)
    with pytest.raises(InputBindingError):
        read_development_input(preprocess, **kwargs)
    with pytest.raises(InputBindingError):
        read_development_input(preprocess, inclusive=True, **{**kwargs, "dataset": "atlas2025_exactly4lep"})


@pytest.mark.parametrize("dataset", ["atlas2020_4lep", "atlas2025_exactly4lep"])
def test_inclusive_micro_root_preprocessing(tmp_path, dataset):
    from tests.integration.test_preprocess_micro_root import _write_inputs
    from src.artifacts.manifest import sha256_file
    from src.preprocessing.pipeline import prepare_table
    higgs, zz = _write_inputs(tmp_path, dataset)
    protocol = load_preprocess_protocol(PROJECT / "config/preprocess_protocol_inclusive.yaml", dataset=dataset)
    protocol = replace(protocol, samples={role: replace(protocol.samples[role], sha256=sha256_file(path), expected_entry_count=2) for role, path in (("higgs", higgs), ("zz", zz))})
    frame, cuts, _, _ = prepare_table(protocol, PreprocessRunConfig({"higgs": higgs, "zz": zz}, 1, b"fixture"))
    assert len(frame) == 4
    assert "train_weight" not in frame
    assert all(cut["stages"]["m4l_analysis_window"]["enabled"] is False for cut in cuts.values())


def test_inclusive_unqualified_oof_does_not_publish_model(tmp_path, monkeypatch):
    from tests.integration.test_development_run import _fake_fold_result
    preprocess, _ = write_synthetic_preprocess_run(tmp_path, inclusive=True, poison_test_feature=True)
    monkeypatch.setattr(app, "train_fold", lambda fold, protocol, *, target_lambda: _fake_fold_result(fold, target_lambda))
    monkeypatch.setattr(app, "train_fixed_epochs", lambda *a, **k: pytest.fail("no eligible final fit"))
    run = tmp_path / "unqualified"
    result = app.execute_development(dataset="atlas2020_4lep", input_run=preprocess, protocol_path=PROTOCOL, run_dir=run, allowed_root=tmp_path)
    # Perfect class ranking with tied background scores selects all background;
    # epsilon_s == epsilon_b == 1 violates the sealed strict efficiency rule.
    assert result.status == "no_eligible_candidate"
    assert not (run / "model").exists()
    assert (run / "artifacts/mass_diagnostics.json").is_file()
    qualification = json.loads((run / "artifacts/qualification.json").read_bytes())
    assert all("loose_signal_efficiency_not_greater" in row["rejection_reasons"] for row in qualification["candidates"])
    with pytest.raises(OpeningRefused, match="inclusive development run") as error:
        _load_binding(run, allowed_root=tmp_path, dataset="atlas2020_4lep")
    assert "--debug" not in str(error.value)
