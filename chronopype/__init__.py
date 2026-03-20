"""Chronopype - A flexible clock implementation for real-time and backtesting scenarios."""

from importlib.metadata import PackageNotFoundError, version

from chronopype.clocks.base import (
    ClockStartEvent,
    ClockStopEvent,
    ClockTickEvent,
    ProcessorStats,
)
from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.exceptions import (
    ClockContextError,
    ClockError,
    ProcessorError,
    ProcessorTimeoutError,
)
from chronopype.time import Time, TimestampFormat

try:
    __version__ = version("chronopype")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "__version__",
    "ClockConfig",
    "ClockMode",
    "ClockError",
    "ClockContextError",
    "ClockStartEvent",
    "ClockTickEvent",
    "ClockStopEvent",
    "ProcessorError",
    "ProcessorTimeoutError",
    "ProcessorStats",
    "Time",
    "TimestampFormat",
]
