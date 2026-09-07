from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from src.config import InputBindingError, load_preprocess_protocol
from src.domain.selection import SelectionConfig, select_event
from src.training.config import load_training_protocol, INCLUSIVE_INPUT_COLUMNS
from src.training.dataset import validate_development_frame, build_validated_fold
from src.training.inclusive import MassBinning, InsufficientStatistics, fit_scientific_state
from src.training.mass_diagnostics import mass_diagnostics
from src.training.qualification import weighted_roc_points, weighted_auc
from src.training.trainer import train_fold, validate_checkpoint
from tests.development_fixtures import write_synthetic_preprocess_run
from tests.unit.test_preprocess_domain import _event

PROJECT = Path(__file__).resolve().parents[2]


def test_semantic_protocol_names_preserve_old_exact_bytes():
    hashes = {
        "preprocess_protocol_mass_window.yaml": "2d58eaaf8788d50e9d8fc2232782b6bbf6504237867968d0134c4d7fbedf99e3",
        "adversarial_mlp_protocol_mass_window.yaml": "78b958ce8dd27222840be4bbd7d5084f72e3571c0e2cb7524469ade862c054fd"}
    for name, expected in hashes.items():
        assert hashlib.sha256((PROJECT / "config" / name).read_bytes()).hexdigest() == expected
    assert not (PROJECT / "config/preprocess_protocol_v2.yaml").exists()
    assert not (PROJECT / "config/adversarial_mlp_protocol_normal_v2.yaml").exists()


def test_inclusive_protocol_is_sealed_and_filename_independent(tmp_path):
    path = PROJECT / "config/adversarial_mlp_protocol_inclusive.yaml"
    renamed = tmp_path / "arbitrary.yaml"
    renamed.write_bytes(path.read_bytes())
    assert load_training_protocol(renamed).inclusive
    with pytest.raises(InputBindingError, match="debug"):
        load_training_protocol(path, debug=True)
    renamed.write_text(path.read_text().replace("auc_minimum: 0.8", "auc_minimum: 0.7"))
    with pytest.raises(InputBindingError):
        load_training_protocol(renamed)


def test_quantiles_right_closure_tails_ties_and_signed_weights():
    masses = np.repeat(np.arange(1, 23, dtype=float), 2)
    weights = np.tile([1.0, -1.0], 22)
    binning = MassBinning.fit(masses, weights)
    assert binning.boundaries == tuple(float(i) for i in range(2, 22, 2))
    assert binning.indices([0, 2, 2.01, 20, 20.01, 1e12]).tolist() == [0, 0, 1, 9, 10, 10]
    assert MassBinning.fit(masses[::-1], weights[::-1]) == binning
    assert MassBinning.fit(np.append(masses, 1e20), np.append(weights, 0)) == binning
    assert MassBinning.from_dict(binning.to_dict()) == binning
    assert binning.to_dict()["edges_gev"][0] is None


@pytest.mark.parametrize("masses,weights", [([1] * 22, [1] * 22), (list(range(22)), [0] * 22), (list(range(22)), [1000] + [1] * 21)])
def test_degenerate_quantiles_stop(masses, weights):
    with pytest.raises(InsufficientStatistics):
        MassBinning.fit(masses, weights)


def test_no_window_preserves_other_selection():
    normal = load_preprocess_protocol(PROJECT / "config/preprocess_protocol_mass_window.yaml", dataset="atlas2020_4lep")
    inclusive = load_preprocess_protocol(PROJECT / "config/preprocess_protocol_inclusive.yaml", dataset="atlas2020_4lep")
    assert tuple(inclusive.output_columns) == INCLUSIVE_INPUT_COLUMNS
    assert {k: v for k, v in normal.selection.items() if k != "m4l_window_gev"} == {k: v for k, v in inclusive.selection.items() if k != "m4l_window_gev"}
    event = _event()
    event["lep_pt"] = [p * 1.2 for p in event["lep_pt"]]
    event["lep_e"] = [p * 1.2 for p in event["lep_e"]]
    assert select_event(event, SelectionConfig.from_mapping(normal.selection), "GeV").failed_stage == "m4l_analysis_window"
    assert select_event(event, SelectionConfig.from_mapping(inclusive.selection), "GeV").accepted
    event["trigE"] = False
    assert select_event(event, SelectionConfig.from_mapping(inclusive.selection), "GeV").failed_stage == "trigger"


