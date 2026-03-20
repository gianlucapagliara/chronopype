"""Tests for uncovered lines in chronopype/clocks/realtime.py."""

import asyncio
import logging
import time
from unittest.mock import AsyncMock, patch

import pytest

from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.clocks.realtime import RealtimeClock
from chronopype.exceptions import ClockError
from tests.conftest import MockProcessor


@pytest.fixture
def realtime_config() -> ClockConfig:
    return ClockConfig(
        clock_mode=ClockMode.REALTIME,
        tick_size=0.1,
        processor_timeout=1.0,
        max_retries=2,
        stats_window_size=10,
    )


@pytest.fixture
def realtime_clock(realtime_config: ClockConfig) -> RealtimeClock:
    return RealtimeClock(realtime_config)


# Line 29: init with wrong mode
def test_init_wrong_mode() -> None:
    config = ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        tick_size=1.0,
        start_time=1000.0,
        end_time=1010.0,
    )
    with pytest.raises(ClockError, match="RealtimeClock requires REALTIME mode"):
        RealtimeClock(config)


# Lines 34-42: run() with CancelledError handling
async def test_run_cancelled(realtime_clock: RealtimeClock) -> None:
    processor = MockProcessor()
    realtime_clock.add_processor(processor)

    async with realtime_clock:
        task = asyncio.create_task(realtime_clock.run())
        await asyncio.sleep(0.15)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    # After cancellation, clock should be cleaned up
    assert realtime_clock._task is None


# Line 47: run_til when _task is not None
async def test_run_til_already_running(realtime_clock: RealtimeClock) -> None:
    processor = MockProcessor()
    realtime_clock.add_processor(processor)

    async with realtime_clock:
        # Start run_til in background
        target = time.time() + 5.0
        task = asyncio.create_task(realtime_clock.run_til(target))
        await asyncio.sleep(0.05)

        # Try to run_til again while already running
        with pytest.raises(ClockError, match="Clock is already running"):
            await realtime_clock.run_til(target)

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


# Line 78: _run_til_impl when not running
async def test_run_til_impl_not_running(realtime_clock: RealtimeClock) -> None:
    # _running is False by default
    with pytest.raises(ClockError, match="Clock must be started"):
        await realtime_clock._run_til_impl(time.time() + 1.0, [])


# Lines 96-97: CancelledError in _wait_next_tick
async def test_wait_next_tick_cancelled() -> None:
    # Use a long tick_size so the sleep is long enough to cancel
    config = ClockConfig(
        clock_mode=ClockMode.REALTIME,
        tick_size=10.0,
        processor_timeout=1.0,
    )
    clock = RealtimeClock(config)

    async def cancel_during_wait() -> None:
        await asyncio.sleep(0.01)
        task.cancel()

    clock._running = True
    clock._started = True
    task = asyncio.create_task(clock._wait_next_tick())
    asyncio.create_task(cancel_during_wait())

    with pytest.raises(asyncio.CancelledError):
        await task


# Line 104: drift logging (ticks_passed > 0)
async def test_drift_logging(realtime_clock: RealtimeClock) -> None:
    import chronopype.clocks.realtime as rt_module

    tick_size = realtime_clock._config.tick_size
    base_time = time.time()
    aligned = (base_time // tick_size + 1) * tick_size

    call_count = 0
    real_time = time.time

    def mock_time() -> float:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # current_time (line 87)
            return aligned - 0.01
        elif call_count == 2:
            # actual_time (line 100) - simulate big drift
            return aligned + tick_size * 3.5
        return real_time()

    mock_time_mod = type(time)("mock_time")
    mock_time_mod.time = mock_time  # type: ignore[attr-defined]

    original_time = rt_module.time
    original_logger = rt_module.logger
    mock_logger = type("MockLogger", (), {"debug": staticmethod(lambda *a, **kw: None)})()
    debug_calls: list[tuple] = []

    def capture_debug(*args: object, **kwargs: object) -> None:
        debug_calls.append(args)

    mock_logger.debug = capture_debug  # type: ignore[attr-defined]

    rt_module.time = mock_time_mod  # type: ignore[assignment]
    rt_module.logger = mock_logger  # type: ignore[assignment]
    try:
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await realtime_clock._wait_next_tick()
    finally:
        rt_module.time = original_time
        rt_module.logger = original_logger

    assert len(debug_calls) == 1
    assert "Clock drift detected" in debug_calls[0][0]
    assert "skipped" in debug_calls[0][0]
