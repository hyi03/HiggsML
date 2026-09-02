"""Temporary M1-02 alias; authoritative code is domain.angular5. Delete in M1-05."""

import sys

from .domain import angular5 as _implementation

sys.modules[__name__] = _implementation
