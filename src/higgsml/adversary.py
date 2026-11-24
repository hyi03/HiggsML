from __future__ import annotations

import torch
from torch import Tensor, nn

from .config import InputBindingError


class _GradientReverse(torch.autograd.Function):
    @staticmethod
    def forward(ctx: object, values: Tensor, lambda_effective: float) -> Tensor:
        if not torch.isfinite(torch.tensor(lambda_effective)) or lambda_effective < 0:
            raise InputBindingError("lambda_effective must be finite and non-negative")
        ctx.lambda_effective = float(lambda_effective)
        return values.view_as(values)

    @staticmethod
    def backward(ctx: object, gradient: Tensor) -> tuple[Tensor, None]:
        return -ctx.lambda_effective * gradient, None


def gradient_reverse(values: Tensor, lambda_effective: float) -> Tensor:
    return _GradientReverse.apply(values, lambda_effective)


class Adversary(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(1, 32), nn.LayerNorm(32, eps=1.0e-5), nn.SiLU(),
            nn.Linear(32, 32), nn.LayerNorm(32, eps=1.0e-5), nn.SiLU(),
            nn.Linear(32, 11),
        )

    def forward(self, logits: Tensor, *, lambda_effective: float) -> Tensor:
        if any(parameter.device.type != "cpu" for parameter in self.parameters()):
            raise InputBindingError("adversary parameters must remain on CPU")
        if logits.ndim != 1:
            raise InputBindingError("adversary requires scalar classifier logits")
        return self.layers(gradient_reverse(logits, lambda_effective).unsqueeze(1))
