import asyncio
from typing import Any
from unittest.mock import Mock

import pytest

from chronopype.clocks.base import BaseClock
from chronopype.clocks.modes import ClockMode
from chronopype.exceptions import ClockContextError, ClockError
from tests.conftest import MockProcessor


@pytest.mark.parametrize(
    "clock_fixture,expected_mode",
    [
        ("clock", ClockMode.BACKTEST),
        ("realtime_clock", ClockMode.REALTIME),
    ],
)
def test_clock_initialization(
    clock_fixture: str, expected_mode: ClockMode, request: Any
) -> None:
    """Test basic clock initialization for both clock types."""
    clock = request.getfixturevalue(clock_fixture)
    assert isinstance(clock, BaseClock)
    assert clock.clock_mode == expected_mode
    assert clock.tick_size > 0
    assert len(clock.processors) == 0


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
def test_processor_management(
    clock_fixture: str, request: Any, mock_processor: MockProcessor
) -> None:
    """Test processor management for both clock types."""
    clock = request.getfixturevalue(clock_fixture)

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


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
def test_context_manager_errors(clock_fixture: str, request: Any) -> None:
    """Test context manager error cases for both clock types."""
    clock = request.getfixturevalue(clock_fixture)

    # Test nested context
    async def test_nested() -> None:
        async with clock:
            with pytest.raises(ClockContextError):
                async with clock:
                    pass

    asyncio.run(test_nested())

    # Test re-entry after error
    async def test_reentry() -> None:
        try:
            async with clock:
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected error

        with pytest.raises(ClockContextError):
            async with clock:
                pass  # Should raise because context is not properly cleaned up

    asyncio.run(test_reentry())

    # Reset the clock state
    clock._current_context = None
    clock._running = False

    # Test running flag
    clock._running = True

    async def test_running() -> None:
        with pytest.raises(ClockContextError):
            async with clock:
                pass

    asyncio.run(test_running())


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
def test_add_processor_when_started(
    clock_fixture: str, request: Any, mock_processor: MockProcessor
) -> None:
    """Test adding a processor when the clock is already started."""
    clock = request.getfixturevalue(clock_fixture)
    clock._started = True  # Simulate clock started state

    # Setup mock start method
    mock_processor.start = Mock()  # type: ignore

    # Add processor
    clock.add_processor(mock_processor)
    assert mock_processor in clock.processors

    # Verify processor was started
    state = clock.get_processor_state(mock_processor)
    assert state is not None
    assert state.is_active
    mock_processor.start.assert_called_once()

    # Test error handling during start
    error_processor = MockProcessor()
    error_processor.start = Mock(side_effect=ValueError("Start error"))  # type: ignore

    with pytest.raises(ClockError) as exc_info:
        clock.add_processor(error_processor)
    assert "Failed to start processor" in str(exc_info.value)
    assert error_processor not in clock.processors
    assert clock.get_processor_state(error_processor) is None


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
def test_remove_processor_when_active(
    clock_fixture: str, request: Any, mock_processor: MockProcessor
) -> None:
    """Test removing an active processor."""
    clock = request.getfixturevalue(clock_fixture)

    # Setup mock stop method
    mock_processor.stop = Mock()  # type: ignore

    clock.add_processor(mock_processor)

    # Simulate active processor
    state = clock.get_processor_state(mock_processor)
    clock._processor_states[mock_processor] = state.model_copy(
        update={"is_active": True}
    )

    # Remove processor
    clock.remove_processor(mock_processor)
    assert mock_processor not in clock.processors
    assert clock.get_processor_state(mock_processor) is None
    mock_processor.stop.assert_called_once()

    # Test error handling during stop
    error_processor = MockProcessor()
    error_processor.stop = Mock(side_effect=ValueError("Stop error"))  # type: ignore
    clock.add_processor(error_processor)
    clock._processor_states[error_processor] = state.model_copy(
        update={"is_active": True}
    )

    with pytest.raises(ClockError) as exc_info:
        clock.remove_processor(error_processor)
    assert "Failed to stop processor" in str(exc_info.value)
    assert error_processor not in clock.processors
    assert clock.get_processor_state(error_processor) is None
