# RealtimeClock

**Module:** `chronopype.clocks.realtime`

**Inherits:** [`BaseClock`](base-clock.md)

A clock implementation that synchronizes with wall-clock time. It handles drift compensation automatically.

## Constructor

```python
RealtimeClock(
    config: ClockConfig,
    error_callback: Callable[[TickProcessor, Exception], None] | None = None
)
```

**Raises:** `ClockError` if `config.clock_mode` is not `ClockMode.REALTIME`.

## Methods

### `run()`

Run the clock indefinitely. Each tick fires at `tick_size` intervals. The clock compensates for drift --- if a tick takes longer than the tick interval, the next tick fires immediately.

Cancel via `asyncio.Task.cancel()` or by exiting the context manager.

### `run_til(target_time)`

Run the clock until `target_time` is reached. The target is in the clock's timestamp domain; internally the clock calculates the wall-clock duration as `target_time - current_tick` and runs for that duration.

**Raises:** `ClockError` if the clock is already running or not in a context.

## Example

```python
import asyncio
import time
from chronopype import ClockConfig, ClockMode
from chronopype.clocks import RealtimeClock
from chronopype.processors import TickProcessor


class HeartbeatProcessor(TickProcessor):
    async def async_tick(self, timestamp: float) -> None:
        print(f"Heartbeat at {timestamp:.2f}")


async def main():
    config = ClockConfig(
        clock_mode=ClockMode.REALTIME,
        start_time=time.time(),
        tick_size=1.0,
    )

    async with RealtimeClock(config) as clock:
        clock.add_processor(HeartbeatProcessor())

        # Run for 30 seconds
        await clock.run_til(config.start_time + 30)


asyncio.run(main())
```

## Drift Handling

When a processor takes longer than `tick_size`, the clock:

1. Detects the drift (elapsed time - tick_size)
2. Fires the next tick immediately (no sleep)
3. Continues compensating until caught up

This ensures the total number of ticks over time remains accurate, even if individual ticks are delayed.
