import pytest

from chronopype.clocks.backtest import BacktestClock
from chronopype.clocks.config import ClockConfig
from chronopype.exceptions import ClockError
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
async def test_step_single(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test stepping the clock by a single tick."""
    clock.add_processor(mock_processor)

    async with clock:
        result = await clock.step()
        assert result == clock.start_time + 1.0
        assert mock_processor.tick_count == 1
        assert mock_processor.last_timestamp == clock.start_time + 1.0
        assert clock.current_timestamp == clock.start_time + 1.0


@pytest.mark.asyncio
async def test_step_multiple(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test stepping the clock by multiple ticks."""
    clock.add_processor(mock_processor)

    async with clock:
        result = await clock.step(3)
        assert result == clock.start_time + 3.0
        assert mock_processor.tick_count == 3
        assert mock_processor.last_timestamp == clock.start_time + 3.0


@pytest.mark.asyncio
async def test_step_sequential_calls(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test making multiple sequential step calls with interleaved logic."""
    clock.add_processor(mock_processor)

    async with clock:
        await clock.step()
        assert mock_processor.tick_count == 1
        assert mock_processor.last_timestamp == clock.start_time + 1.0

        await clock.step(2)
        assert mock_processor.tick_count == 3
        assert mock_processor.last_timestamp == clock.start_time + 3.0

        await clock.step()
        assert mock_processor.tick_count == 4
        assert mock_processor.last_timestamp == clock.start_time + 4.0


@pytest.mark.asyncio
async def test_step_past_end_time(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test that stepping past end_time raises ClockError."""
    clock.add_processor(mock_processor)

    async with clock:
        with pytest.raises(ClockError):
            # clock has 10 ticks (1000 to 1010), stepping 11 should fail
            await clock.step(11)


@pytest.mark.asyncio
async def test_step_invalid_n(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test that step with n < 1 raises ClockError."""
    clock.add_processor(mock_processor)

    async with clock:
        with pytest.raises(ClockError):
            await clock.step(0)
        with pytest.raises(ClockError):
            await clock.step(-1)


@pytest.mark.asyncio
async def test_step_without_context(clock: BacktestClock) -> None:
    """Test that step outside a context raises ClockError."""
    with pytest.raises(ClockError):
        await clock.step()


@pytest.mark.asyncio
async def test_step_to_basic(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test stepping the clock to a target time."""
    clock.add_processor(mock_processor)

    async with clock:
        result = await clock.step_to(clock.start_time + 5)
        assert result == clock.start_time + 5.0
        assert mock_processor.tick_count == 5
        assert mock_processor.last_timestamp == clock.start_time + 5.0


@pytest.mark.asyncio
async def test_step_to_sequential(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test multiple sequential step_to calls."""
    clock.add_processor(mock_processor)

    async with clock:
        await clock.step_to(clock.start_time + 3)
        assert mock_processor.tick_count == 3

        await clock.step_to(clock.start_time + 7)
        assert mock_processor.tick_count == 7

        await clock.step_to(clock.end_time)
        assert mock_processor.tick_count == 10


@pytest.mark.asyncio
async def test_step_to_no_advance(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test step_to with a target at or before current time returns immediately."""
    clock.add_processor(mock_processor)

    async with clock:
        result = await clock.step_to(clock.start_time)
        assert result == clock.start_time
        assert mock_processor.tick_count == 0


@pytest.mark.asyncio
async def test_step_to_past_end_time(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test that step_to past end_time raises ClockError."""
    clock.add_processor(mock_processor)

    async with clock:
        with pytest.raises(ClockError):
            await clock.step_to(clock.end_time + 1)


@pytest.mark.asyncio
async def test_step_to_without_context(clock: BacktestClock) -> None:
    """Test that step_to outside a context raises ClockError."""
    with pytest.raises(ClockError):
        await clock.step_to(clock.start_time + 1)


@pytest.mark.asyncio
async def test_step_does_not_set_running(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test that step/step_to do not set the clock to running state."""
    clock.add_processor(mock_processor)

    async with clock:
        await clock.step(2)
        # After step, clock should not be in "running" state,
        # so run_til should still work
        await clock.run_til(clock.start_time + 5)
        assert mock_processor.tick_count == 5


@pytest.mark.asyncio
async def test_step_mixed_with_run_til(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test interleaving step() and run_til() calls."""
    clock.add_processor(mock_processor)

    async with clock:
        await clock.step(3)
        assert mock_processor.tick_count == 3

        await clock.run_til(clock.start_time + 7)
        assert mock_processor.tick_count == 7


@pytest.mark.asyncio
async def test_step_to_exact_end_time(
    clock: BacktestClock, mock_processor: MockProcessor
) -> None:
    """Test stepping to exactly end_time succeeds."""
    clock.add_processor(mock_processor)

    async with clock:
        result = await clock.step_to(clock.end_time)
        assert result == clock.end_time
        assert mock_processor.tick_count == 10


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
