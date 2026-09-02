"""Temporary M1-02 alias; authoritative code is domain.weights. Delete in M1-05."""

import sys

from .domain import weights as _implementation

sys.modules[__name__] = _implementation
