"""Chronopype - A flexible clock implementation for real-time and backtesting scenarios."""

from importlib.metadata import PackageNotFoundError, version

from chronopype.clocks.backtest import BacktestClock
from chronopype.clocks.base import (
    BaseClock,
    ClockStartEvent,
    ClockStopEvent,
    ClockTickEvent,
    ProcessorStats,
)
from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.clocks.realtime import RealtimeClock
from chronopype.exceptions import (
    ClockContextError,
    ClockError,
    ClockRuntimeError,
    ProcessorError,
    ProcessorTimeoutError,
)
from chronopype.processors.base import TickProcessor
from chronopype.processors.models import ProcessorState
from chronopype.processors.network import NetworkProcessor, NetworkStatus
from chronopype.runtime.clock_runtime import ClockRuntime
from chronopype.runtime.config import ClockRuntimeConfig
from chronopype.time import Time, TimestampFormat

try:
    __version__ = version("chronopype")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "__version__",
    # Clocks
    "BaseClock",
    "BacktestClock",
    "RealtimeClock",
    "ClockConfig",
    "ClockMode",
    # Events
    "ClockStartEvent",
    "ClockTickEvent",
    "ClockStopEvent",
    # Processors
    "TickProcessor",
    "ProcessorState",
    "ProcessorStats",
    "NetworkProcessor",
    "NetworkStatus",
    # Runtime
    "ClockRuntime",
    "ClockRuntimeConfig",
    # Exceptions
    "ClockError",
    "ClockContextError",
    "ClockRuntimeError",
    "ProcessorError",
    "ProcessorTimeoutError",
    # Time utilities
    "Time",
    "TimestampFormat",
]
