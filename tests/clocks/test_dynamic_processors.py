"""Tests for dynamic processor add/remove during active clock context."""

import asyncio

import pytest

from chronopype.clocks.backtest import BacktestClock
from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.clocks.realtime import RealtimeClock
from tests.conftest import MockProcessor


@pytest.fixture
def backtest_config() -> ClockConfig:
    return ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        tick_size=1.0,
        start_time=1000.0,
        end_time=1020.0,
        processor_timeout=0.5,
        max_retries=0,
        stats_window_size=10,
    )


@pytest.fixture
def backtest_clock(backtest_config: ClockConfig) -> BacktestClock:
    return BacktestClock(backtest_config)


@pytest.fixture
def realtime_config() -> ClockConfig:
    return ClockConfig(
        clock_mode=ClockMode.REALTIME,
        tick_size=0.1,
        processor_timeout=1.0,
        max_retries=0,
        stats_window_size=10,
    )


@pytest.fixture
def realtime_clock(realtime_config: ClockConfig) -> RealtimeClock:
    return RealtimeClock(realtime_config)


class TestAddProcessorDuringContext:
    """Test adding processors after __aenter__ and verifying they get ticked."""

    async def test_add_processor_after_enter_gets_ticked(
        self, backtest_clock: BacktestClock
    ) -> None:
        """A processor added after __aenter__ should receive ticks."""
        p1 = MockProcessor("pre")
        backtest_clock.add_processor(p1)

        async with backtest_clock:
            # p1 is in context from __aenter__
            await backtest_clock.step(2)
            assert p1.tick_count == 2

            # Add p2 dynamically
            p2 = MockProcessor("dynamic")
            backtest_clock.add_processor(p2)
            assert p2.start_called

            # Both should be ticked
            await backtest_clock.step(3)
            assert p1.tick_count == 5
            assert p2.tick_count == 3

    async def test_add_processor_to_empty_context(
        self, backtest_clock: BacktestClock
    ) -> None:
        """A processor added to a clock with no initial processors should get ticked."""
        async with backtest_clock:
            p = MockProcessor("dynamic")
            backtest_clock.add_processor(p)

            await backtest_clock.step(3)
            assert p.tick_count == 3
            assert p.start_called

    async def test_add_multiple_processors_dynamically(
        self, backtest_clock: BacktestClock
    ) -> None:
        """Multiple processors added dynamically should all get ticked."""
        async with backtest_clock:
            processors = []
            for i in range(3):
                p = MockProcessor(f"dyn{i}")
                backtest_clock.add_processor(p)
                processors.append(p)

            await backtest_clock.step(4)
            for p in processors:
                assert p.tick_count == 4
                assert p.start_called


class TestRemoveProcessorDuringContext:
    """Test removing processors during active context."""

    async def test_remove_processor_stops_ticking(
        self, backtest_clock: BacktestClock
    ) -> None:
        """A removed processor should no longer receive ticks."""
        p1 = MockProcessor("keep")
        p2 = MockProcessor("remove")
        backtest_clock.add_processor(p1)
        backtest_clock.add_processor(p2)

        async with backtest_clock:
            await backtest_clock.step(2)
            assert p1.tick_count == 2
            assert p2.tick_count == 2

            backtest_clock.remove_processor(p2)
            assert p2.stop_called

            await backtest_clock.step(3)
            assert p1.tick_count == 5
            assert p2.tick_count == 2  # No further ticks

    async def test_remove_all_processors_during_context(
        self, backtest_clock: BacktestClock
    ) -> None:
        """Removing all processors should result in no ticks executed."""
        p1 = MockProcessor("p1")
        p2 = MockProcessor("p2")
        backtest_clock.add_processor(p1)
        backtest_clock.add_processor(p2)

        async with backtest_clock:
            await backtest_clock.step(1)
            assert p1.tick_count == 1
            assert p2.tick_count == 1

            backtest_clock.remove_processor(p1)
            backtest_clock.remove_processor(p2)

            # Clock should still advance without errors
            await backtest_clock.step(2)
            assert p1.tick_count == 1
            assert p2.tick_count == 1


class TestAddRemoveBetweenRunTilCalls:
    """Test adding/removing processors between sequential run_til/step calls."""

    async def test_add_processor_between_run_til_calls(
        self, backtest_clock: BacktestClock
    ) -> None:
        """A processor added between run_til calls should participate in subsequent ticks."""
        p1 = MockProcessor("original")
        backtest_clock.add_processor(p1)

        async with backtest_clock:
            await backtest_clock.run_til(backtest_clock.start_time + 3)
            assert p1.tick_count == 3

            p2 = MockProcessor("added")
            backtest_clock.add_processor(p2)

            await backtest_clock.run_til(backtest_clock.start_time + 6)
            assert p1.tick_count == 6
            assert p2.tick_count == 3

    async def test_remove_processor_between_step_calls(
        self, backtest_clock: BacktestClock
    ) -> None:
        """A processor removed between step calls should not participate further."""
        p1 = MockProcessor("keep")
        p2 = MockProcessor("remove")
        backtest_clock.add_processor(p1)
        backtest_clock.add_processor(p2)

        async with backtest_clock:
            await backtest_clock.step(3)
            assert p1.tick_count == 3
            assert p2.tick_count == 3

            backtest_clock.remove_processor(p2)

            await backtest_clock.step(3)
            assert p1.tick_count == 6
            assert p2.tick_count == 3

    async def test_add_and_remove_between_steps(
        self, backtest_clock: BacktestClock
    ) -> None:
        """Mixed add/remove between steps should work correctly."""
        p1 = MockProcessor("p1")
        p2 = MockProcessor("p2")
        backtest_clock.add_processor(p1)
        backtest_clock.add_processor(p2)

        async with backtest_clock:
            await backtest_clock.step(2)
            assert p1.tick_count == 2
            assert p2.tick_count == 2

            # Remove p2, add p3
            backtest_clock.remove_processor(p2)
            p3 = MockProcessor("p3")
            backtest_clock.add_processor(p3)

            await backtest_clock.step(2)
            assert p1.tick_count == 4
            assert p2.tick_count == 2  # Removed
            assert p3.tick_count == 2  # New


