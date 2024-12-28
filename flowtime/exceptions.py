class ClockError(Exception):
    """Base exception for clock-related errors."""

    pass


class ClockContextError(ClockError):
    """Raised when clock context is misused."""

    pass


class ProcessorError(ClockError):
    """Raised when a processor encounters an error."""

    pass


class ProcessorTimeoutError(ProcessorError):
    """Raised when a processor execution times out."""

    pass
