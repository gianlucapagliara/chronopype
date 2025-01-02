import asyncio
import time

import pytest

from chronopype.clocks.config import ClockConfig
from chronopype.clocks.realtime import RealtimeClock
from tests.conftest import MockProcessor


def test_realtime_config(realtime_config: ClockConfig) -> None:
    """Test realtime clock configuration."""
    clock = RealtimeClock(realtime_config)
    assert clock.tick_size == 0.1
    assert clock.current_timestamp > 0  # Should be initialized to current time


@pytest.mark.asyncio
async def test_realtime_execution(
    realtime_clock: RealtimeClock, mock_processor: MockProcessor
) -> None:
    """Test clock execution in realtime mode."""
    realtime_clock.add_processor(mock_processor)

    start_time = time.time()
    async with realtime_clock:
        # Run for a short time
        await asyncio.wait_for(
            realtime_clock.run_til(realtime_clock.current_timestamp + 0.3), timeout=1
        )
    end_time = time.time()

    assert mock_processor.start_called
    assert mock_processor.tick_count >= 2  # At least 2 ticks (0.3s / 0.1s tick size)
    assert mock_processor.stop_called
    assert 0.3 <= end_time - start_time <= 1.0  # Should take roughly the expected time


@pytest.mark.asyncio
async def test_realtime_drift_handling(
    realtime_clock: RealtimeClock, mock_processor: MockProcessor
) -> None:
    """Test handling of clock drift in realtime mode."""
    realtime_clock.add_processor(mock_processor)

    # Make processor take longer than tick size
    mock_processor.sleep_time = realtime_clock.tick_size * 2

    start_time = time.time()
    async with realtime_clock:
        # Run for a few ticks
        await asyncio.wait_for(
            realtime_clock.run_til(realtime_clock.current_timestamp + 1.0), timeout=2.0
        )
    end_time = time.time()

    # Check that we didn't fall too far behind
    actual_duration = end_time - start_time
    assert actual_duration < 2.0  # Should skip ticks rather than accumulating delay

    # Check that processor still executed
    assert mock_processor.tick_count > 0


@pytest.mark.asyncio
async def test_realtime_concurrent_execution(realtime_clock: RealtimeClock) -> None:
    """Test concurrent execution in realtime mode."""
    processors = [MockProcessor(f"mock{i}") for i in range(3)]
    for p in processors:
        p.sleep_time = 0.05  # Each processor takes half a tick
        realtime_clock.add_processor(p)

    start_time = time.time()
    async with realtime_clock:
        await asyncio.wait_for(
            realtime_clock.run_til(realtime_clock.current_timestamp + 0.3), timeout=1
        )
    end_time = time.time()

    # All processors should have executed
    for p in processors:
        assert p.tick_count >= 2  # At least 2 ticks
        assert p.last_timestamp is not None

    # Should complete in roughly the expected time
    assert 0.3 <= end_time - start_time <= 1.0


@pytest.mark.asyncio
async def test_realtime_late_processor(
    realtime_clock: RealtimeClock, mock_processor: MockProcessor
) -> None:
    """Test handling of processors that take too long."""
    realtime_clock.add_processor(mock_processor)

    # Make processor take much longer than tick size
    mock_processor.sleep_time = realtime_clock.tick_size * 5

    start_time = time.time()
    async with realtime_clock:
        # Run for a short time
        await asyncio.wait_for(
            realtime_clock.run_til(realtime_clock.current_timestamp + 0.3), timeout=1
        )
    end_time = time.time()

    # Should still complete in roughly the expected time
    assert end_time - start_time <= 1.0

    # Processor should have executed at least once
    assert mock_processor.tick_count >= 1
