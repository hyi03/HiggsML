from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    USAGE = 2
    INPUT_BINDING = 3
    TRANSACTION = 4
    REFUSED = 5
    INTERNAL_ERROR = 70
