import asyncio

import pytest

from flowtime.clocks.base import BaseClock
from flowtime.exceptions import ClockError
from tests.conftest import MockProcessor


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
def test_add_remove_processor(
    clock_fixture: str, request: pytest.FixtureRequest, mock_processor: MockProcessor
) -> None:
    """Test adding and removing processors."""
    clock: BaseClock = request.getfixturevalue(clock_fixture)

    # Add processor
    clock.add_processor(mock_processor)
    assert mock_processor in clock.processors
    assert len(clock.processors) == 1

    state = clock.get_processor_state(mock_processor)
    assert state is not None
    assert not state.is_active

    # Remove processor
    clock.remove_processor(mock_processor)
    assert mock_processor not in clock.processors
    assert len(clock.processors) == 0

    # Test duplicate add
    clock.add_processor(mock_processor)
    with pytest.raises(ClockError):
        clock.add_processor(mock_processor)

    # Test remove non-existent
    clock.remove_processor(mock_processor)
    with pytest.raises(ClockError):
        clock.remove_processor(mock_processor)


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
@pytest.mark.asyncio
async def test_processor_async_tick(
    clock_fixture: str, request: pytest.FixtureRequest, mock_processor: MockProcessor
) -> None:
    """Test processor with async_tick implementation."""
    clock: BaseClock = request.getfixturevalue(clock_fixture)

    class AsyncProcessor(MockProcessor):
        async def async_tick(self, timestamp: float) -> None:
            await asyncio.sleep(0.1)
            await super().async_tick(timestamp)

    processor = AsyncProcessor("async")
    clock.add_processor(processor)

    async with clock:
        await clock.run_til(clock.current_timestamp + 1)

    assert processor.tick_count >= 1


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
def test_processor_state_transitions(
    clock_fixture: str, request: pytest.FixtureRequest, mock_processor: MockProcessor
) -> None:
    """Test processor state transitions."""
    clock: BaseClock = request.getfixturevalue(clock_fixture)
    clock.add_processor(mock_processor)

    # Test initial state
    state = clock.get_processor_state(mock_processor)
    assert state is not None
    assert not state.is_active
    assert state.retry_count == 0

    # Test state after pause/resume
    clock.resume_processor(mock_processor)
    state = clock.get_processor_state(mock_processor)
    assert state is not None
    assert state.is_active

    clock.pause_processor(mock_processor)
    state = clock.get_processor_state(mock_processor)
    assert state is not None
    assert not state.is_active

    # Test idempotent operations
    clock.pause_processor(mock_processor)  # Should not raise
    clock.resume_processor(mock_processor)
    clock.resume_processor(mock_processor)  # Should not raise


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
@pytest.mark.asyncio
async def test_processor_state_management(
    clock_fixture: str, request: pytest.FixtureRequest, mock_processor: MockProcessor
) -> None:
    """Test processor state management edge cases."""
    clock: BaseClock = request.getfixturevalue(clock_fixture)

    # Test adding duplicate processor
    clock.add_processor(mock_processor)
    with pytest.raises(ClockError):
        clock.add_processor(mock_processor)

    # Test removing non-existent processor
    other_processor = MockProcessor("other")
    with pytest.raises(ClockError):
        clock.remove_processor(other_processor)

    # Test pausing/resuming non-existent processor
    with pytest.raises(ClockError):
        clock.pause_processor(other_processor)
    with pytest.raises(ClockError):
        clock.resume_processor(other_processor)

    # Test idempotent pause/resume
    clock.pause_processor(mock_processor)
    clock.pause_processor(mock_processor)  # Should not raise
    state = clock.get_processor_state(mock_processor)
    assert state is not None
    assert not state.is_active

    clock.resume_processor(mock_processor)
    clock.resume_processor(mock_processor)  # Should not raise
    state = clock.get_processor_state(mock_processor)
    assert state is not None
    assert state.is_active
