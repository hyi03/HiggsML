"""Temporary M1-02 alias; authoritative code is domain.selection. Delete in M1-05."""

import sys

from .domain import selection as _implementation

sys.modules[__name__] = _implementation
