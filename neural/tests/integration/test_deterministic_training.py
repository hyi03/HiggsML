from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

from src.config import InputBindingError
from src.training.config import TrainingProtocol, load_training_protocol
from src.training.dataset import build_validated_fold, validate_development_frame
from src.training.network import Adversary
from src.training.trainer import (
    EarlyStoppingState,
    lambda_for_epoch,
    train_fixed_epochs,
    train_fold,
    validate_checkpoint,
)
from tests.training_fixtures import synthetic_development_frame


PROJECT = Path(__file__).resolve().parents[2]


def _fold():
    protocol = load_training_protocol(PROJECT / "config/adversarial_mlp_protocol_normal.yaml")
    frame = synthetic_development_frame()
    development = validate_development_frame(frame, protocol_sha256=protocol.sha256)
    fitting = np.flatnonzero(frame["split"].to_numpy() == "train")
    validation = np.flatnonzero(frame["split"].to_numpy() == "validation")
    return protocol, build_validated_fold(development, fitting, validation, fold_index=0)


def test_lambda_schedule_boundaries() -> None:
    target = 0.5
    assert [lambda_for_epoch(epoch, target) for epoch in (1, 5, 6, 14, 15, 16)] == [
        0.0,
        0.0,
        0.05,
        0.45,
        0.5,
        0.5,
    ]

    with pytest.raises(InputBindingError):
        lambda_for_epoch(1, 0.3)
    with pytest.raises(InputBindingError):
        lambda_for_epoch(0, 0.5)


def test_synthetic_cpu_training_is_exactly_deterministic() -> None:
    protocol, fold = _fold()
    first = train_fold(fold, protocol, target_lambda=0.0)
    second = train_fold(fold, protocol, target_lambda=0.0)

    assert first.best_epoch == second.best_epoch
    assert first.best_validation_weighted_auc == second.best_validation_weighted_auc
    assert first.validation_scores == second.validation_scores
    assert len(first.epochs) == len(second.epochs)
    for name, tensor in first.checkpoint["classifier_state_dict"].items():
        assert torch.equal(tensor, second.checkpoint["classifier_state_dict"][name])
    validate_checkpoint(first.checkpoint, protocol, fold)
    assert first.environment["device"] == "cpu"
    assert first.environment["deterministic_algorithms"] is True


@pytest.mark.parametrize("target_lambda", [0.05, 0.50])
def test_nonzero_lambda_training_is_exactly_deterministic(target_lambda: float) -> None:
    protocol, fold = _fold()
    first = train_fold(fold, protocol, target_lambda=target_lambda)
    second = train_fold(fold, protocol, target_lambda=target_lambda)

    deterministic_first = [
        (
            metric.epoch,
            metric.lambda_effective,
            metric.train_cls_loss,
            metric.train_adv_loss,
            metric.train_total_loss,
            metric.validation_weighted_auc,
            metric.is_best,
        )
        for metric in first.epochs
    ]
    deterministic_second = [
        (
            metric.epoch,
            metric.lambda_effective,
            metric.train_cls_loss,
            metric.train_adv_loss,
            metric.train_total_loss,
            metric.validation_weighted_auc,
            metric.is_best,
        )
        for metric in second.epochs
    ]
    assert deterministic_first == deterministic_second
    assert first.validation_scores == second.validation_scores
    for key in ("classifier_state_dict", "adversary_state_dict"):
        assert all(
            torch.equal(tensor, second.checkpoint[key][name])
            for name, tensor in first.checkpoint[key].items()
        )


def test_different_lambdas_reuse_warmup_initialization_and_batch_order() -> None:
    protocol, fold = _fold()
    low = train_fold(fold, protocol, target_lambda=0.05)
    high = train_fold(fold, protocol, target_lambda=0.50)

    assert len(low.epochs) >= 5 and len(high.epochs) >= 5
    for low_metric, high_metric in zip(low.epochs[:5], high.epochs[:5], strict=True):
        assert (
            low_metric.epoch,
            low_metric.lambda_effective,
            low_metric.train_cls_loss,
            low_metric.train_adv_loss,
            low_metric.train_total_loss,
            low_metric.validation_weighted_auc,
            low_metric.is_best,
        ) == (
            high_metric.epoch,
            high_metric.lambda_effective,
            high_metric.train_cls_loss,
            high_metric.train_adv_loss,
            high_metric.train_total_loss,
            high_metric.validation_weighted_auc,
            high_metric.is_best,
        )


def test_early_stopping_tie_threshold_reset_and_patience() -> None:
    state = EarlyStoppingState()
    assert state.observe(0.5, 1, minimum_improvement=1.0e-4, patience=20) == (True, False)
    assert state.observe(0.5, 2, minimum_improvement=1.0e-4, patience=20) == (False, False)
    assert state.observe(0.5001, 3, minimum_improvement=1.0e-4, patience=20) == (False, False)
    assert state.non_improving == 2
    assert state.observe(0.5001001, 4, minimum_improvement=1.0e-4, patience=20) == (True, False)
    assert state.non_improving == 0
    assert state.best_epoch == 4

    patience_state = EarlyStoppingState()
    patience_state.observe(0.5, 1, minimum_improvement=1.0e-4, patience=20)
    for epoch in range(2, 21):
        assert patience_state.observe(0.5, epoch, minimum_improvement=1.0e-4, patience=20) == (False, False)
    assert patience_state.observe(0.5, 21, minimum_improvement=1.0e-4, patience=20) == (False, True)


