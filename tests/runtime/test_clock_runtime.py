"""Tests for ClockRuntime."""

import asyncio

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
            cfg.thread_stop_timeout_seconds = 2.0  # type: ignore[misc]

    def test_custom_clock_config(self) -> None:
        cc = ClockConfig(
            clock_mode=ClockMode.BACKTEST,
            tick_size=0.5,
            start_time=100.0,
            end_time=200.0,
        )
        cfg = ClockRuntimeConfig(clock_config=cc)
        assert cfg.clock_mode == ClockMode.BACKTEST
        assert cfg.tick_size == 0.5
        assert cfg.start_time == 100.0
        assert cfg.end_time == 200.0

    def test_validation_timeout(self) -> None:
        with pytest.raises(ValidationError):
            ClockRuntimeConfig(thread_stop_timeout_seconds=0)

    def test_validation_poll_interval(self) -> None:
        with pytest.raises(ValidationError):
            ClockRuntimeConfig(clock_poll_interval_seconds=0)

    def test_shortcut_properties(self) -> None:
        cc = ClockConfig(clock_mode=ClockMode.BACKTEST, start_time=10.0, end_time=20.0)
        cfg = ClockRuntimeConfig(clock_config=cc)
        assert cfg.clock_mode is cc.clock_mode
        assert cfg.tick_size == cc.tick_size
        assert cfg.start_time == cc.start_time
        assert cfg.end_time == cc.end_time


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


class TestClockRuntimeConstruction:
    def test_init_with_defaults_creates_realtime_clock(self) -> None:
        rt = ClockRuntime()
        assert isinstance(rt.clock, RealtimeClock)

    def test_init_with_backtest_config(self) -> None:
        cc = ClockConfig(
            clock_mode=ClockMode.BACKTEST,
            start_time=1000.0,
            end_time=1010.0,
        )
        cfg = ClockRuntimeConfig(clock_config=cc)
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
        cfg = ClockRuntimeConfig()  # defaults to REALTIME
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
        cc = ClockConfig(clock_mode=ClockMode.REALTIME, tick_size=2.5)
        cfg = ClockRuntimeConfig(clock_config=cc)
        rt = ClockRuntime(config=cfg)
        assert rt.config is cfg

    def test_is_running_false_initially(self) -> None:
        rt = ClockRuntime()
        assert rt.is_running is False

    def test_get_clock_loop_none_initially(self) -> None:
        rt = ClockRuntime()
        assert rt.get_clock_loop() is None

    def test_task_error_none_initially(self) -> None:
        rt = ClockRuntime()
        assert rt.task_error is None


# ---------------------------------------------------------------------------
# Async lifecycle — backtest
# ---------------------------------------------------------------------------


def _backtest_config() -> ClockRuntimeConfig:
    return ClockRuntimeConfig(
        clock_config=ClockConfig(
            clock_mode=ClockMode.BACKTEST,
            tick_size=1.0,
            start_time=1000.0,
            end_time=1010.0,
        )
    )