class TestRemoveAndReaddProcessor:
    """Test removing a processor and re-adding it."""

    async def test_remove_and_readd_same_processor(
        self, backtest_clock: BacktestClock
    ) -> None:
        """A processor removed and re-added should resume receiving ticks."""
        p = MockProcessor("reusable")
        backtest_clock.add_processor(p)

        async with backtest_clock:
            await backtest_clock.step(2)
            assert p.tick_count == 2

            backtest_clock.remove_processor(p)
            await backtest_clock.step(2)
            assert p.tick_count == 2  # No ticks while removed

            backtest_clock.add_processor(p)
            await backtest_clock.step(2)
            assert p.tick_count == 4  # Resumed

    async def test_remove_readd_across_run_til(
        self, backtest_clock: BacktestClock
    ) -> None:
        """Remove and re-add across run_til calls."""
        p = MockProcessor("lifecycle")
        backtest_clock.add_processor(p)

        async with backtest_clock:
            await backtest_clock.run_til(backtest_clock.start_time + 3)
            assert p.tick_count == 3

            backtest_clock.remove_processor(p)
            await backtest_clock.run_til(backtest_clock.start_time + 5)
            assert p.tick_count == 3

            backtest_clock.add_processor(p)
            await backtest_clock.run_til(backtest_clock.start_time + 8)
            assert p.tick_count == 6


class TestRealtimeDynamicProcessors:
    """Test dynamic processor management with RealtimeClock."""

    async def test_add_processor_before_run_til(
        self, realtime_clock: RealtimeClock
    ) -> None:
        """Processors added after __aenter__ but before run_til should get ticked."""
        async with realtime_clock:
            p = MockProcessor("dynamic")
            realtime_clock.add_processor(p)

            await asyncio.wait_for(
                realtime_clock.run_til(realtime_clock.current_timestamp + 0.25),
                timeout=2.0,
            )

            assert p.start_called
            assert p.tick_count >= 1

    async def test_realtime_add_processor_between_run_til(
        self, realtime_clock: RealtimeClock
    ) -> None:
        """Processors added between run_til calls should participate in subsequent runs."""
        p1 = MockProcessor("pre")
        realtime_clock.add_processor(p1)

        async with realtime_clock:
            await asyncio.wait_for(
                realtime_clock.run_til(realtime_clock.current_timestamp + 0.15),
                timeout=2.0,
            )
            p1_count_after_first = p1.tick_count
            assert p1_count_after_first >= 1

            p2 = MockProcessor("dynamic")
            realtime_clock.add_processor(p2)

            await asyncio.wait_for(
                realtime_clock.run_til(realtime_clock.current_timestamp + 0.15),
                timeout=2.0,
            )

            assert p1.tick_count > p1_count_after_first
            assert p2.tick_count >= 1


class TestCurrentContextConsistency:
    """Test that _current_context stays consistent with processor operations."""

    async def test_context_reflects_dynamic_add(
        self, backtest_clock: BacktestClock
    ) -> None:
        """_current_context should include dynamically added processors."""
        p1 = MockProcessor("p1")
        backtest_clock.add_processor(p1)

        async with backtest_clock:
            assert p1 in backtest_clock._current_context

            p2 = MockProcessor("p2")
            backtest_clock.add_processor(p2)
            assert p2 in backtest_clock._current_context
            assert len(backtest_clock._current_context) == 2

    async def test_context_reflects_dynamic_remove(
        self, backtest_clock: BacktestClock
    ) -> None:
        """_current_context should exclude removed processors."""
        p1 = MockProcessor("p1")
        p2 = MockProcessor("p2")
        backtest_clock.add_processor(p1)
        backtest_clock.add_processor(p2)

        async with backtest_clock:
            assert len(backtest_clock._current_context) == 2

            backtest_clock.remove_processor(p2)
            assert p2 not in backtest_clock._current_context
            assert len(backtest_clock._current_context) == 1

    async def test_context_none_outside_context(
        self, backtest_clock: BacktestClock
    ) -> None:
        """_current_context should be None outside async context."""
        p = MockProcessor("p")
        backtest_clock.add_processor(p)

        assert backtest_clock._current_context is None

        async with backtest_clock:
            assert backtest_clock._current_context is not None

        assert backtest_clock._current_context is None

    async def test_add_outside_context_does_not_create_context(
        self, backtest_clock: BacktestClock
    ) -> None:
        """Adding a processor outside context should not create _current_context."""
        p = MockProcessor("p")
        backtest_clock.add_processor(p)
        assert backtest_clock._current_context is None