def test_unregistered_lambda_is_rejected_before_training() -> None:
    protocol, fold = _fold()
    with pytest.raises(InputBindingError, match="not pre-registered"):
        train_fold(fold, protocol, target_lambda=0.3)


def test_zero_effective_background_skips_adversary_forward(monkeypatch: pytest.MonkeyPatch) -> None:
    protocol, fold = _fold()
    fold = replace(fold, adversarial_weights=torch.zeros_like(fold.adversarial_weights))

    def forbidden_forward(*args: object, **kwargs: object) -> torch.Tensor:
        raise AssertionError("adversary received a zero-effective-background batch")

    monkeypatch.setattr(Adversary, "forward", forbidden_forward)
    result = train_fold(fold, protocol, target_lambda=0.50)

    assert all(metric.train_adv_loss == 0.0 for metric in result.epochs)


def test_epoch_loss_uses_raw_components_and_keeps_partial_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol, fold = _fold()
    monkeypatch.setattr(TrainingProtocol, "batch_size", property(lambda self: 7))
    monkeypatch.setattr(TrainingProtocol, "maximum_epochs", property(lambda self: 1))

    def controlled_components(
        logits: torch.Tensor, labels: torch.Tensor, weights: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        denominator = weights.sum()
        return logits.sum() * 0.0 + denominator.square(), denominator

    monkeypatch.setattr("src.training.trainer.binary_loss_components", controlled_components)
    result = train_fold(fold, protocol, target_lambda=0.0)

    assert fold.fitting_features.shape[0] == 22
    assert result.epochs_completed == 1
    assert result.epochs[0].train_cls_loss == pytest.approx((49.0 + 49.0 + 49.0 + 1.0) / 22.0)


def test_checkpoint_validator_rejects_metric_and_state_corruption() -> None:
    protocol, fold = _fold()
    result = train_fold(fold, protocol, target_lambda=0.0)
    original = result.checkpoint

    corruptions = []
    missing = copy.deepcopy(original)
    missing.pop("best_epoch")
    corruptions.append(missing)
    bad_auc = copy.deepcopy(original)
    bad_auc["best_validation_weighted_auc"] = 1.1
    corruptions.append(bad_auc)
    for mutation in ("shape", "dtype", "device"):
        changed = copy.deepcopy(original)
        name = next(iter(changed["classifier_state_dict"]))
        tensor = changed["classifier_state_dict"][name]
        if mutation == "shape":
            changed["classifier_state_dict"][name] = tensor[:-1]
        elif mutation == "dtype":
            changed["classifier_state_dict"][name] = tensor.to(torch.float64)
        else:
            changed["classifier_state_dict"][name] = torch.empty_like(tensor, device="meta")
        corruptions.append(changed)

    for changed in corruptions:
        with pytest.raises(InputBindingError):
            validate_checkpoint(changed, protocol, fold)


def test_checkpoint_validation_preserves_torch_rng_state() -> None:
    protocol, fold = _fold()
    result = train_fold(fold, protocol, target_lambda=0.0)
    torch.manual_seed(917)
    before = torch.random.get_rng_state().clone()

    validate_checkpoint(result.checkpoint, protocol, fold)

    assert torch.equal(before, torch.random.get_rng_state())


def test_runtime_nonfinite_metric_is_internal_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol, fold = _fold()
    monkeypatch.setattr(TrainingProtocol, "maximum_epochs", property(lambda self: 1))
    monkeypatch.setattr("src.training.trainer.roc_auc_score", lambda *args, **kwargs: float("nan"))

    with pytest.raises(RuntimeError, match="non-finite training metric"):
        train_fold(fold, protocol, target_lambda=0.0)


def test_final_fit_uses_all_development_and_exact_fixed_epoch_count() -> None:
    protocol, fold = _fold()
    frame = synthetic_development_frame()
    development = validate_development_frame(frame, protocol_sha256=protocol.sha256)

    first = train_fixed_epochs(development, protocol, target_lambda=0.50, epochs=6)
    second = train_fixed_epochs(development, protocol, target_lambda=0.50, epochs=6)

    assert first.scaler.fitting_rows == len(frame)
    assert len(first.epochs) == 6
    assert first.epochs[-1]["lambda_effective"] == 0.05
    assert first.model_payload["epochs"] == 6
    assert type(first.model_payload["environment"]["pytorch"]) is str
    assert "validation_weighted_auc" not in first.epochs[-1]
    for key in ("classifier_state_dict", "adversary_state_dict"):
        assert all(
            torch.equal(tensor, second.model_payload[key][name])
            for name, tensor in first.model_payload[key].items()
        )
