from __future__ import annotations

from dataclasses import dataclass
import copy
import platform
import random
import sys
import time
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score
import torch
from torch import Tensor

from src.config import InputBindingError
from src.training.config import TARGET_LAMBDAS, TrainingProtocol
from src.training.dataset import FEATURE_COLUMNS, FoldLocalScaler, ValidatedDevelopment, ValidatedFold
from src.training.losses import (
    adversarial_bin_weights,
    adversarial_loss_components,
    binary_loss_components,
    mass_bin_indices,
)
from src.training.network import AdversarialMLP


@dataclass(frozen=True)
class EpochMetric:
    epoch: int
    lambda_effective: float
    train_cls_loss: float
    train_adv_loss: float
    train_total_loss: float
    validation_weighted_auc: float
    is_best: bool
    duration_seconds: float
    events_per_second: float


@dataclass(frozen=True)
class TrainingResult:
    checkpoint: dict[str, Any]
    epochs: tuple[EpochMetric, ...]
    epochs_completed: int
    stopped_early: bool
    best_epoch: int
    best_validation_weighted_auc: float
    validation_scores: tuple[float, ...]
    environment: dict[str, Any]


@dataclass(frozen=True)
class FinalTrainingResult:
    model_payload: dict[str, Any]
    epochs: tuple[dict[str, float | int], ...]
    scaler: FoldLocalScaler
    environment: dict[str, Any]


@dataclass
class EarlyStoppingState:
    best_auc: float = -np.inf
    best_epoch: int = 0
    non_improving: int = 0

    def observe(self, auc: float, epoch: int, *, minimum_improvement: float, patience: int) -> tuple[bool, bool]:
        if (
            not np.isfinite(auc)
            or type(epoch) is not int
            or epoch < 1
            or not np.isfinite(minimum_improvement)
            or minimum_improvement < 0
            or type(patience) is not int
            or patience < 1
        ):
            raise RuntimeError("invalid early-stopping metric state")
        improved = self.best_epoch == 0 or auc > self.best_auc + minimum_improvement
        if improved:
            self.best_auc = float(auc)
            self.best_epoch = int(epoch)
            self.non_improving = 0
        else:
            self.non_improving += 1
        return improved, self.non_improving >= patience


def lambda_for_epoch(
    epoch: int,
    target_lambda: float,
    *,
    warmup_epochs: int = 5,
    ramp_epochs: int = 10,
) -> float:
    if (
        type(epoch) is not int
        or epoch < 1
        or type(target_lambda) is not float
        or target_lambda not in TARGET_LAMBDAS
        or type(warmup_epochs) is not int
        or warmup_epochs < 0
        or type(ramp_epochs) is not int
        or ramp_epochs < 1
    ):
        raise InputBindingError("invalid lambda schedule input")
    if epoch <= warmup_epochs:
        return 0.0
    if epoch <= warmup_epochs + ramp_epochs:
        return float(target_lambda * (epoch - warmup_epochs) / ramp_epochs)
    return float(target_lambda)


def _seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)


def _state(module: torch.nn.Module) -> dict[str, Tensor]:
    return {name: value.detach().cpu().clone() for name, value in module.state_dict().items()}


def _checkpoint(model: AdversarialMLP, fold: ValidatedFold, protocol: TrainingProtocol, target_lambda: float, epoch: int, auc: float) -> dict[str, Any]:
    return {
        "protocol_sha256": protocol.sha256,
        "feature_tuple": FEATURE_COLUMNS,
        "scaler": fold.scaler.to_dict(),
        "fold_index": fold.fold_index,
        "fold_seed": fold.fold_seed,
        "target_lambda": float(target_lambda),
        "best_epoch": int(epoch),
        "best_validation_weighted_auc": float(auc),
        "classifier_state_dict": _state(model.classifier),
        "adversary_state_dict": _state(model.adversary),
    }


def validate_checkpoint(checkpoint: dict[str, Any], protocol: TrainingProtocol, fold: ValidatedFold) -> None:
    required = {"protocol_sha256", "feature_tuple", "scaler", "fold_index", "fold_seed", "target_lambda", "best_epoch", "best_validation_weighted_auc", "classifier_state_dict", "adversary_state_dict"}
    if set(checkpoint) != required or checkpoint["protocol_sha256"] != protocol.sha256 or checkpoint["protocol_sha256"] != fold.protocol_sha256:
        raise InputBindingError("checkpoint protocol binding changed")
    if (
        tuple(checkpoint["feature_tuple"]) != FEATURE_COLUMNS
        or type(checkpoint["fold_index"]) is not int
        or checkpoint["fold_index"] != fold.fold_index
        or type(checkpoint["fold_seed"]) is not int
        or checkpoint["fold_seed"] != fold.fold_seed
    ):
        raise InputBindingError("checkpoint fold binding changed")
    auc = checkpoint["best_validation_weighted_auc"]
    if (
        type(checkpoint["target_lambda"]) is not float
        or checkpoint["target_lambda"] not in protocol.target_lambdas
        or type(checkpoint["best_epoch"]) is not int
        or checkpoint["best_epoch"] < 1
        or type(auc) is not float
        or not np.isfinite(auc)
        or not 0.0 <= auc <= 1.0
    ):
        raise InputBindingError("checkpoint metric binding changed")
    type(fold.scaler).from_dict(checkpoint["scaler"])
    with torch.random.fork_rng(devices=[]):
        expected = AdversarialMLP()
    for key, module in (("classifier_state_dict", expected.classifier), ("adversary_state_dict", expected.adversary)):
        state = checkpoint[key]
        reference = module.state_dict()
        if not isinstance(state, dict) or set(state) != set(reference):
            raise InputBindingError("checkpoint state-dict keys changed")
        for name, tensor in state.items():
            if not isinstance(tensor, Tensor) or tensor.shape != reference[name].shape or tensor.dtype != torch.float32 or tensor.device.type != "cpu" or not torch.isfinite(tensor).all():
                raise InputBindingError("checkpoint state-dict tensor changed")