def test_fitting_state_and_scaler_ignore_validation(tmp_path):
    _, frame = write_synthetic_preprocess_run(tmp_path, inclusive=True)
    frame = frame.loc[frame.split != "test"].reset_index(drop=True)
    protocol = load_training_protocol(PROJECT / "config/adversarial_mlp_protocol_inclusive.yaml")
    from src.training.folds import assign_folds
    dev = validate_development_frame(frame, protocol_sha256=protocol.sha256, inclusive=True)
    folds = assign_folds(dev)
    fitting, validation = np.flatnonzero(folds != 0), np.flatnonzero(folds == 0)
    fold = build_validated_fold(dev, fitting, validation, fold_index=0)
    changed = frame.copy()
    changed.loc[validation, "physical_weight"] *= 100
    changed.loc[validation, "m4l"] += 10000
    changed.loc[validation, "lep1_pt"] += 10000
    other = build_validated_fold(validate_development_frame(changed, protocol_sha256=protocol.sha256, inclusive=True), fitting, validation, fold_index=0)
    assert fold.scientific_state == other.scientific_state
    assert fold.scaler.to_dict() == other.scaler.to_dict()
    assert torch.equal(fold.train_weights, other.train_weights)
    for label in (0, 1):
        assert fold.train_weights[fold.labels == label].mean().item() == pytest.approx(1.0)
    assert np.array_equal(fold.validation_metric_weights.numpy(), np.abs(frame.iloc[validation].physical_weight))
    short = deepcopy(protocol.raw)
    short["optimization"]["maximum_epochs"] = 16
    result = train_fold(fold, replace(protocol, raw=short), target_lambda=0.1)
    assert any(epoch.lambda_effective > 0 and epoch.train_adv_loss > 0 for epoch in result.epochs)
    assert result.checkpoint["scientific_state"] == fold.scientific_state
    tampered = deepcopy(result.checkpoint)
    tampered["scientific_state"]["weight_normalization"]["class_means"]["0"] *= 2
    with pytest.raises(InputBindingError, match="scientific state"):
        validate_checkpoint(tampered, protocol, fold)


def test_metric_weights_and_unavailable_local_diagnostics():
    frame = pd.DataFrame({"label": [0, 0, 1, 1], "score": [.1, .8, .6, .9],
                          "metric_weight": [10., 1., 1., 1.], "physical_weight": [-10., 1., 1., 1.], "m4l": [0., 100., 1., 200.]})
    fpr, tpr = weighted_roc_points(frame)
    assert weighted_auc(frame.label, frame.score, frame.metric_weight) == pytest.approx(np.trapezoid(tpr, fpr))
    bins = MassBinning(tuple(float(i) for i in range(10, 110, 10)))
    report = mass_diagnostics(frame, bins, {"tight": {"threshold": 1.0}})
    assert sum(x["classes"]["0"]["rows"] + x["classes"]["1"]["rows"] for x in report["statistics"]) == 4
    assert all(x["local_mass_ks"] is None and x["unavailable_reasons"] for x in report["working_points"]["tight"]["bins"])


def test_zero_weight_batches_do_not_update_or_abort(tmp_path):
    from src.training.folds import assign_folds
    from src.training.trainer import train_fixed_epochs
    _, frame = write_synthetic_preprocess_run(tmp_path, inclusive=True)
    frame = frame.loc[frame.split != "test"].reset_index(drop=True)
    frame.loc[frame.index[::4], "physical_weight"] = 0.0
    protocol = load_training_protocol(PROJECT / "config/adversarial_mlp_protocol_inclusive.yaml")
    dev = validate_development_frame(frame, protocol_sha256=protocol.sha256, inclusive=True)
    folds = assign_folds(dev)
    fold = build_validated_fold(dev, np.flatnonzero(folds != 0), np.flatnonzero(folds == 0), fold_index=0)
    raw = deepcopy(protocol.raw)
    raw["optimization"].update(batch_size=1, maximum_epochs=1)
    short = replace(protocol, raw=raw)
    trained = train_fold(fold, short, target_lambda=0.0)
    final = train_fixed_epochs(dev, short, target_lambda=0.0, epochs=1)
    assert np.isfinite(trained.epochs[0].train_cls_loss)
    assert np.isfinite(final.epochs[0]["train_cls_loss"])
