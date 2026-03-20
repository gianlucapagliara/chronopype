"""Tests for clock event publishing (start, tick, stop events)."""

import pytest

from chronopype.clocks.backtest import BacktestClock
from chronopype.clocks.base import ClockStartEvent, ClockStopEvent, ClockTickEvent
from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from tests.conftest import MockProcessor


@pytest.fixture
def clock() -> BacktestClock:
    config = ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        tick_size=1.0,
        start_time=1000.0,
        end_time=1010.0,
        processor_timeout=0.5,
        max_retries=2,
        stats_window_size=10,
    )
    return BacktestClock(config)


class TestClockStartEvent:
    """Test that ClockStartEvent is emitted on context entry."""

    async def test_start_event_emitted(self, clock: BacktestClock) -> None:
        events: list[ClockStartEvent] = []

        def on_start(event: ClockStartEvent) -> None:
            events.append(event)

        clock.add_subscriber_with_callback(
            clock.start_publication, on_start, with_event_info=False
        )

        async with clock:
            pass

        assert len(events) == 1

    async def test_start_event_has_correct_data(self, clock: BacktestClock) -> None:
        events: list[ClockStartEvent] = []

        def on_start(event: ClockStartEvent) -> None:
            events.append(event)

        clock.add_subscriber_with_callback(
            clock.start_publication, on_start, with_event_info=False
        )

        async with clock:
            pass

        event = events[0]
        assert event.timestamp == 1000.0
        assert event.mode == ClockMode.BACKTEST
        assert event.tick_size == 1.0


class TestClockTickEvent:
    """Test that ClockTickEvent is emitted on each tick."""

    async def test_tick_events_emitted(self, clock: BacktestClock) -> None:
        events: list[ClockTickEvent] = []
        processor = MockProcessor()
        clock.add_processor(processor)

        def on_tick(event: ClockTickEvent) -> None:
            events.append(event)

        clock.add_subscriber_with_callback(
            clock.tick_publication, on_tick, with_event_info=False
        )

        async with clock:
            await clock.run_til(clock.start_time + 3)

        assert len(events) == 3

    async def test_tick_event_has_correct_counter(
        self, clock: BacktestClock
    ) -> None:
        events: list[ClockTickEvent] = []
        processor = MockProcessor()
        clock.add_processor(processor)

        def on_tick(event: ClockTickEvent) -> None:
            events.append(event)

        clock.add_subscriber_with_callback(
            clock.tick_publication, on_tick, with_event_info=False
        )

        async with clock:
            await clock.run_til(clock.start_time + 3)

        assert events[0].tick_counter == 1
        assert events[1].tick_counter == 2
        assert events[2].tick_counter == 3

    async def test_tick_event_has_correct_timestamps(
        self, clock: BacktestClock
    ) -> None:
        events: list[ClockTickEvent] = []
        processor = MockProcessor()
        clock.add_processor(processor)

        def on_tick(event: ClockTickEvent) -> None:
            events.append(event)

        clock.add_subscriber_with_callback(
            clock.tick_publication, on_tick, with_event_info=False
        )

        async with clock:
            await clock.run_til(clock.start_time + 3)

        assert events[0].timestamp == 1001.0
        assert events[1].timestamp == 1002.0
        assert events[2].timestamp == 1003.0

    async def test_tick_event_includes_active_processors(
        self, clock: BacktestClock
    ) -> None:
        events: list[ClockTickEvent] = []
        p1 = MockProcessor("p1")
        p2 = MockProcessor("p2")
        clock.add_processor(p1)
        clock.add_processor(p2)

        def on_tick(event: ClockTickEvent) -> None:
            events.append(event)

        clock.add_subscriber_with_callback(
            clock.tick_publication, on_tick, with_event_info=False
        )

        async with clock:
            await clock.run_til(clock.start_time + 1)

        assert len(events) == 1
        assert len(events[0].processors) == 2


class TestClockStopEvent:
    """Test that ClockStopEvent is emitted on shutdown."""

    async def test_stop_event_emitted(self, clock: BacktestClock) -> None:
        events: list[ClockStopEvent] = []
        processor = MockProcessor()
        clock.add_processor(processor)

        def on_stop(event: ClockStopEvent) -> None:
            events.append(event)

        clock.add_subscriber_with_callback(
            clock.stop_publication, on_stop, with_event_info=False
        )

        async with clock:
            await clock.run_til(clock.start_time + 2)

        assert len(events) == 1

    async def test_stop_event_has_correct_data(self, clock: BacktestClock) -> None:
        events: list[ClockStopEvent] = []
        processor = MockProcessor()
        clock.add_processor(processor)

        def on_stop(event: ClockStopEvent) -> None:
            events.append(event)

        clock.add_subscriber_with_callback(
            clock.stop_publication, on_stop, with_event_info=False
        )

        async with clock:
            await clock.run_til(clock.start_time + 5)

        event = events[0]
        assert event.total_ticks == 5
        assert processor in event.final_states

    async def test_stop_event_on_empty_clock(self, clock: BacktestClock) -> None:
        """Stop event should fire even with no processors."""
        events: list[ClockStopEvent] = []

        def on_stop(event: ClockStopEvent) -> None:
            events.append(event)

        clock.add_subscriber_with_callback(
            clock.stop_publication, on_stop, with_event_info=False
        )

        async with clock:
            pass

        assert len(events) == 1
        assert events[0].total_ticks == 0


class TestEventOrdering:
    """Test that events fire in the correct order."""

    async def test_start_before_tick_before_stop(
        self, clock: BacktestClock
    ) -> None:
        order: list[str] = []
        processor = MockProcessor()
        clock.add_processor(processor)

        clock.add_subscriber_with_callback(
            clock.start_publication,
            lambda e: order.append("start"),
            with_event_info=False,
        )
        clock.add_subscriber_with_callback(
            clock.tick_publication,
            lambda e: order.append("tick"),
            with_event_info=False,
        )
        clock.add_subscriber_with_callback(
            clock.stop_publication,
            lambda e: order.append("stop"),
            with_event_info=False,
        )

        async with clock:
            await clock.run_til(clock.start_time + 2)

        assert order == ["start", "tick", "tick", "stop"]