def _environment() -> dict[str, Any]:
    return {
        "os": platform.system(), "architecture": platform.machine(), "python": sys.version.split()[0],
        "pytorch": torch.__version__, "device": "cpu", "dtype": "float32", "threads": torch.get_num_threads(),
        "data_loader_workers": 0, "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
    }


def train_fold(fold: ValidatedFold, protocol: TrainingProtocol, *, target_lambda: float) -> TrainingResult:
    if target_lambda not in protocol.target_lambdas:
        raise InputBindingError("target lambda is not pre-registered")
    if fold.protocol_sha256 != protocol.sha256:
        raise InputBindingError("fold protocol binding changed")
    _seed(fold.fold_seed)
    model = AdversarialMLP().cpu().to(torch.float32)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(protocol.raw["optimization"]["learning_rate"]),
        weight_decay=float(protocol.raw["optimization"]["weight_decay"]),
    )
    generator = torch.Generator(device="cpu").manual_seed(fold.fold_seed)
    early = EarlyStoppingState()
    best_checkpoint: dict[str, Any] | None = None
    metrics: list[EpochMetric] = []
    stopped_early = False
    rows = fold.fitting_features.shape[0]

    for epoch in range(1, protocol.maximum_epochs + 1):
        started = time.perf_counter()
        model.train()
        effective = lambda_for_epoch(
            epoch,
            target_lambda,
            warmup_epochs=protocol.warmup_epochs,
            ramp_epochs=protocol.ramp_epochs,
        )
        order = torch.randperm(rows, generator=generator)
        cls_num = cls_den = adv_num = adv_den = 0.0
        for offset in range(0, rows, protocol.batch_size):
            index = order[offset : offset + protocol.batch_size]
            features = fold.fitting_features[index]
            labels = fold.labels[index]
            class_weights = fold.train_weights[index]
            optimizer.zero_grad(set_to_none=True)
            logits = model.classifier(features)
            cls_numerator, cls_denominator = binary_loss_components(logits, labels, class_weights)
            cls_loss = cls_numerator / cls_denominator
            cls_num += float(cls_numerator.item())
            cls_den += float(cls_denominator.item())
            adv_loss = 0.0 * logits.sum()
            if effective > 0.0:
                background = labels == 0
                adv_weights = fold.adversarial_weights[index][background]
                if torch.any(background) and adv_weights.sum().item() > 0.0:
                    adv_logits = model.adversary(logits[background], lambda_effective=effective)
                    adv_numerator, adv_denominator = adversarial_loss_components(adv_logits, fold.mass_bins[index][background], adv_weights)
                    adv_loss = adv_numerator / adv_denominator
                    adv_num += float(adv_numerator.item())
                    adv_den += float(adv_denominator.item())
            (cls_loss + adv_loss).backward()
            optimizer.step()
        cls_epoch = cls_num / cls_den
        adv_epoch = adv_num / adv_den if adv_den > 0 else 0.0
        model.eval()
        with torch.no_grad():
            validation_logits = model.classifier(fold.validation_features)
            validation_scores = torch.sigmoid(validation_logits).cpu().numpy()
        auc = float(roc_auc_score(fold.validation_labels.numpy(), validation_scores, sample_weight=fold.validation_weights.numpy()))
        if not np.isfinite(auc) or not np.isfinite(cls_epoch) or not np.isfinite(adv_epoch):
            raise RuntimeError("non-finite training metric")
        improved, should_stop = early.observe(
            auc, epoch, minimum_improvement=protocol.minimum_improvement, patience=protocol.patience
        )
        if improved:
            best_checkpoint = _checkpoint(model, fold, protocol, target_lambda, epoch, auc)
        duration = time.perf_counter() - started
        metrics.append(EpochMetric(epoch, effective, cls_epoch, adv_epoch, cls_epoch + adv_epoch, auc, improved, duration, rows / max(duration, np.finfo(float).eps)))
        if should_stop:
            stopped_early = True
            break

    if best_checkpoint is None:
        raise RuntimeError("training completed without checkpoint")
    validate_checkpoint(best_checkpoint, protocol, fold)
    model.classifier.load_state_dict(copy.deepcopy(best_checkpoint["classifier_state_dict"]))
    model.classifier.eval()
    with torch.no_grad():
        best_scores = tuple(float(value) for value in torch.sigmoid(model.classifier(fold.validation_features)).tolist())
    return TrainingResult(
        best_checkpoint, tuple(metrics), len(metrics), stopped_early,
        int(best_checkpoint["best_epoch"]), float(best_checkpoint["best_validation_weighted_auc"]),
        best_scores, _environment(),
    )


