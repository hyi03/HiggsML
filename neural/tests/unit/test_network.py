from __future__ import annotations

import torch
from torch import nn

from src.training.network import AdversarialMLP, gradient_reverse


def test_network_shapes_and_exact_parameter_counts() -> None:
    model = AdversarialMLP()
    features = torch.zeros((7, 15), dtype=torch.float32)
    logits = model.classifier(features)
    adversary = model.adversary(logits[:4], lambda_effective=0.2)

    assert logits.shape == (7,)
    assert adversary.shape == (4, 11)
    assert sum(parameter.numel() for parameter in model.classifier.parameters()) == 7617
    assert sum(parameter.numel() for parameter in model.adversary.parameters()) == 1611
    assert sum(parameter.numel() for parameter in model.parameters()) == 9228


def test_gradient_reversal_is_identity_and_scales_negative_gradient() -> None:
    values = torch.tensor([1.0, -2.0], requires_grad=True)
    output = gradient_reverse(values, 0.25)
    assert torch.equal(output, values)

    output.sum().backward()
    assert torch.equal(values.grad, torch.tensor([-0.25, -0.25]))


def test_network_module_order_dropout_and_layer_norm_are_exact() -> None:
    model = AdversarialMLP()
    assert [type(module) for module in model.classifier.layers] == [
        nn.Linear,
        nn.LayerNorm,
        nn.SiLU,
        nn.Dropout,
        nn.Linear,
        nn.LayerNorm,
        nn.SiLU,
        nn.Dropout,
        nn.Linear,
        nn.LayerNorm,
        nn.SiLU,
        nn.Linear,
    ]
    assert [type(module) for module in model.adversary.layers] == [
        nn.Linear,
        nn.LayerNorm,
        nn.SiLU,
        nn.Linear,
        nn.LayerNorm,
        nn.SiLU,
        nn.Linear,
    ]
    dropouts = [module for module in model.classifier.layers if isinstance(module, nn.Dropout)]
    layer_norms = [
        module
        for module in (*model.classifier.layers, *model.adversary.layers)
        if isinstance(module, nn.LayerNorm)
    ]
    assert [module.p for module in dropouts] == [0.10, 0.10]
    assert all(module.eps == 1.0e-5 for module in layer_norms)
    assert all(module.elementwise_affine for module in layer_norms)
    assert all(layer.bias is not None for layer in model.modules() if isinstance(layer, nn.Linear))
    assert all(parameter.device.type == "cpu" and parameter.dtype == torch.float32 for parameter in model.parameters())


def test_composed_adversary_gradient_reverses_classifier_logit_gradient() -> None:
    model = AdversarialMLP().eval()
    direct_logits = torch.tensor([-0.5, 0.25, 1.0], requires_grad=True)
    model.adversary.layers(direct_logits.unsqueeze(1))[:, 0].sum().backward()
    direct_gradient = direct_logits.grad.detach().clone()

    reversed_logits = direct_logits.detach().clone().requires_grad_(True)
    model.adversary(reversed_logits, lambda_effective=0.5)[:, 0].sum().backward()

    assert torch.count_nonzero(direct_gradient).item() > 0
    assert torch.allclose(reversed_logits.grad, -0.5 * direct_gradient, rtol=0.0, atol=1e-7)
