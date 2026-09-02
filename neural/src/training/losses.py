from __future__ import annotations

import torch
from torch import Tensor
from torch.nn import functional as F

from src.config import InputBindingError


def _weights(weights: Tensor, *, name: str) -> Tensor:
    if weights.ndim != 1 or not torch.isfinite(weights).all() or torch.any(weights < 0):
        raise InputBindingError(f"{name} must be finite non-negative vector")
    return weights


def binary_loss_components(logits: Tensor, labels: Tensor, weights: Tensor) -> tuple[Tensor, Tensor]:
    weights = _weights(weights, name="train_weight")
    if logits.shape != labels.shape or logits.shape != weights.shape:
        raise InputBindingError("classification loss shape mismatch")
    denominator = weights.sum()
    if denominator.item() <= 0:
        raise InputBindingError("classification batch weight sum must be positive")
    losses = F.binary_cross_entropy_with_logits(logits, labels.to(logits.dtype), reduction="none")
    return (losses * weights).sum(), denominator


def weighted_binary_cross_entropy(logits: Tensor, labels: Tensor, weights: Tensor) -> Tensor:
    numerator, denominator = binary_loss_components(logits, labels, weights)
    return numerator / denominator


def mass_bin_indices(masses: Tensor) -> Tensor:
    if masses.ndim != 1 or not torch.isfinite(masses).all():
        raise InputBindingError("m4l must be a finite vector")
    if torch.any(masses < 105.0) or torch.any(masses > 160.0):
        raise InputBindingError("m4l outside sealed adversary range")
    return torch.floor((masses - 105.0) / 5.0).to(torch.int64).clamp(max=10)


def adversarial_bin_weights(bins: Tensor, physical_weights: Tensor) -> Tensor:
    if bins.ndim != 1 or physical_weights.shape != bins.shape:
        raise InputBindingError("adversarial weight shape mismatch")
    if not torch.isfinite(physical_weights).all():
        raise InputBindingError("physical_weight must be finite")
    absolute = physical_weights.abs().to(torch.float32)
    output = torch.zeros_like(absolute)
    for index in range(11):
        mask = bins == index
        if not torch.any(mask):
            raise InputBindingError(f"mass bin {index} is empty")
        denominator = absolute[mask].sum()
        if denominator.item() <= 0:
            raise InputBindingError(f"mass bin {index} absolute-weight sum must be positive")
        output[mask] = absolute[mask] / denominator
    return output


def adversarial_loss_components(logits: Tensor, bins: Tensor, weights: Tensor) -> tuple[Tensor, Tensor]:
    weights = _weights(weights, name="adversarial weight")
    if logits.ndim != 2 or logits.shape[1] != 11 or logits.shape[0] != bins.shape[0] or bins.shape != weights.shape:
        raise InputBindingError("adversarial loss shape mismatch")
    denominator = weights.sum()
    if denominator.item() <= 0:
        raise InputBindingError("adversarial batch weight sum must be positive")
    losses = F.cross_entropy(logits, bins, reduction="none")
    return (losses * weights).sum(), denominator


def weighted_adversarial_cross_entropy(logits: Tensor, bins: Tensor, weights: Tensor) -> Tensor:
    numerator, denominator = adversarial_loss_components(logits, bins, weights)
    return numerator / denominator
