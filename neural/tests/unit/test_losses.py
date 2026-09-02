from __future__ import annotations

import pytest
import torch
from torch import nn

from src.config import InputBindingError
from src.training.losses import (
    adversarial_loss_components,
    adversarial_bin_weights,
    binary_loss_components,
    mass_bin_indices,
    weighted_adversarial_cross_entropy,
    weighted_binary_cross_entropy,
)
from src.training.network import AdversarialMLP


def test_weighted_losses_match_hand_computation() -> None:
    logits = torch.tensor([0.2, -0.4])
    labels = torch.tensor([1, 0])
    weights = torch.tensor([1.0, 3.0])
    expected_bce = (
        nn.functional.binary_cross_entropy_with_logits(logits, labels.float(), reduction="none")
        * weights
    ).sum() / weights.sum()
    assert torch.equal(weighted_binary_cross_entropy(logits, labels, weights), expected_bce)

    adv_logits = torch.zeros((2, 11))
    bins = torch.tensor([0, 10])
    adv_weights = torch.tensor([0.25, 0.75])
    expected_ce = (
        nn.functional.cross_entropy(adv_logits, bins, reduction="none") * adv_weights
    ).sum() / adv_weights.sum()
    assert torch.equal(weighted_adversarial_cross_entropy(adv_logits, bins, adv_weights), expected_ce)


def test_mass_bins_and_fold_weights_are_exactly_balanced() -> None:
    masses = torch.tensor([105.0, 109.999, 110.0, 159.999, 160.0], dtype=torch.float64)
    assert mass_bin_indices(masses).tolist() == [0, 0, 1, 10, 10]

    all_masses = torch.tensor([107.5 + 5.0 * index for index in range(11)] * 2)
    physical = torch.tensor([-2.0] * 11 + [1.0] * 11)
    bins = mass_bin_indices(all_masses)
    weights = adversarial_bin_weights(bins, physical)
    totals = torch.zeros(11).scatter_add_(0, bins, weights)
    assert torch.allclose(totals, torch.ones(11), rtol=0.0, atol=1e-7)


def test_every_mass_edge_and_invalid_mass_failures_are_bound() -> None:
    edges = torch.arange(105.0, 165.0, 5.0, dtype=torch.float64)
    expected = list(range(11)) + [10]
    assert mass_bin_indices(edges).tolist() == expected

    for invalid in (
        torch.tensor([104.999], dtype=torch.float64),
        torch.tensor([160.001], dtype=torch.float64),
        torch.tensor([float("nan")], dtype=torch.float64),
        torch.tensor([float("inf")], dtype=torch.float64),
    ):
        with pytest.raises(InputBindingError):
            mass_bin_indices(invalid)


def test_adversarial_bin_weight_rejects_empty_and_zero_sum_bins() -> None:
    bins = torch.arange(11)
    with pytest.raises(InputBindingError, match="absolute-weight sum"):
        adversarial_bin_weights(bins, torch.zeros(11))

    with pytest.raises(InputBindingError, match="mass bin"):
        adversarial_bin_weights(bins[:-1], torch.ones(10))


def test_loss_components_preserve_raw_numerator_and_denominator() -> None:
    logits = torch.tensor([0.2, -0.4])
    labels = torch.tensor([1, 0])
    weights = torch.tensor([1.0, 3.0])
    binary_numerator, binary_denominator = binary_loss_components(logits, labels, weights)
    assert torch.equal(binary_numerator / binary_denominator, weighted_binary_cross_entropy(logits, labels, weights))
    assert binary_denominator.item() == 4.0

    adv_logits = torch.zeros((2, 11))
    bins = torch.tensor([0, 10])
    adv_weights = torch.tensor([0.25, 0.75])
    adv_numerator, adv_denominator = adversarial_loss_components(adv_logits, bins, adv_weights)
    assert torch.equal(adv_numerator / adv_denominator, weighted_adversarial_cross_entropy(adv_logits, bins, adv_weights))
    assert adv_denominator.item() == 1.0


def test_zero_effective_background_batch_does_not_update_adversary() -> None:
    model = AdversarialMLP()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    before = {name: value.detach().clone() for name, value in model.adversary.state_dict().items()}
    features = torch.ones((3, 15))
    labels = torch.ones(3, dtype=torch.int64)
    weights = torch.ones(3)

    optimizer.zero_grad(set_to_none=True)
    logits = model.classifier(features)
    loss = weighted_binary_cross_entropy(logits, labels, weights) + 0.0 * logits.sum()
    loss.backward()
    assert all(parameter.grad is None for parameter in model.adversary.parameters())
    optimizer.step()

    assert all(torch.equal(before[name], value) for name, value in model.adversary.state_dict().items())
