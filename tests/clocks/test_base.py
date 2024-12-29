import asyncio
from typing import Any

import pytest

from chronopype.clocks.base import BaseClock
from chronopype.clocks.modes import ClockMode
from chronopype.exceptions import ClockContextError
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
