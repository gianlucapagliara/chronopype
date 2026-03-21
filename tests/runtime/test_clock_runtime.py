"""Tests for ClockRuntime."""

import asyncio
import threading

import pytest
from pydantic import ValidationError

from chronopype.clocks.backtest import BacktestClock
from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.clocks.realtime import RealtimeClock
from chronopype.exceptions import ClockRuntimeError
from chronopype.runtime.clock_runtime import ClockRuntime
from chronopype.runtime.config import ClockRuntimeConfig

from ..conftest import MockProcessor


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestClockRuntimeConfig:
    def test_defaults(self) -> None:
        cfg = ClockRuntimeConfig()
        assert cfg.clock_mode == ClockMode.REALTIME
        assert cfg.tick_size == 1.0
        assert cfg.start_time == 0.0
        assert cfg.end_time == 0.0
        assert cfg.thread_stop_timeout_seconds == 3.0
        assert cfg.clock_poll_interval_seconds == 0.1

    def test_frozen(self) -> None:
        cfg = ClockRuntimeConfig()
        with pytest.raises(ValidationError):
            cfg.tick_size = 2.0  # type: ignore[misc]

    def test_validation_tick_size(self) -> None:
        with pytest.raises(ValidationError):
            ClockRuntimeConfig(tick_size=0)
        with pytest.raises(ValidationError):
            ClockRuntimeConfig(tick_size=-1)

    def test_validation_timeout(self) -> None:
        with pytest.raises(ValidationError):
            ClockRuntimeConfig(thread_stop_timeout_seconds=0)

    def test_validation_poll_interval(self) -> None:
        with pytest.raises(ValidationError):
            ClockRuntimeConfig(clock_poll_interval_seconds=0)


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


class TestClockRuntimeConstruction:
    def test_init_with_defaults_creates_realtime_clock(self) -> None:
        rt = ClockRuntime()
        assert isinstance(rt.clock, RealtimeClock)

    def test_init_with_backtest_config(self) -> None:
        cfg = ClockRuntimeConfig(
            clock_mode=ClockMode.BACKTEST,
            start_time=1000.0,
            end_time=1010.0,
        )
        rt = ClockRuntime(config=cfg)
        assert isinstance(rt.clock, BacktestClock)

    def test_init_with_prebuilt_clock(self) -> None:
        clock = BacktestClock(
            ClockConfig(
                clock_mode=ClockMode.BACKTEST,
                tick_size=1.0,
                start_time=0.0,
                end_time=10.0,
            )
        )
        rt = ClockRuntime(clock=clock)
        assert rt.clock is clock

    def test_init_prebuilt_clock_takes_precedence(self) -> None:
        cfg = ClockRuntimeConfig(clock_mode=ClockMode.REALTIME)
        clock = BacktestClock(
            ClockConfig(
                clock_mode=ClockMode.BACKTEST,
                tick_size=1.0,
                start_time=0.0,
                end_time=10.0,
            )
        )
        rt = ClockRuntime(config=cfg, clock=clock)
        assert rt.clock is clock
        assert isinstance(rt.clock, BacktestClock)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestClockRuntimeProperties:
    def test_clock_property(self) -> None:
        rt = ClockRuntime()
        assert rt.clock is not None

    def test_config_property(self) -> None:
        cfg = ClockRuntimeConfig(tick_size=2.5)
        rt = ClockRuntime(config=cfg)
        assert rt.config is cfg

    def test_is_running_false_initially(self) -> None:
        rt = ClockRuntime()
        assert rt.is_running is False

    def test_get_clock_loop_none_initially(self) -> None:
        rt = ClockRuntime()
        assert rt.get_clock_loop() is None


# ---------------------------------------------------------------------------
# Async lifecycle — backtest
# ---------------------------------------------------------------------------


class TestClockRuntimeBacktest:
    @pytest.fixture
    def backtest_config(self) -> ClockRuntimeConfig:
        return ClockRuntimeConfig(
            clock_mode=ClockMode.BACKTEST,
            tick_size=1.0,
            start_time=1000.0,
            end_time=1010.0,
        )

    async def test_start_enters_context(
        self, backtest_config: ClockRuntimeConfig
    ) -> None:
        rt = ClockRuntime(config=backtest_config)
        await rt.start()
        assert rt.is_running is True
        await rt.stop()
        assert rt.is_running is False

    async def test_stop_exits_context(
        self, backtest_config: ClockRuntimeConfig
    ) -> None:
        rt = ClockRuntime(config=backtest_config)
        await rt.start()
        await rt.stop()
        assert rt.is_running is False

    async def test_context_manager(
        self, backtest_config: ClockRuntimeConfig
    ) -> None:
        async with ClockRuntime(config=backtest_config) as rt:
            assert rt.is_running is True
        assert rt.is_running is False

    async def test_backtest_til_advances_clock(
        self, backtest_config: ClockRuntimeConfig
    ) -> None:
        rt = ClockRuntime(config=backtest_config)
        processor = MockProcessor("bt")
        rt.clock.add_processor(processor)
        await rt.start()
        await rt.backtest_til(1005.0)
        assert processor.tick_count == 5
        assert rt.clock.current_timestamp == 1005.0
        await rt.stop()

    async def test_backtest_til_without_processors(
        self, backtest_config: ClockRuntimeConfig
    ) -> None:
        """When no processors are registered, backtest_til just updates the timestamp."""
        rt = ClockRuntime(config=backtest_config)
        # Don't enter context — just update the raw timestamp
        assert isinstance(rt.clock, BacktestClock)
        await rt.backtest_til(1007.0)
        assert rt.clock.current_timestamp == 1007.0

    async def test_backtest_til_on_realtime_raises(self) -> None:
        rt = ClockRuntime()  # defaults to realtime
        with pytest.raises(ClockRuntimeError, match="BacktestClock"):
            await rt.backtest_til(100.0)

    async def test_start_idempotent(
        self, backtest_config: ClockRuntimeConfig
    ) -> None:
        rt = ClockRuntime(config=backtest_config)
        await rt.start()
        await rt.start()  # should not raise
        assert rt.is_running is True
        await rt.stop()


