"""Tests targeting specific uncovered lines in chronopype/clocks/base.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from chronopype.clocks.backtest import BacktestClock
from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.clocks.base import BaseClock
from chronopype.exceptions import ClockContextError, ClockError
from chronopype.processors.base import TickProcessor
from tests.conftest import MockProcessor


# ---------------------------------------------------------------------------
# Line 139: tick_counter property
# ---------------------------------------------------------------------------


async def test_tick_counter_property(clock: BacktestClock):
    """Access the tick_counter property to cover line 139."""
    assert clock.tick_counter == 0


# ---------------------------------------------------------------------------
# Line 152: get_processor_performance for unknown processor
# ---------------------------------------------------------------------------


async def test_get_processor_performance_unknown_processor(clock: BacktestClock):
    """get_processor_performance returns (0, 0, 0) for unknown processor."""
    unknown = MockProcessor("unknown")
    result = clock.get_processor_performance(unknown)
    assert result == (0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# Line 173: shutdown() early return when not running and not started
# ---------------------------------------------------------------------------


async def test_shutdown_early_return_not_running(clock: BacktestClock):
    """shutdown() returns immediately when not running and not started."""
    assert not clock._running
    assert not clock._started
    await clock.shutdown()  # Should just return


# ---------------------------------------------------------------------------
# Lines 181-185: shutdown with active task (cancel + await + exception catch)
# ---------------------------------------------------------------------------


async def test_shutdown_cancels_active_task(clock: BacktestClock):
    """shutdown() cancels and awaits an active _task."""
    clock._started = True
    clock._running = True

    # Create a real long-running task that will be cancelled
    async def long_running():
        await asyncio.sleep(100)

    clock._task = asyncio.create_task(long_running())
    await clock.shutdown()

    assert clock._task.cancelled() or clock._task.done()


async def test_shutdown_task_raises_exception(clock: BacktestClock):
    """shutdown() handles exception from awaiting cancelled task."""
    clock._started = True
    clock._running = True

    # Create a task that raises a non-CancelledError exception
    async def failing_task():
        raise RuntimeError("task error")

    task = asyncio.create_task(failing_task())
    # Let the task actually fail
    await asyncio.sleep(0)
    clock._task = task
    await clock.shutdown()  # Should not raise


# ---------------------------------------------------------------------------
# Lines 195-196: shutdown exception during processor stop
# ---------------------------------------------------------------------------


async def test_shutdown_processor_stop_raises(clock: BacktestClock):
    """shutdown() catches exceptions from processor.stop() during cleanup."""
    proc = MockProcessor("failing_stop")
    clock.add_processor(proc)

    clock._started = True
    clock._running = True
    clock._current_context = [proc]
    # Make the processor state active so the shutdown path processes it
    state = clock._processor_states[proc]
    clock._processor_states[proc] = state.model_copy(update={"is_active": True})

    # Override stop to raise
    def bad_stop():
        raise RuntimeError("stop failed")

    proc.stop = bad_stop  # type: ignore[assignment]

    await clock.shutdown()  # Should not raise


# ---------------------------------------------------------------------------
# Line 305: _execute_processor returns early when is_active=False
# ---------------------------------------------------------------------------


async def test_execute_processor_inactive(clock: BacktestClock):
    """_execute_processor returns early when processor is_active=False."""
    proc = MockProcessor("inactive")
    clock.add_processor(proc)
    # Processor state is inactive by default (clock not started)
    await clock._execute_processor(proc, 1000.0)
    assert proc.tick_count == 0


# ---------------------------------------------------------------------------
# Lines 538-546: __aenter__ processor start() failure
# ---------------------------------------------------------------------------


async def test_aenter_processor_start_failure_cleans_up(clock_config: ClockConfig):
    """When a processor fails to start in __aenter__, already-started ones get stopped."""
    clock = BacktestClock(clock_config)

    good_proc = MockProcessor("good")
    bad_proc = MockProcessor("bad_start")

    # Override bad_proc.start to raise
    original_start = bad_proc.start

    def failing_start(timestamp: float) -> None:
        raise RuntimeError("start failed")

    bad_proc.start = failing_start  # type: ignore[assignment]

    clock.add_processor(good_proc)
    clock.add_processor(bad_proc)

    with pytest.raises(ClockError, match="Failed to start processor"):
        async with clock:
            pass  # pragma: no cover

    # good_proc was started then stopped during cleanup
    assert good_proc.start_called
    assert good_proc.stop_called


# ---------------------------------------------------------------------------
# Lines 549-551: __aenter__ generic except clause (cleanup on unexpected error)
# ---------------------------------------------------------------------------


async def test_aenter_generic_exception_cleanup(clock_config: ClockConfig):
    """The bare except in __aenter__ calls _cleanup on unexpected errors.

    The ClockError raised by the processor start failure path already goes
    through the bare except (lines 549-551) after _cleanup is called in
    the inner except. This test verifies cleanup happens via ClockError
    which re-raises through the bare except clause.
    """
    clock = BacktestClock(clock_config)
    proc = MockProcessor("bad")

    def failing_start(timestamp: float) -> None:
        raise RuntimeError("unexpected")

    proc.start = failing_start  # type: ignore[assignment]
    clock.add_processor(proc)

    with pytest.raises(ClockError):
        async with clock:
            pass  # pragma: no cover

    # After cleanup, state should be reset
    assert clock._current_context is None
    assert not clock._started
    assert not clock._running


# ---------------------------------------------------------------------------
# Line 561: __aexit__ when _current_context is None
# ---------------------------------------------------------------------------


async def test_aexit_not_in_context(clock: BacktestClock):
    """__aexit__ raises ClockContextError when _current_context is None."""
    assert clock._current_context is None
    with pytest.raises(ClockContextError, match="Clock is not in a context"):
        await clock.__aexit__(None, None, None)


# ---------------------------------------------------------------------------
# Lines 567-569: __aexit__ exception during shutdown
# ---------------------------------------------------------------------------


async def test_aexit_shutdown_raises(clock_config: ClockConfig):
    """__aexit__ propagates exception from shutdown and sets error_occurred."""
    clock = BacktestClock(clock_config)
    proc = MockProcessor("ok")
    clock.add_processor(proc)

    # Manually set up state as if we're in a context
    clock._current_context = [proc]
    clock._started = True
    clock._running = False

    # Start the processor so stop() works
    proc.start(1000.0)
    state = clock._processor_states[proc]
    clock._processor_states[proc] = state.model_copy(update={"is_active": True})

    # Patch shutdown to raise
    async def bad_shutdown(timeout=None):
        raise RuntimeError("shutdown boom")

    clock.shutdown = bad_shutdown  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="shutdown boom"):
        await clock.__aexit__(None, None, None)

    # Cleanup should still have happened
    assert clock._current_context is None


# ---------------------------------------------------------------------------
# Lines 585-586: __aexit__ processor.stop() raises exception
# ---------------------------------------------------------------------------


async def test_aexit_processor_stop_raises(clock_config: ClockConfig):
    """__aexit__ catches processor.stop() exceptions and sets error_occurred."""
    clock = BacktestClock(clock_config)
    proc = MockProcessor("bad_stop")
    clock.add_processor(proc)

    # Enter context normally
    await clock.__aenter__()

    # Now make stop() raise
    def bad_stop():
        raise RuntimeError("stop error")

    proc.stop = bad_stop  # type: ignore[assignment]

    # Exit with an exception so shutdown is skipped (avoid double-stop issues)
    await clock.__aexit__(RuntimeError, RuntimeError("test"), None)

    # Cleanup should still have run
    assert clock._current_context is None


# ---------------------------------------------------------------------------
# Lines 591-594: __aexit__ await_cleanup for processors with that method
# ---------------------------------------------------------------------------


class CleanupProcessor(MockProcessor):
    """A processor that has an await_cleanup method."""

    def __init__(self, name: str = "cleanup_proc"):
        super().__init__(name)
        self.cleanup_called = False

    async def await_cleanup(self) -> None:
        self.cleanup_called = True


async def test_aexit_await_cleanup(clock_config: ClockConfig):
    """__aexit__ calls await_cleanup on processors that have it."""
    clock = BacktestClock(clock_config)
    proc = CleanupProcessor("with_cleanup")
    clock.add_processor(proc)

    async with clock:
        pass  # Just enter and exit

    assert proc.cleanup_called


async def test_aexit_await_cleanup_exception_suppressed(clock_config: ClockConfig):
    """__aexit__ suppresses exceptions from await_cleanup."""
    clock = BacktestClock(clock_config)

    class FailingCleanupProcessor(MockProcessor):
        async def await_cleanup(self) -> None:
            raise RuntimeError("cleanup failed")

    proc = FailingCleanupProcessor("failing_cleanup")
    clock.add_processor(proc)

    async with clock:
        pass  # Should not raise despite await_cleanup failure


# ---------------------------------------------------------------------------
# Line 602: get_processor_stats for unknown processor returns {}
# ---------------------------------------------------------------------------


async def test_get_processor_stats_unknown_processor(clock: BacktestClock):
    """get_processor_stats returns {} for an unregistered processor."""
    unknown = MockProcessor("unknown")
    result = clock.get_processor_stats(unknown)
    assert result == {}
