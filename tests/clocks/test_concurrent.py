"""Tests for concurrent processor execution and pause/resume during execution."""

import asyncio
from collections.abc import Callable

import pytest

from chronopype.clocks.backtest import BacktestClock
from chronopype.clocks.base import BaseClock
from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.clocks.realtime import RealtimeClock
from chronopype.exceptions import ProcessorTimeoutError
from chronopype.processors.base import TickProcessor
from tests.conftest import MockProcessor


@pytest.fixture
def concurrent_backtest_config() -> ClockConfig:
    return ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        tick_size=1.0,
        start_time=1000.0,
        end_time=1010.0,
        processor_timeout=1.0,
        max_retries=2,
        concurrent_processors=True,
        stats_window_size=10,
    )


@pytest.fixture
def concurrent_realtime_config() -> ClockConfig:
    return ClockConfig(
        clock_mode=ClockMode.REALTIME,
        tick_size=0.1,
        processor_timeout=1.0,
        max_retries=2,
        concurrent_processors=True,
        stats_window_size=10,
    )


@pytest.fixture
def concurrent_clock(concurrent_backtest_config: ClockConfig) -> BacktestClock:
    return BacktestClock(concurrent_backtest_config)


@pytest.fixture
def concurrent_realtime_clock(
    concurrent_realtime_config: ClockConfig,
) -> RealtimeClock:
    return RealtimeClock(concurrent_realtime_config)


class TestConcurrentExecution:
    """Test concurrent processor execution."""

    async def test_all_processors_execute_concurrently(
        self, concurrent_clock: BacktestClock
    ) -> None:
        """All processors should execute on each tick in concurrent mode."""
        processors = [MockProcessor(f"p{i}") for i in range(5)]
        for p in processors:
            concurrent_clock.add_processor(p)

        async with concurrent_clock:
            await concurrent_clock.run_til(concurrent_clock.start_time + 3)

        for p in processors:
            assert p.tick_count == 3

    async def test_concurrent_faster_than_sequential(
        self, concurrent_backtest_config: ClockConfig
    ) -> None:
        """Concurrent execution should be faster than sequential for slow processors."""
        import time

        # Sequential
        seq_config = concurrent_backtest_config.model_copy(
            update={"concurrent_processors": False}
        )
        seq_clock = BacktestClock(seq_config)
        processors_seq = [MockProcessor(f"seq{i}") for i in range(3)]
        for p in processors_seq:
            p.sleep_time = 0.05
            seq_clock.add_processor(p)

        start = time.perf_counter()
        async with seq_clock:
            await seq_clock.run_til(seq_clock.start_time + 1)
        seq_time = time.perf_counter() - start

        # Concurrent
        conc_clock = BacktestClock(concurrent_backtest_config)
        processors_conc = [MockProcessor(f"conc{i}") for i in range(3)]
        for p in processors_conc:
            p.sleep_time = 0.05
            conc_clock.add_processor(p)

        start = time.perf_counter()
        async with conc_clock:
            await conc_clock.run_til(conc_clock.start_time + 1)
        conc_time = time.perf_counter() - start

        # Concurrent should be notably faster with 3 processors
        assert conc_time < seq_time

    async def test_concurrent_partial_failure(
        self, concurrent_clock: BacktestClock
    ) -> None:
        """When one processor fails in concurrent mode, others should still execute."""
        good1 = MockProcessor("good1")
        bad = MockProcessor("bad")
        good2 = MockProcessor("good2")
        bad.should_raise = True

        concurrent_clock.add_processor(good1)
        concurrent_clock.add_processor(bad)
        concurrent_clock.add_processor(good2)

        errors: list[tuple[TickProcessor, Exception]] = []

        def error_cb(proc: TickProcessor, err: Exception) -> None:
            errors.append((proc, err))

        concurrent_clock._error_callback = error_cb

        async with concurrent_clock:
            with pytest.raises(ValueError):
                await concurrent_clock.run_til(concurrent_clock.start_time + 1)

        # The good processors should have executed (gather runs all)
        assert good1.tick_count == 1
        assert good2.tick_count == 1
        assert bad.tick_count == 0

        # Error was reported
        assert len(errors) >= 1

    async def test_concurrent_multiple_failures(
        self, concurrent_clock: BacktestClock
    ) -> None:
        """Multiple processor failures - first error is raised."""
        p1 = MockProcessor("fail1")
        p2 = MockProcessor("fail2")
        p1.should_raise = True
        p2.should_raise = True

        concurrent_clock.add_processor(p1)
        concurrent_clock.add_processor(p2)

        errors: list[tuple[TickProcessor, Exception]] = []
        concurrent_clock._error_callback = lambda p, e: errors.append((p, e))

        async with concurrent_clock:
            with pytest.raises(ValueError):
                await concurrent_clock.run_til(concurrent_clock.start_time + 1)

        # Both errors were reported via callback
        assert len(errors) == 2

    async def test_concurrent_with_slow_processor(
        self, concurrent_clock: BacktestClock
    ) -> None:
        """A slow processor shouldn't block fast processors in concurrent mode."""
        fast = MockProcessor("fast")
        slow = MockProcessor("slow")
        slow.sleep_time = 0.1

        concurrent_clock.add_processor(fast)
        concurrent_clock.add_processor(slow)

        async with concurrent_clock:
            await concurrent_clock.run_til(concurrent_clock.start_time + 1)

        assert fast.tick_count == 1
        assert slow.tick_count == 1