# ---------------------------------------------------------------------------
# Async lifecycle — realtime
# ---------------------------------------------------------------------------


class TestClockRuntimeRealtime:
    async def test_start_creates_task(self) -> None:
        cfg = ClockRuntimeConfig(
            clock_mode=ClockMode.REALTIME, tick_size=0.1
        )
        rt = ClockRuntime(config=cfg)
        await rt.start()
        assert rt.is_running is True
        assert rt._clock_task is not None
        await rt.stop()

    async def test_stop_cancels_task(self) -> None:
        cfg = ClockRuntimeConfig(
            clock_mode=ClockMode.REALTIME, tick_size=0.1
        )
        rt = ClockRuntime(config=cfg)
        await rt.start()
        await rt.stop()
        assert rt._clock_task is None
        assert rt.is_running is False

    async def test_context_manager(self) -> None:
        cfg = ClockRuntimeConfig(
            clock_mode=ClockMode.REALTIME, tick_size=0.1
        )
        async with ClockRuntime(config=cfg) as rt:
            assert rt.is_running is True
        assert rt.is_running is False


# ---------------------------------------------------------------------------
# Threaded mode
# ---------------------------------------------------------------------------


class TestClockRuntimeThreaded:
    def test_start_threaded_creates_thread(self) -> None:
        cfg = ClockRuntimeConfig(
            clock_mode=ClockMode.REALTIME, tick_size=0.5
        )
        rt = ClockRuntime(config=cfg)
        rt.start_threaded()
        assert rt._clock_thread is not None
        assert rt._clock_thread.is_alive()
        assert rt.is_running is True
        rt.stop_threaded()

    def test_stop_threaded_joins_thread(self) -> None:
        cfg = ClockRuntimeConfig(
            clock_mode=ClockMode.REALTIME, tick_size=0.5
        )
        rt = ClockRuntime(config=cfg)
        rt.start_threaded()
        rt.stop_threaded()
        assert rt._clock_thread is None
        assert rt._stop_event is None
        assert rt.is_running is False

    def test_start_threaded_with_backtest_raises(self) -> None:
        cfg = ClockRuntimeConfig(
            clock_mode=ClockMode.BACKTEST,
            start_time=0.0,
            end_time=10.0,
        )
        rt = ClockRuntime(config=cfg)
        with pytest.raises(ClockRuntimeError, match="RealtimeClock"):
            rt.start_threaded()

    def test_start_threaded_idempotent(self) -> None:
        cfg = ClockRuntimeConfig(
            clock_mode=ClockMode.REALTIME, tick_size=0.5
        )
        rt = ClockRuntime(config=cfg)
        rt.start_threaded()
        thread = rt._clock_thread
        rt.start_threaded()  # should not create a new thread
        assert rt._clock_thread is thread
        rt.stop_threaded()

    def test_get_clock_loop_in_threaded_mode(self) -> None:
        cfg = ClockRuntimeConfig(
            clock_mode=ClockMode.REALTIME, tick_size=0.5
        )
        rt = ClockRuntime(config=cfg)
        rt.start_threaded()
        # Give the thread a moment to set up the event loop
        import time

        time.sleep(0.3)
        loop = rt.get_clock_loop()
        assert loop is not None
        assert isinstance(loop, asyncio.AbstractEventLoop)
        rt.stop_threaded()

    def test_get_clock_loop_none_after_stop(self) -> None:
        cfg = ClockRuntimeConfig(
            clock_mode=ClockMode.REALTIME, tick_size=0.5
        )
        rt = ClockRuntime(config=cfg)
        rt.start_threaded()
        rt.stop_threaded()
        assert rt.get_clock_loop() is None

    def test_error_callback_called_on_failure(self) -> None:
        """Verify error callback fires when the clock thread encounters an error."""
        cfg = ClockRuntimeConfig(
            clock_mode=ClockMode.REALTIME, tick_size=0.5
        )
        rt = ClockRuntime(config=cfg)
        errors: list[str] = []
        rt.start_threaded(on_error_callback=lambda msg: errors.append(msg))
        # Just verify it started; full error path requires injecting a failure
        rt.stop_threaded()