class TestClockRuntimeBacktest:
    @pytest.fixture
    def backtest_config(self) -> ClockRuntimeConfig:
        return _backtest_config()

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

    async def test_context_manager(self, backtest_config: ClockRuntimeConfig) -> None:
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

    async def test_start_idempotent(self, backtest_config: ClockRuntimeConfig) -> None:
        rt = ClockRuntime(config=backtest_config)
        await rt.start()
        await rt.start()  # should not raise
        assert rt.is_running is True
        await rt.stop()

    async def test_stop_without_start(
        self, backtest_config: ClockRuntimeConfig
    ) -> None:
        """Calling stop() without start() should be a no-op."""
        rt = ClockRuntime(config=backtest_config)
        await rt.stop()  # should not raise
        assert rt.is_running is False

    async def test_double_stop(self, backtest_config: ClockRuntimeConfig) -> None:
        """Calling stop() twice should be safe."""
        rt = ClockRuntime(config=backtest_config)
        await rt.start()
        await rt.stop()
        await rt.stop()  # second stop should not raise
        assert rt.is_running is False

    async def test_backtest_til_backward_time(
        self, backtest_config: ClockRuntimeConfig
    ) -> None:
        """backtest_til with a past target should be a no-op via step_to."""
        rt = ClockRuntime(config=backtest_config)
        processor = MockProcessor("bt")
        rt.clock.add_processor(processor)
        await rt.start()
        await rt.backtest_til(1005.0)
        # Try to go backward — should not change anything
        await rt.backtest_til(1002.0)
        assert rt.clock.current_timestamp == 1005.0
        assert processor.tick_count == 5
        await rt.stop()

    async def test_backtest_til_exact_boundary(
        self, backtest_config: ClockRuntimeConfig
    ) -> None:
        """backtest_til to exactly end_time should work."""
        rt = ClockRuntime(config=backtest_config)
        processor = MockProcessor("bt")
        rt.clock.add_processor(processor)
        await rt.start()
        await rt.backtest_til(1010.0)
        assert rt.clock.current_timestamp == 1010.0
        await rt.stop()

    async def test_backtest_til_sequential_calls(
        self, backtest_config: ClockRuntimeConfig
    ) -> None:
        """Multiple backtest_til calls should be cumulative."""
        rt = ClockRuntime(config=backtest_config)
        processor = MockProcessor("bt")
        rt.clock.add_processor(processor)
        await rt.start()
        await rt.backtest_til(1003.0)
        assert processor.tick_count == 3
        await rt.backtest_til(1007.0)
        assert processor.tick_count == 7
        await rt.stop()

    async def test_backtest_til_without_context_validates_end_time(self) -> None:
        """backtest_til without context should validate against end_time."""
        cfg = _backtest_config()
        rt = ClockRuntime(config=cfg)
        with pytest.raises(ClockRuntimeError, match="exceeds end_time"):
            await rt.backtest_til(2000.0)

    async def test_backtest_til_processor_error_propagates(
        self, backtest_config: ClockRuntimeConfig
    ) -> None:
        """Errors from processors should propagate through backtest_til."""
        rt = ClockRuntime(config=backtest_config)
        processor = MockProcessor("failing")
        processor.should_raise = True
        rt.clock.add_processor(processor)
        await rt.start()
        with pytest.raises(ValueError, match="Test error"):
            await rt.backtest_til(1005.0)
        await rt.stop()

    async def test_prebuilt_backtest_clock_uses_isinstance(self) -> None:
        """When a BacktestClock is passed with a default (REALTIME) config,
        start() should still enter backtest mode based on isinstance check."""
        clock = BacktestClock(
            ClockConfig(
                clock_mode=ClockMode.BACKTEST,
                tick_size=1.0,
                start_time=0.0,
                end_time=10.0,
            )
        )
        # Config defaults to REALTIME, but clock is BacktestClock
        rt = ClockRuntime(clock=clock)
        await rt.start()
        # Should be in backtest mode — no task created
        assert rt._clock_task is None
        assert rt.is_running is True
        await rt.stop()


# ---------------------------------------------------------------------------
# Async lifecycle — realtime
# ---------------------------------------------------------------------------


