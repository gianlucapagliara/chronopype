"""Tests for uncovered lines in processors/base.py, models.py, and network.py."""

import asyncio
import logging
import time

import pytest

from chronopype.processors.base import TickProcessor
from chronopype.processors.models import ProcessorState
from chronopype.processors.network import NetworkProcessor, NetworkStatus


class MockNetworkProcessor(NetworkProcessor):
    _logger = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._logger is None:
            cls._logger = logging.getLogger("MockNetworkProcessor")
        return cls._logger

    async def check_network(self) -> NetworkStatus:
        return NetworkStatus.CONNECTED


# --- base.py coverage ---


# Line 21: current_timestamp when last_timestamp is None
def test_current_timestamp_default() -> None:
    proc = TickProcessor()
    assert proc.current_timestamp == 0


# Line 44: tick() base method does nothing
def test_tick_base_does_nothing() -> None:
    proc = TickProcessor()
    proc.tick(1.0)  # Should not raise


# Line 52: async_tick default calls tick()
async def test_async_tick_calls_tick() -> None:
    proc = TickProcessor()
    # Patch tick to verify it gets called
    called_with: list[float] = []
    original_tick = proc.tick

    def recording_tick(ts: float) -> None:
        called_with.append(ts)
        original_tick(ts)

    proc.tick = recording_tick  # type: ignore[assignment]
    await proc.async_tick(42.0)
    assert called_with == [42.0]


# --- models.py coverage ---


# Line 123: window overflow in update_execution_time
def test_update_execution_time_window_overflow() -> None:
    window_size = 3
    state = ProcessorState(execution_times=[1.0, 2.0, 3.0])
    # len == window_size, so it should trim
    new_state = state.update_execution_time(4.0, window_size)
    # Should keep last (window_size - 1) = 2 items, then append
    assert new_state.execution_times == [2.0, 3.0, 4.0]


def test_update_execution_time_window_overflow_larger() -> None:
    window_size = 2
    state = ProcessorState(execution_times=[1.0, 2.0, 3.0])
    new_state = state.update_execution_time(4.0, window_size)
    # Should keep last 1 item, then append
    assert new_state.execution_times == [3.0, 4.0]


# --- network.py coverage ---


# Line 38: base logger() raises NotImplementedError
def test_base_logger_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        NetworkProcessor.logger()


# Line 46: last_connected_timestamp property
def test_last_connected_timestamp_property() -> None:
    proc = MockNetworkProcessor()
    import math

    assert math.isnan(proc.last_connected_timestamp)


# Line 54: check_network_interval setter with value < 0.1
def test_check_network_interval_clamped() -> None:
    proc = MockNetworkProcessor()
    proc.check_network_interval = 0.01
    assert proc.check_network_interval == 0.1


# Line 70: network_error_wait_time setter with value < 0.1
def test_network_error_wait_time_clamped() -> None:
    proc = MockNetworkProcessor()
    proc.network_error_wait_time = 0.001
    assert proc.network_error_wait_time == 0.1


# Lines 140-143: disconnection transition
async def test_disconnection_transition() -> None:
    proc = MockNetworkProcessor()
    stop_called = False

    async def mock_stop_network() -> None:
        nonlocal stop_called
        stop_called = True

    proc.stop_network = mock_stop_network  # type: ignore[assignment]

    # Simulate transition from CONNECTED to NOT_CONNECTED
    proc._network_status = NetworkStatus.CONNECTED
    await proc._handle_status_transition(
        NetworkStatus.NOT_CONNECTED, NetworkStatus.CONNECTED
    )
    assert stop_called
    assert proc._network_status == NetworkStatus.NOT_CONNECTED


# Lines 196-197: _safe_stop_network exception handling
async def test_safe_stop_network_exception() -> None:
    proc = MockNetworkProcessor()

    async def failing_stop() -> None:
        raise RuntimeError("stop failed")

    proc.stop_network = failing_stop  # type: ignore[assignment]
    # Should not raise
    await proc._safe_stop_network()


# Lines 207-213: await_cleanup normal case
async def test_await_cleanup_normal() -> None:
    proc = MockNetworkProcessor()
    proc.start(time.time())
    await asyncio.sleep(0.05)
    proc.stop()
    await proc.await_cleanup(timeout=2.0)
    assert proc._stop_network_task is None


# Lines 207-213: await_cleanup timeout case
async def test_await_cleanup_timeout() -> None:
    proc = MockNetworkProcessor()

    async def slow_stop() -> None:
        await asyncio.sleep(10.0)

    # Manually set the stop task to a slow operation
    proc._stop_network_task = asyncio.create_task(slow_stop())
    await proc.await_cleanup(timeout=0.05)
    assert proc._stop_network_task is None


# Lines 207-213: await_cleanup when no task
async def test_await_cleanup_no_task() -> None:
    proc = MockNetworkProcessor()
    # Should be a no-op
    await proc.await_cleanup()


# Line 217: tick() pass method
def test_network_processor_tick_pass() -> None:
    proc = MockNetworkProcessor()
    proc.tick(1.0)  # Should not raise


# Line 228: on_disconnected logger call
def test_on_disconnected_logs(caplog: pytest.LogCaptureFixture) -> None:
    proc = MockNetworkProcessor()
    proc._network_status = NetworkStatus.DISCONNECTING
    with caplog.at_level(logging.INFO, logger="MockNetworkProcessor"):
        proc.on_disconnected()
    assert "Stopping networking" in caplog.text


# async_tick delegates to super without double-tracking
async def test_async_tick_propagates_errors() -> None:
    """async_tick should propagate errors without recording them (clock handles that)."""
    proc = MockNetworkProcessor()

    def failing_tick(ts: float) -> None:
        raise ValueError("tick error")

    proc.tick = failing_tick  # type: ignore[assignment]

    with pytest.raises(ValueError, match="tick error"):
        await proc.async_tick(1.0)

    # Error is NOT recorded by the processor — the clock is responsible for that
    assert proc.state.error_count == 0


# --- base.py pause/resume ---


def test_tick_processor_pause_noop() -> None:
    """Base TickProcessor.pause() is a no-op."""
    proc = TickProcessor()
    proc.pause()  # Should not raise


def test_tick_processor_resume_noop() -> None:
    """Base TickProcessor.resume() is a no-op."""
    proc = TickProcessor()
    proc.resume()  # Should not raise


# --- network.py pause/resume ---


async def test_network_processor_pause_cancels_loop() -> None:
    """pause() should cancel the background network check loop."""
    proc = MockNetworkProcessor()
    proc.start(time.time())
    await asyncio.sleep(0.01)

    assert proc._check_network_task is not None
    proc.pause()
    assert proc._check_network_task is None


async def test_network_processor_resume_restarts_loop() -> None:
    """resume() should restart the background network check loop."""
    proc = MockNetworkProcessor()
    proc.start(time.time())
    await asyncio.sleep(0.01)

    proc.pause()
    assert proc._check_network_task is None

    # resume() only restarts if is_active — set it
    proc._state = proc._state.model_copy(update={"is_active": True})
    proc.resume()
    assert proc._check_network_task is not None

    # Cleanup
    proc.stop()
    await proc.await_cleanup(timeout=1.0)


async def test_network_processor_resume_noop_when_inactive() -> None:
    """resume() should not restart loop if processor is inactive."""
    proc = MockNetworkProcessor()
    proc.start(time.time())
    await asyncio.sleep(0.01)

    proc.pause()
    # state.is_active is False (from stop behavior), so resume should be a no-op
    proc._state = proc._state.model_copy(update={"is_active": False})
    proc.resume()
    assert proc._check_network_task is None
