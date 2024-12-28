import pytest

from flowtime.clocks.backtest import BacktestClock
from flowtime.exceptions import ClockError
from flowtime.models import ClockConfig
from tests.conftest import MockProcessor


def test_backtest_config(clock_config: ClockConfig) -> None:
    """Test backtest clock configuration."""
    clock = BacktestClock(clock_config)
    assert clock.start_time == 1000.0
    assert clock.end_time == 1010.0
    assert clock.current_timestamp == clock.start_time


@pytest.mark.asyncio
async def test_backtest_execution(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test clock execution in backtest mode."""
    clock.add_processor(mock_processor)

    async with clock:
        await clock.run_til(clock.start_time + 5)

    assert mock_processor.start_called
    assert mock_processor.tick_count == 5
    assert mock_processor.stop_called
    assert mock_processor.last_timestamp == clock.start_time + 5


@pytest.mark.asyncio
async def test_fast_forward(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test fast forward functionality in backtest mode."""
    clock.add_processor(mock_processor)

    async with clock:
        await clock.fast_forward(5)

    assert mock_processor.tick_count == 5
    assert mock_processor.last_timestamp == clock.start_time + 5


@pytest.mark.asyncio
async def test_backtest_end_time(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test that backtest clock stops at end_time."""
    clock.add_processor(mock_processor)

    async with clock:
        # Try to run past end_time
        with pytest.raises(ClockError):
            await clock.run_til(clock.end_time + 1)

        # Run to end_time should succeed
        await clock.run_til(clock.end_time)
        assert mock_processor.last_timestamp == clock.end_time


@pytest.mark.asyncio
async def test_backtest_deterministic(clock: BacktestClock) -> None:
    """Test that backtest execution is deterministic."""
    processors = [MockProcessor(f"mock{i}") for i in range(3)]
    for p in processors:
        p.sleep_time = 0.1  # Add some sleep to test determinism
        clock.add_processor(p)

    async with clock:
        await clock.run_til(clock.start_time + 1)

    # All processors should have executed exactly once
    for p in processors:
        assert p.tick_count == 1
        assert p.last_timestamp == clock.start_time + 1
