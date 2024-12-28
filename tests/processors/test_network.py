import asyncio
import logging
import time

import pytest

from flowtime.processors.network import NetworkProcessor, NetworkStatus


class MockNetworkProcessor(NetworkProcessor):
    """A mock network processor for testing."""

    _logger = None  # Match the base class definition

    def __init__(self, stats_window_size: int = 100) -> None:
        super().__init__(stats_window_size=stats_window_size)
        self._check_network_calls = 0
        self._should_fail = False
        self._should_timeout = False

    @property
    def check_network_calls(self) -> int:
        return self._check_network_calls

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._logger is None:
            cls._logger = logging.getLogger("MockNetworkProcessor")
        return cls._logger

    async def check_network(self) -> NetworkStatus:
        self._check_network_calls += 1
        if self._should_fail:
            self._network_status = NetworkStatus.ERROR
            raise RuntimeError("Test error")
        if self._should_timeout:
            # Set status to NOT_CONNECTED before timing out
            self._network_status = NetworkStatus.NOT_CONNECTED
            await asyncio.sleep(10)  # Force timeout
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED


@pytest.fixture
def network_processor() -> MockNetworkProcessor:
    return MockNetworkProcessor()


@pytest.mark.asyncio
async def test_network_processor_initialization(
    network_processor: MockNetworkProcessor,
) -> None:
    """Test network processor initialization."""
    status = network_processor.network_status
    assert isinstance(status, NetworkStatus)
    assert status.value == NetworkStatus.STOPPED.value
    assert network_processor.check_network_interval == 10.0
    assert network_processor.check_network_timeout == 5.0
    assert network_processor.network_error_wait_time == 60.0


@pytest.mark.asyncio
async def test_network_processor_start_stop(
    network_processor: MockNetworkProcessor,
) -> None:
    """Test network processor start/stop."""
    network_processor.start(time.time())
    status = network_processor.network_status
    assert isinstance(status, NetworkStatus)
    assert status.value == NetworkStatus.NOT_CONNECTED.value

    # Wait for first check
    await asyncio.sleep(0.1)
    assert network_processor.check_network_calls > 0
    status = network_processor.network_status
    assert isinstance(status, NetworkStatus)
    assert status.value == NetworkStatus.CONNECTED.value

    network_processor.stop()
    status = network_processor.network_status
    assert isinstance(status, NetworkStatus)
    assert status.value == NetworkStatus.STOPPED.value


@pytest.mark.asyncio
async def test_network_processor_error_handling(
    network_processor: MockNetworkProcessor,
) -> None:
    """Test network processor error handling."""
    network_processor._should_fail = True
    network_processor.start(time.time())

    # Wait for error
    await asyncio.sleep(0.1)
    assert network_processor.check_network_calls > 0
    status = network_processor.network_status
    assert isinstance(status, NetworkStatus)
    assert status.value == NetworkStatus.ERROR.value

    # Check error state
    state = network_processor.state
    assert state.error_count > 0
    assert state.last_error is not None
    assert state.last_error == "Test error"  # Check error message instead of type

    network_processor.stop()


@pytest.mark.asyncio
async def test_network_processor_timeout(
    network_processor: MockNetworkProcessor,
) -> None:
    """Test network processor timeout handling."""
    network_processor._should_timeout = True
    network_processor.check_network_timeout = 0.1  # Set short timeout
    network_processor.start(time.time())

    # Wait for timeout and state transition
    await asyncio.sleep(0.3)  # Wait for the complete state transition
    assert network_processor.check_network_calls > 0
    status = network_processor.network_status
    assert isinstance(status, NetworkStatus)
    assert status.value == NetworkStatus.NOT_CONNECTED.value

    # Check error state
    state = network_processor.state
    assert state.error_count > 0
    assert state.last_error is not None
    assert "timed out" in state.last_error.lower()  # Check for timeout message

    network_processor.stop()


@pytest.mark.asyncio
async def test_network_processor_backoff(
    network_processor: MockNetworkProcessor,
) -> None:
    """Test network processor backoff strategy."""
    network_processor._should_fail = True
    network_processor.start(time.time())

    # Wait for multiple retries
    await asyncio.sleep(0.5)
    initial_calls = network_processor.check_network_calls

    # Wait more to see if backoff is working
    await asyncio.sleep(1)
    later_calls = network_processor.check_network_calls

    # The rate of calls should decrease due to exponential backoff
    initial_rate = initial_calls / 0.5
    later_rate = (later_calls - initial_calls) / 1.0
    assert later_rate < initial_rate

    network_processor.stop()
