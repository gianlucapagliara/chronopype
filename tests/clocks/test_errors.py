from collections.abc import Callable

import pytest

from chronopype.clocks.base import BaseClock
from chronopype.exceptions import ProcessorTimeoutError
from chronopype.processors.base import TickProcessor
from tests.conftest import MockProcessor


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
@pytest.mark.asyncio
async def test_processor_timeout(
    clock_fixture: str,
    request: pytest.FixtureRequest,
    mock_processor: MockProcessor,
    error_callback: Callable[[TickProcessor, Exception], None],
    error_list: list[tuple[TickProcessor, Exception]],
) -> None:
    """Test processor timeout handling."""
    clock: BaseClock = request.getfixturevalue(clock_fixture)
    clock._error_callback = error_callback
    clock.add_processor(mock_processor)
    mock_processor.sleep_time = clock.config.processor_timeout + 0.1

    async with clock:
        with pytest.raises(ProcessorTimeoutError):
            await clock.run_til(clock.current_timestamp + 1)

    assert len(error_list) > 0
    assert isinstance(error_list[0][1], ProcessorTimeoutError)


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
@pytest.mark.asyncio
async def test_processor_timeout_with_retries(
    clock_fixture: str,
    request: pytest.FixtureRequest,
    mock_processor: MockProcessor,
    error_callback: Callable[[TickProcessor, Exception], None],
    error_list: list[tuple[TickProcessor, Exception]],
) -> None:
    """Test processor timeout with retries."""
    clock: BaseClock = request.getfixturevalue(clock_fixture)
    clock._error_callback = error_callback
    clock.add_processor(mock_processor)

    # Make processor sleep longer than timeout but less than total retry time
    mock_processor.sleep_time = (
        clock.config.processor_timeout * 0.6
    )  # Should succeed after retries

    async with clock:
        await clock.run_til(clock.current_timestamp + 1)

    assert len(error_list) == 0
    assert mock_processor.tick_count >= 1

    # Now make it fail even with retries
    mock_processor.sleep_time = clock.config.processor_timeout * 2

    async with clock:
        with pytest.raises(ProcessorTimeoutError):
            await clock.run_til(clock.current_timestamp + 2)

    assert len(error_list) > 0
    assert isinstance(error_list[0][1], ProcessorTimeoutError)


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
@pytest.mark.asyncio
async def test_processor_error_handling(
    clock_fixture: str,
    request: pytest.FixtureRequest,
    mock_processor: MockProcessor,
    error_callback: Callable[[TickProcessor, Exception], None],
    error_list: list[tuple[TickProcessor, Exception]],
) -> None:
    """Test error handling during processor execution."""
    clock: BaseClock = request.getfixturevalue(clock_fixture)
    clock._error_callback = error_callback
    clock.add_processor(mock_processor)

    # Make processor raise an error
    mock_processor.should_raise = True

    async with clock:
        with pytest.raises(ValueError):
            await clock.run_til(clock.current_timestamp + 1)

    assert len(error_list) > 0
    assert isinstance(error_list[0][1], ValueError)

    state = clock.get_processor_state(mock_processor)
    assert state is not None
    assert state.error_count == 1
    assert state.last_error is not None
    assert state.last_error_time is not None


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
@pytest.mark.asyncio
async def test_concurrent_processor_errors(
    clock_fixture: str, request: pytest.FixtureRequest
) -> None:
    """Test error handling in concurrent mode."""
    clock: BaseClock = request.getfixturevalue(clock_fixture)

    # Create a new config with concurrent_processors set to True
    new_config = clock.config.model_copy(update={"concurrent_processors": True})
    clock._config = new_config

    # Add multiple processors that will raise errors
    processors = [MockProcessor() for _ in range(3)]
    for processor in processors:
        processor.should_raise = True
        clock.add_processor(processor)

    async with clock:
        with pytest.raises(ValueError):
            await clock.run_til(clock.current_timestamp + 1)

    # Check that all processors have error states
    for processor in processors:
        state = clock.get_processor_state(processor)
        assert state is not None
        assert state.error_count == 1
        assert state.last_error is not None
        assert state.last_error_time is not None


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
@pytest.mark.asyncio
async def test_processor_execution_errors(
    clock_fixture: str,
    request: pytest.FixtureRequest,
    mock_processor: MockProcessor,
    error_callback: Callable[[TickProcessor, Exception], None],
    error_list: list[tuple[TickProcessor, Exception]],
) -> None:
    """Test various error scenarios during processor execution."""
    clock: BaseClock = request.getfixturevalue(clock_fixture)
    clock._error_callback = error_callback
    clock.add_processor(mock_processor)

    # Test timeout error
    mock_processor.sleep_time = clock.config.processor_timeout * 2
    async with clock:
        with pytest.raises(ProcessorTimeoutError):
            await clock.run_til(clock.current_timestamp + 1)

    assert len(error_list) > 0
    assert isinstance(error_list[0][1], ProcessorTimeoutError)

    # Test regular exception
    mock_processor.should_raise = True
    mock_processor.sleep_time = 0
    error_list.clear()  # Clear previous errors

    async with clock:
        with pytest.raises(ValueError):
            await clock.run_til(clock.current_timestamp + 1)

    assert len(error_list) > 0
    assert isinstance(error_list[-1][1], ValueError)