def train_fixed_epochs(
    development: ValidatedDevelopment,
    protocol: TrainingProtocol,
    *,
    target_lambda: float,
    epochs: int,
) -> FinalTrainingResult:
    if (
        target_lambda not in protocol.target_lambdas
        or type(epochs) is not int
        or epochs < 1
        or epochs > protocol.maximum_epochs
        or development.protocol_sha256 != protocol.sha256
    ):
        raise InputBindingError("final-fit binding changed")
    frame = development.frame
    scaler = FoldLocalScaler.fit(frame[list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64))
    features = torch.from_numpy(
        scaler.transform(frame[list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64))
    )
    labels = torch.tensor(frame["label"].to_numpy(), dtype=torch.int64)
    class_weights = torch.tensor(frame["train_weight"].to_numpy(), dtype=torch.float32)
    background = labels == 0
    masses = torch.tensor(frame.loc[background.numpy(), "m4l"].to_numpy(), dtype=torch.float64)
    physical = torch.tensor(
        frame.loc[background.numpy(), "physical_weight"].to_numpy(), dtype=torch.float32
    )
    bins = mass_bin_indices(masses)
    background_weights = adversarial_bin_weights(bins, physical)
    mass_bins = torch.full_like(labels, -1)
    adversarial_weights = torch.zeros_like(class_weights)
    mass_bins[background] = bins
    adversarial_weights[background] = background_weights

    seed = int(protocol.raw["final_fit"]["seed"])
    _seed(seed)
    model = AdversarialMLP().cpu().to(torch.float32)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(protocol.raw["optimization"]["learning_rate"]),
        weight_decay=float(protocol.raw["optimization"]["weight_decay"]),
    )
    generator = torch.Generator(device="cpu").manual_seed(seed)
    metrics: list[dict[str, float | int]] = []
    rows = len(frame)
    for epoch in range(1, epochs + 1):
        model.train()
        effective = lambda_for_epoch(
            epoch,
            target_lambda,
            warmup_epochs=protocol.warmup_epochs,
            ramp_epochs=protocol.ramp_epochs,
        )
        order = torch.randperm(rows, generator=generator)
        cls_num = cls_den = adv_num = adv_den = 0.0
        for offset in range(0, rows, protocol.batch_size):
            index = order[offset : offset + protocol.batch_size]
            optimizer.zero_grad(set_to_none=True)
            logits = model.classifier(features[index])
            cls_numerator, cls_denominator = binary_loss_components(
                logits, labels[index], class_weights[index]
            )
            cls_loss = cls_numerator / cls_denominator
            cls_num += float(cls_numerator.item())
            cls_den += float(cls_denominator.item())
            adv_loss = 0.0 * logits.sum()
            if effective > 0.0:
                batch_background = labels[index] == 0
                adv_weights = adversarial_weights[index][batch_background]
                if torch.any(batch_background) and adv_weights.sum().item() > 0.0:
                    adv_logits = model.adversary(
                        logits[batch_background], lambda_effective=effective
                    )
                    adv_numerator, adv_denominator = adversarial_loss_components(
                        adv_logits, mass_bins[index][batch_background], adv_weights
                    )
                    adv_loss = adv_numerator / adv_denominator
                    adv_num += float(adv_numerator.item())
                    adv_den += float(adv_denominator.item())
            (cls_loss + adv_loss).backward()
            optimizer.step()
        cls_epoch = cls_num / cls_den
        adv_epoch = adv_num / adv_den if adv_den > 0 else 0.0
        if not np.isfinite(cls_epoch) or not np.isfinite(adv_epoch):
            raise RuntimeError("non-finite final-fit metric")
        metrics.append(
            {
                "epoch": epoch,
                "lambda_effective": effective,
                "train_cls_loss": cls_epoch,
                "train_adv_loss": adv_epoch,
                "train_total_loss": cls_epoch + adv_epoch,
            }
        )
    environment = _environment()
    payload = {
        "schema_version": "adversarial-mlp-final-v1",
        "protocol_sha256": protocol.sha256,
        "feature_tuple": FEATURE_COLUMNS,
        "scaler": scaler.to_dict(),
        "target_lambda": float(target_lambda),
        "seed": seed,
        "epochs": epochs,
        "classifier_state_dict": _state(model.classifier),
        "adversary_state_dict": _state(model.adversary),
        "environment": environment,
    }
    return FinalTrainingResult(payload, tuple(metrics), scaler, environment)
