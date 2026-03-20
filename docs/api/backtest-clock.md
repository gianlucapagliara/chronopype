# BacktestClock

**Module:** `chronopype.clocks.backtest`

**Inherits:** [`BaseClock`](base-clock.md)

A clock implementation for deterministic historical time simulation. Ticks advance instantly without waiting for wall-clock time.

## Constructor

```python
BacktestClock(
    config: ClockConfig,
    error_callback: Callable[[TickProcessor, Exception], None] | None = None
)
```

**Raises:** `ClockError` if `config.clock_mode` is not `ClockMode.BACKTEST` or `end_time` is not set.

## Methods

### `run()`

Run the clock from `start_time` to `end_time`, executing all ticks.

### `run_til(target_time)`

Run the clock until `target_time` is reached. Creates an internal async task.

**Raises:** `ClockError` if not in context, already running, or `target_time` exceeds `end_time`.

### `step(n=1)`

Advance the clock by exactly `n` ticks. Returns the new current timestamp.

```python
new_time = await clock.step()      # advance 1 tick
new_time = await clock.step(10)    # advance 10 ticks
```

**Raises:** `ClockError` if not in context, `n < 1`, or advancing would exceed `end_time`.

### `step_to(target_time)`

Advance the clock tick-by-tick until reaching `target_time`. Returns the new current timestamp.

```python
new_time = await clock.step_to(1700001000.0)
```

**Raises:** `ClockError` if not in context or `target_time` exceeds `end_time`.

### `fast_forward(seconds)`

Fast forward the clock by the specified number of seconds, executing all intermediate ticks.

```python
await clock.fast_forward(3600.0)  # advance 1 hour
```

**Raises:** `ClockError` if not in context or advancing would exceed `end_time`.

## Example

```python
import asyncio
from chronopype import ClockConfig, ClockMode
from chronopype.clocks import BacktestClock
from chronopype.processors import TickProcessor


class StrategyProcessor(TickProcessor):
    def __init__(self) -> None:
        super().__init__()
        self.signals: list[float] = []

    async def async_tick(self, timestamp: float) -> None:
        # Simulate strategy logic
        if some_condition(timestamp):
            self.signals.append(timestamp)


async def main():
    config = ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        start_time=1700000000.0,
        end_time=1700086400.0,  # 1 day
        tick_size=60.0,          # 1-minute ticks
    )

    strategy = StrategyProcessor()

    async with BacktestClock(config) as clock:
        clock.add_processor(strategy)

        # Step through the first hour manually
        for _ in range(60):
            await clock.step()
            if strategy.signals:
                print(f"Signal at {strategy.signals[-1]}")

        # Fast forward the rest
        await clock.run()

    print(f"Total signals: {len(strategy.signals)}")


asyncio.run(main())
```

## Step-by-Step Testing

The `step` and `step_to` methods are particularly useful for testing strategies where you need to inspect or modify state between ticks:

```python
async with BacktestClock(config) as clock:
    clock.add_processor(strategy)

    # Step to a specific event time
    await clock.step_to(event_timestamp)

    # Inspect state
    assert strategy.state_is_valid()

    # Continue stepping
    await clock.step(5)
```
