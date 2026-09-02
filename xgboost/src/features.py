"""Temporary M1-02 alias; authoritative code is domain.features. Delete in M1-05."""

import sys

from .domain import features as _implementation

sys.modules[__name__] = _implementation