class TestPauseResumeDuringExecution:
    """Test pausing and resuming processors during clock execution."""

    async def test_pause_processor_skips_execution(self) -> None:
        """A paused processor should not execute on ticks."""
        config = ClockConfig(
            clock_mode=ClockMode.BACKTEST,
            tick_size=1.0,
            start_time=1000.0,
            end_time=1010.0,
            processor_timeout=0.5,
            max_retries=0,
        )
        clock = BacktestClock(config)
        processor = MockProcessor("p")
        clock.add_processor(processor)

        async with clock:
            # Execute 2 ticks normally
            await clock.step(2)
            assert processor.tick_count == 2

            # Pause and execute 2 more
            clock.pause_processor(processor)
            await clock.step(2)
            assert processor.tick_count == 2  # No change

            # Resume and execute 2 more
            clock.resume_processor(processor)
            await clock.step(2)
            assert processor.tick_count == 4

    async def test_pause_one_of_multiple_processors(self) -> None:
        """Pausing one processor should not affect others."""
        config = ClockConfig(
            clock_mode=ClockMode.BACKTEST,
            tick_size=1.0,
            start_time=1000.0,
            end_time=1010.0,
            processor_timeout=0.5,
        )
        clock = BacktestClock(config)
        p1 = MockProcessor("p1")
        p2 = MockProcessor("p2")
        clock.add_processor(p1)
        clock.add_processor(p2)

        async with clock:
            await clock.step(2)
            assert p1.tick_count == 2
            assert p2.tick_count == 2

            clock.pause_processor(p1)
            await clock.step(2)
            assert p1.tick_count == 2  # Paused
            assert p2.tick_count == 4  # Still running

    async def test_pause_resume_preserves_state(self) -> None:
        """Pause/resume should preserve processor error state."""
        config = ClockConfig(
            clock_mode=ClockMode.BACKTEST,
            tick_size=1.0,
            start_time=1000.0,
            end_time=1020.0,
            processor_timeout=0.5,
            max_retries=0,
        )
        clock = BacktestClock(config)
        processor = MockProcessor("p")
        clock.add_processor(processor)

        errors: list[tuple[TickProcessor, Exception]] = []
        clock._error_callback = lambda p, e: errors.append((p, e))

        async with clock:
            # Run a tick successfully
            await clock.step(1)
            assert processor.tick_count == 1

            # Cause an error
            processor.should_raise = True
            with pytest.raises(ValueError):
                await clock.step(1)

            # Check error state
            state = clock.get_processor_state(processor)
            assert state is not None
            assert state.error_count == 1

            # Pause and resume
            clock.pause_processor(processor)
            clock.resume_processor(processor)

            # Error count should be preserved
            state = clock.get_processor_state(processor)
            assert state is not None
            assert state.error_count == 1

    async def test_get_active_processors(self) -> None:
        """get_active_processors should reflect pause/resume state."""
        config = ClockConfig(
            clock_mode=ClockMode.BACKTEST,
            tick_size=1.0,
            start_time=1000.0,
            end_time=1010.0,
        )
        clock = BacktestClock(config)
        p1 = MockProcessor("p1")
        p2 = MockProcessor("p2")
        p3 = MockProcessor("p3")
        clock.add_processor(p1)
        clock.add_processor(p2)
        clock.add_processor(p3)

        async with clock:
            assert len(clock.get_active_processors()) == 3

            clock.pause_processor(p2)
            assert len(clock.get_active_processors()) == 2
            assert p2 not in clock.get_active_processors()

            clock.resume_processor(p2)
            assert len(clock.get_active_processors()) == 3


class TestConcurrentPauseResume:
    """Test pause/resume in concurrent execution mode."""

    async def test_paused_processor_skipped_in_concurrent(
        self, concurrent_clock: BacktestClock
    ) -> None:
        """Paused processors should not be included in concurrent execution."""
        p1 = MockProcessor("p1")
        p2 = MockProcessor("p2")
        concurrent_clock.add_processor(p1)
        concurrent_clock.add_processor(p2)

        async with concurrent_clock:
            await concurrent_clock.step(1)
            assert p1.tick_count == 1
            assert p2.tick_count == 1

            concurrent_clock.pause_processor(p1)
            await concurrent_clock.step(1)
            assert p1.tick_count == 1  # Skipped
            assert p2.tick_count == 2  # Still ran


class TestConcurrentTimeout:
    """Test timeout behavior in concurrent mode."""

    async def test_concurrent_timeout_one_processor(
        self, concurrent_clock: BacktestClock
    ) -> None:
        """One processor timing out should not prevent others from executing."""
        fast = MockProcessor("fast")
        slow = MockProcessor("slow")
        slow.sleep_time = concurrent_clock.config.processor_timeout + 0.5

        concurrent_clock.add_processor(fast)
        concurrent_clock.add_processor(slow)

        errors: list[tuple[TickProcessor, Exception]] = []
        concurrent_clock._error_callback = lambda p, e: errors.append((p, e))

        async with concurrent_clock:
            with pytest.raises(ProcessorTimeoutError):
                await concurrent_clock.run_til(concurrent_clock.start_time + 1)

        # Fast processor should have executed
        assert fast.tick_count == 1
        # Error was reported for slow processor
        assert any(isinstance(e, ProcessorTimeoutError) for _, e in errors)
