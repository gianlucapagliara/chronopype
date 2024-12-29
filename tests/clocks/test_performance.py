import asyncio

import pytest

from chronopype.clocks.base import BaseClock
from tests.conftest import MockProcessor


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
def test_processor_stats(
    clock_fixture: str, request: pytest.FixtureRequest, mock_processor: MockProcessor
) -> None:
    """Test processor statistics collection."""
    clock: BaseClock = request.getfixturevalue(clock_fixture)
    clock.add_processor(mock_processor)

    # Run some ticks
    async def run_clock() -> None:
        async with clock:
            await clock.run_til(clock.current_timestamp + 3)

    asyncio.run(run_clock())

    stats = clock.get_processor_stats(mock_processor)
    assert stats is not None
    assert stats["total_ticks"] >= 3
    assert stats["successful_ticks"] >= 3
    assert stats["failed_ticks"] == 0
    assert stats["avg_execution_time"] > 0
    assert stats["max_execution_time"] > 0


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
@pytest.mark.asyncio
async def test_lagging_processors(
    clock_fixture: str, request: pytest.FixtureRequest
) -> None:
    """Test detection of lagging processors."""
    clock: BaseClock = request.getfixturevalue(clock_fixture)
    processors = [MockProcessor(f"mock{i}") for i in range(3)]

    # Add processors with different sleep times
    for i, p in enumerate(processors):
        p.sleep_time = i * 0.1
        clock.add_processor(p)

    async with clock:
        await clock.run_til(clock.current_timestamp + 1)

    # Check lagging processors
    lagging = clock.get_lagging_processors(0.1)  # Small threshold
    assert len(lagging) > 0

    lagging = clock.get_lagging_processors(100)  # Large threshold
    assert len(lagging) == 0


@pytest.mark.parametrize("clock_fixture", ["clock", "realtime_clock"])
@pytest.mark.asyncio
async def test_processor_performance_tracking(
    clock_fixture: str, request: pytest.FixtureRequest, mock_processor: MockProcessor
) -> None:
    """Test processor performance tracking."""
    clock: BaseClock = request.getfixturevalue(clock_fixture)
    clock.add_processor(mock_processor)

    # Set varying execution times
    times = [0.1, 0.2, 0.3]
    time_index = 0

    async def timed_tick(timestamp: float) -> None:
        nonlocal time_index
        await asyncio.sleep(times[time_index % len(times)])
        time_index += 1

    mock_processor.async_tick = timed_tick  # type: ignore

    async with clock:
        await clock.run_til(clock.current_timestamp + len(times))

    # Check performance metrics
    mean, std_dev, percentile_95 = clock.get_processor_performance(mock_processor)
    assert 0.1 < mean < 0.3
    assert std_dev > 0
    assert 0.2 < percentile_95 < 0.4

    # Check state statistics
    state = clock.get_processor_state(mock_processor)
    assert state is not None
    assert state.avg_execution_time == mean
    assert state.std_dev_execution_time == std_dev
    assert state.error_rate == 0.0
