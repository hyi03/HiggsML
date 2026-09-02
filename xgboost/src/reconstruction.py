"""Temporary M1-02 alias; authoritative code is domain.reconstruction. Delete in M1-05."""

import sys

from .domain import reconstruction as _implementation

sys.modules[__name__] = _implementation
