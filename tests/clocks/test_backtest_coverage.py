"""Tests targeting specific uncovered lines in chronopype/clocks/backtest.py."""

import asyncio

import pytest
from pydantic import ValidationError

from chronopype.clocks.backtest import BacktestClock
from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.exceptions import ClockError
from tests.conftest import MockProcessor

# --- Line 28: init with wrong mode ---


def test_init_wrong_mode():
    config = ClockConfig(
        clock_mode=ClockMode.REALTIME,
        tick_size=1.0,
    )
    with pytest.raises(ClockError, match="BacktestClock requires BACKTEST mode"):
        BacktestClock(config)


# --- Line 30: init with end_time=0 ---


def test_init_end_time_zero():
    config = ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        tick_size=1.0,
        start_time=0.0,
        end_time=0.0,
    )
    with pytest.raises(ClockError, match="end_time must be set for backtest mode"):
        BacktestClock(config)


# --- Line 35: the run() method ---


async def test_run_delegates_to_run_til(clock_config: ClockConfig):
    clock = BacktestClock(clock_config)
    processor = MockProcessor("run_test")
    clock.add_processor(processor)

    async with clock:
        await clock.run()

    # run() should have ticked from start_time to end_time
    assert processor.tick_count == 10  # 1010 - 1000 = 10 ticks at tick_size=1.0


# --- Line 40: run_til when task is not None ---


async def test_run_til_already_running(clock_config: ClockConfig):
    clock = BacktestClock(clock_config)
    processor = MockProcessor("already_running")
    processor.sleep_time = 0.5
    clock.add_processor(processor)

    async with clock:
        # Start a long-running run_til in a task
        task = asyncio.create_task(clock.run_til(clock_config.end_time))
        # Give it a moment to start
        await asyncio.sleep(0.01)

        with pytest.raises(ClockError, match="Clock is already running"):
            await clock.run_til(clock_config.end_time)

        # Clean up
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


# --- Line 43: run_til outside context ---


async def test_run_til_outside_context(clock_config: ClockConfig):
    clock = BacktestClock(clock_config)
    with pytest.raises(ClockError, match="Clock must be started in a context"):
        await clock.run_til(1005.0)


# --- Line 71: _run_til_impl not running ---


async def test_run_til_impl_not_running(clock_config: ClockConfig):
    clock = BacktestClock(clock_config)

    async with clock:
        # Directly call _run_til_impl with _running=False
        clock._running = False
        with pytest.raises(ClockError, match="Clock must be started in a context."):
            await clock._run_til_impl(1005.0, [])


# --- Line 76: num_ticks <= 0 in _run_til_impl ---


async def test_run_til_impl_zero_ticks(clock_config: ClockConfig):
    clock = BacktestClock(clock_config)

    async with clock:
        clock._running = True
        # Target time == current tick => num_ticks=0 => early return
        await clock._run_til_impl(clock._current_tick, [])
        # Should return without error


# --- Lines 95-97: floating point remainder in _run_til_impl ---


async def test_run_til_impl_float_remainder():
    config = ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        tick_size=0.3,
        start_time=0.0,
        end_time=2.0,
    )
    clock = BacktestClock(config)
    processor = MockProcessor("float_remainder")
    clock.add_processor(processor)

    async with clock:
        await clock.run_til(1.0)

    # tick_size=0.3 into 1.0: int(1.0/0.3)=3 ticks => 0.9
    # remainder 0.1 > FLOAT_EPSILON => extra tick at 1.0
    # So 3 + 1 = 4 ticks total
    assert processor.tick_count == 4
    assert clock._current_tick == 1.0


# --- Lines 171-175: step_to floating point remainder ---


async def test_step_to_float_remainder():
    config = ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        tick_size=0.3,
        start_time=0.0,
        end_time=2.0,
    )
    clock = BacktestClock(config)
    processor = MockProcessor("step_to_float")
    clock.add_processor(processor)

    async with clock:
        result = await clock.step_to(1.0)

    # Same logic: 3 regular ticks + 1 remainder tick = 4
    assert processor.tick_count == 4
    assert result == 1.0


# --- Line 182: fast_forward outside context ---


async def test_fast_forward_outside_context(clock_config: ClockConfig):
    clock = BacktestClock(clock_config)
    with pytest.raises(
        ClockError, match="Fast forward can only be used within a context"
    ):
        await clock.fast_forward(5.0)


# --- Line 185: fast_forward with seconds <= 0 ---


async def test_fast_forward_zero_seconds(clock_config: ClockConfig):
    clock = BacktestClock(clock_config)
    clock.add_processor(MockProcessor("ff_zero"))

    async with clock:
        await clock.fast_forward(0)
        await clock.fast_forward(-1.0)
        # Should return immediately without error


# --- Line 189: fast_forward past end_time ---


async def test_fast_forward_past_end_time(clock_config: ClockConfig):
    clock = BacktestClock(clock_config)
    clock.add_processor(MockProcessor("ff_past"))

    async with clock:
        with pytest.raises(
            ClockError, match="Cannot fast forward past end_time in backtest mode"
        ):
            await clock.fast_forward(999.0)


# --- Config validation ---


class TestConfigValidation:
    """Test ClockConfig field validation."""

    def test_processor_timeout_must_be_positive(self):
        with pytest.raises(ValidationError, match="processor_timeout"):
            ClockConfig(clock_mode=ClockMode.BACKTEST, processor_timeout=0)

    def test_processor_timeout_negative_rejected(self):
        with pytest.raises(ValidationError, match="processor_timeout"):
            ClockConfig(clock_mode=ClockMode.BACKTEST, processor_timeout=-1.0)

    def test_stats_window_size_must_be_positive(self):
        with pytest.raises(ValidationError, match="stats_window_size"):
            ClockConfig(clock_mode=ClockMode.BACKTEST, stats_window_size=0)

    def test_stats_window_size_negative_rejected(self):
        with pytest.raises(ValidationError, match="stats_window_size"):
            ClockConfig(clock_mode=ClockMode.BACKTEST, stats_window_size=-5)

    def test_stats_window_size_exceeds_max(self):
        with pytest.raises(ValidationError, match="stats_window_size"):
            ClockConfig(clock_mode=ClockMode.BACKTEST, stats_window_size=10001)

    def test_stats_window_size_at_max(self):
        config = ClockConfig(clock_mode=ClockMode.BACKTEST, stats_window_size=10000)
        assert config.stats_window_size == 10000

    def test_max_retries_must_be_non_negative(self):
        with pytest.raises(ValidationError, match="max_retries"):
            ClockConfig(clock_mode=ClockMode.BACKTEST, max_retries=-1)

    def test_max_retries_zero_is_valid(self):
        config = ClockConfig(clock_mode=ClockMode.BACKTEST, max_retries=0)
        assert config.max_retries == 0


# --- Stats window sync from clock to processor ---


async def test_stats_window_size_synced_to_processor():
    """Clock should sync its stats_window_size to processors on add."""
    config = ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        tick_size=1.0,
        start_time=0.0,
        end_time=10.0,
        stats_window_size=42,
    )
    clock = BacktestClock(config)
    proc = MockProcessor("p")
    assert proc._stats_window_size == 100  # default

    clock.add_processor(proc)
    assert proc._stats_window_size == 42  # synced from clock
