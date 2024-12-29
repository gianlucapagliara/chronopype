import asyncio
import time
from collections.abc import Callable

import pytest

from chronopype.clocks.backtest import BacktestClock
from chronopype.clocks.modes import ClockMode
from chronopype.clocks.realtime import RealtimeClock
from chronopype.models import ClockConfig
from chronopype.processors.base import TickProcessor


class MockProcessor(TickProcessor):
    """A mock processor for testing."""

    def __init__(self, name: str = "mock") -> None:
        super().__init__()

        self._name = name
        self.start_called = False
        self.stop_called = False
        self.tick_count = 0
        self.should_raise = False
        self.sleep_time = 0.0
        self.last_timestamp: float | None = None

    def start(self, timestamp: float) -> None:
        self.start_called = True
        self.last_timestamp = timestamp
        super().start(timestamp)

    def stop(self) -> None:
        self.stop_called = True
        super().stop()

    def tick(self, timestamp: float) -> None:
        if self.should_raise:
            raise ValueError("Test error")
        if self.sleep_time > 0:
            # Simulate slow processing
            time.sleep(self.sleep_time)
        self.tick_count += 1
        self.last_timestamp = timestamp

    async def async_tick(self, timestamp: float) -> None:
        if self.should_raise:
            raise ValueError("Test error")
        if self.sleep_time > 0:
            await asyncio.sleep(self.sleep_time)
        self.tick_count += 1
        self.last_timestamp = timestamp

    def __str__(self) -> str:
        return f"MockProcessor({self._name})"


@pytest.fixture
def mock_processor() -> MockProcessor:
    """Create a mock processor for testing."""
    return MockProcessor()


@pytest.fixture
def clock_config() -> ClockConfig:
    """Create a basic clock configuration for testing."""
    return ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        tick_size=1.0,
        start_time=1000.0,
        end_time=1010.0,
        processor_timeout=0.5,
        max_retries=2,
        stats_window_size=10,
    )


@pytest.fixture
def realtime_config() -> ClockConfig:
    """Create a realtime clock configuration for testing."""
    return ClockConfig(
        clock_mode=ClockMode.REALTIME,
        tick_size=0.1,
        processor_timeout=1.0,
        max_retries=2,
        stats_window_size=10,
    )


@pytest.fixture
def clock(clock_config: ClockConfig) -> BacktestClock:
    """Create a clock instance for testing."""
    return BacktestClock(clock_config)


@pytest.fixture
def realtime_clock(realtime_config: ClockConfig) -> RealtimeClock:
    """Create a realtime clock instance for testing."""
    return RealtimeClock(realtime_config)


@pytest.fixture
def error_list() -> list[tuple[TickProcessor, Exception]]:
    """Create a list to collect error callbacks."""
    return []


@pytest.fixture
def error_callback(
    error_list: list[tuple[TickProcessor, Exception]]
) -> Callable[[TickProcessor, Exception], None]:
    """Create an error callback that collects errors in a list."""

    def callback(processor: TickProcessor, error: Exception) -> None:
        error_list.append((processor, error))

    return callback


@pytest.fixture
def failing_processor() -> MockProcessor:
    """Create a processor that fails with configurable behavior."""
    processor = MockProcessor("failing")
    processor.should_raise = True
    return processor


@pytest.fixture
def slow_processor() -> MockProcessor:
    """Create a processor that simulates slow processing."""
    processor = MockProcessor("slow")
    processor.sleep_time = 0.2
    return processor
