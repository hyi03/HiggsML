"""Temporary M1-02 alias; authoritative code is domain.split. Delete in M1-05."""

import sys

from .domain import split as _implementation

sys.modules[__name__] = _implementation
