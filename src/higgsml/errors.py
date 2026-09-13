"""Explicit research binding and scientific terminal states."""


class ResearchError(ValueError):
    exit_code = 3

    def __init__(self, message: str, *, status: str = "input_binding_failure"):
        super().__init__(message)
        self.status = status


class ResearchStateError(ResearchError):
    """A declared scientific terminal state, rather than an internal crash."""

    exit_code = 0
