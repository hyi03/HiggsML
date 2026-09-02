"""Temporary M1-02 alias; authoritative code is preprocessing.profiles. Delete in M1-05."""

import sys

from .preprocessing import profiles as _implementation

sys.modules[__name__] = _implementation