class TestClockRuntimeRealtime:
    @pytest.fixture
    def realtime_config(self) -> ClockRuntimeConfig:
        return ClockRuntimeConfig(
            clock_config=ClockConfig(
                clock_mode=ClockMode.REALTIME,
                tick_size=0.1,
            )
        )

    async def test_start_creates_task(
        self, realtime_config: ClockRuntimeConfig
    ) -> None:
        rt = ClockRuntime(config=realtime_config)
        await rt.start()
        assert rt.is_running is True
        assert rt._clock_task is not None
        await rt.stop()

    async def test_stop_cancels_task(self, realtime_config: ClockRuntimeConfig) -> None:
        rt = ClockRuntime(config=realtime_config)
        await rt.start()
        await rt.stop()
        assert rt._clock_task is None
        assert rt.is_running is False

    async def test_context_manager(self, realtime_config: ClockRuntimeConfig) -> None:
        async with ClockRuntime(config=realtime_config) as rt:
            assert rt.is_running is True
        assert rt.is_running is False

    async def test_stop_without_start(
        self, realtime_config: ClockRuntimeConfig
    ) -> None:
        rt = ClockRuntime(config=realtime_config)
        await rt.stop()  # should not raise

    async def test_double_stop(self, realtime_config: ClockRuntimeConfig) -> None:
        rt = ClockRuntime(config=realtime_config)
        await rt.start()
        await rt.stop()
        await rt.stop()  # should not raise

    async def test_is_running_false_after_task_done(
        self, realtime_config: ClockRuntimeConfig
    ) -> None:
        """is_running should reflect actual task state."""
        rt = ClockRuntime(config=realtime_config)
        await rt.start()
        assert rt.is_running is True
        # Cancel the task manually to simulate completion
        rt._clock_task.cancel()  # type: ignore[union-attr]
        with pytest.raises(asyncio.CancelledError):
            await rt._clock_task  # type: ignore[misc]
        # Task is done — is_running should reflect that
        assert rt.is_running is False
        await rt.stop()

    async def test_realtime_with_processor(
        self, realtime_config: ClockRuntimeConfig
    ) -> None:
        """Integration test: realtime runtime with a processor."""
        rt = ClockRuntime(config=realtime_config)
        processor = MockProcessor("rt")
        rt.clock.add_processor(processor)
        await rt.start()
        # Let it tick a few times
        await asyncio.sleep(0.35)
        await rt.stop()
        assert processor.tick_count >= 2


# ---------------------------------------------------------------------------
# Threaded mode
# ---------------------------------------------------------------------------


class TestClockRuntimeThreaded:
    @pytest.fixture
    def rt(self) -> ClockRuntime:
        cfg = ClockRuntimeConfig(
            clock_config=ClockConfig(clock_mode=ClockMode.REALTIME, tick_size=0.5)
        )
        rt = ClockRuntime(config=cfg)
        yield rt  # type: ignore[misc]
        # Ensure cleanup even if a test fails
        rt.stop_threaded()

    def test_start_threaded_creates_thread(self, rt: ClockRuntime) -> None:
        rt.start_threaded()
        assert rt._clock_thread is not None
        assert rt._clock_thread.is_alive()
        assert rt.is_running is True

    def test_stop_threaded_joins_thread(self, rt: ClockRuntime) -> None:
        rt.start_threaded()
        rt.stop_threaded()
        assert rt._clock_thread is None
        assert rt._stop_event is None
        assert rt.is_running is False

    def test_start_threaded_with_backtest_raises(self) -> None:
        cfg = ClockRuntimeConfig(
            clock_config=ClockConfig(
                clock_mode=ClockMode.BACKTEST,
                start_time=0.0,
                end_time=10.0,
            )
        )
        rt = ClockRuntime(config=cfg)
        with pytest.raises(ClockRuntimeError, match="RealtimeClock"):
            rt.start_threaded()

    def test_start_threaded_idempotent(self, rt: ClockRuntime) -> None:
        rt.start_threaded()
        thread = rt._clock_thread
        rt.start_threaded()  # should not create a new thread
        assert rt._clock_thread is thread

    def test_get_clock_loop_in_threaded_mode(self, rt: ClockRuntime) -> None:
        rt.start_threaded()
        # loop_ready event means get_clock_loop() is available immediately
        loop = rt.get_clock_loop()
        assert loop is not None
        assert isinstance(loop, asyncio.AbstractEventLoop)

    def test_get_clock_loop_none_after_stop(self, rt: ClockRuntime) -> None:
        rt.start_threaded()
        rt.stop_threaded()
        assert rt.get_clock_loop() is None

    def test_stop_threaded_without_start(self, rt: ClockRuntime) -> None:
        """stop_threaded() without start_threaded() should be a no-op."""
        rt.stop_threaded()  # should not raise

    def test_double_stop_threaded(self, rt: ClockRuntime) -> None:
        """Double stop_threaded() should be safe."""
        rt.start_threaded()
        rt.stop_threaded()
        rt.stop_threaded()  # should not raise

    def test_error_callback_parameter_accepted(self, rt: ClockRuntime) -> None:
        """Verify error callback parameter is accepted and start works."""
        errors: list[str] = []
        rt.start_threaded(on_error_callback=lambda msg: errors.append(msg))
        assert rt.is_running is True
