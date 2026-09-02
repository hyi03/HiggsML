"""Temporary M1-02 alias; authoritative code is domain.pairing. Delete in M1-05."""

import sys

from .domain import pairing as _implementation

sys.modules[__name__] = _implementation
