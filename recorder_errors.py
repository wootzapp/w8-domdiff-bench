"""Shared exceptions for the browser task recorder."""


class RunnerError(RuntimeError):
    """Raised when a task-recording operation cannot safely continue."""

