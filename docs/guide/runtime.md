# Runtime

The `ClockRuntime` provides a higher-level API for managing clock lifecycle. It handles context entry/exit, async task management, and threaded execution, so you can focus on your processors rather than boilerplate.

## When to Use Runtime vs Direct Clock

| Scenario | Use |
|----------|-----|
| Simple async script | Direct `async with Clock(config)` |
| Need threaded clock for sync code | `ClockRuntime` with `start_threaded()` |
| Backtest with manual stepping | `ClockRuntime` with `backtest_til()` |
| Want unified lifecycle management | `ClockRuntime` |

## Configuration

`ClockRuntimeConfig` composes a `ClockConfig` with runtime-specific parameters:

```python
from chronopype import ClockConfig, ClockMode, ClockRuntimeConfig

config = ClockRuntimeConfig(
    clock_config=ClockConfig(
        clock_mode=ClockMode.REALTIME,
        tick_size=1.0,
        start_time=0.0,
    ),
    thread_stop_timeout_seconds=3.0,
    clock_poll_interval_seconds=0.1,
)
```

Shortcut properties (`config.clock_mode`, `config.tick_size`, etc.) are available for convenience.

## Async Mode

### Context Manager

The simplest way to use `ClockRuntime`:

```python
from chronopype import ClockRuntime, ClockRuntimeConfig, ClockConfig, ClockMode

config = ClockRuntimeConfig(
    clock_config=ClockConfig(
        clock_mode=ClockMode.REALTIME,
        tick_size=1.0,
    )
)

async with ClockRuntime(config=config) as rt:
    # Clock is running — processors are ticking
    await asyncio.sleep(10)
# Clock is stopped
```

### Manual Start/Stop

```python
rt = ClockRuntime(config=config)
await rt.start()
# ... do work ...
await rt.stop(timeout=5.0)
```

### Pre-built Clock

You can pass a pre-built clock instead of a config. The runtime determines the mode from the actual clock type via `isinstance`, not from the config:

```python
clock = BacktestClock(clock_config)
clock.add_processor(my_processor)

async with ClockRuntime(clock=clock) as rt:
    await rt.backtest_til(target_time)
```

## Backtest Mode

In backtest mode, `start()` enters the clock context (initializes processors) but does **not** create a background task. You drive the clock manually:

```python
from chronopype import (
    ClockConfig, ClockMode, ClockRuntime, ClockRuntimeConfig,
)
from chronopype.processors import TickProcessor


class MyStrategy(TickProcessor):
    async def async_tick(self, timestamp: float) -> None:
        # Your logic here
        pass


config = ClockRuntimeConfig(
    clock_config=ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        tick_size=1.0,
        start_time=1000.0,
        end_time=2000.0,
    )
)

async with ClockRuntime(config=config) as rt:
    rt.clock.add_processor(MyStrategy())

    # Advance to specific timestamps
    await rt.backtest_til(1100.0)
    # Inspect state...
    await rt.backtest_til(1500.0)
```

For finer control (`step()`, `fast_forward()`), access the clock directly via `rt.clock`.

## Threaded Mode

For applications that need a clock running in the background from synchronous code:

```python
config = ClockRuntimeConfig(
    clock_config=ClockConfig(
        clock_mode=ClockMode.REALTIME,
        tick_size=1.0,
    )
)
rt = ClockRuntime(config=config)

# Start in a background thread
rt.start_threaded(on_error_callback=lambda msg: print(f"Error: {msg}"))

# get_clock_loop() is available immediately after start_threaded()
loop = rt.get_clock_loop()

# Schedule coroutines from the main thread
import asyncio
future = asyncio.run_coroutine_threadsafe(some_coro(), loop)

# Stop when done
rt.stop_threaded()
```

!!! note
    Threaded mode is only supported for `RealtimeClock`. Attempting to use it with a `BacktestClock` raises `ClockRuntimeError`.

## Error Handling

- **`ClockRuntimeError`**: Raised for runtime-specific issues (wrong clock type, invalid operations).
- **Processor errors**: Propagate through `backtest_til()` in backtest mode.
- **Task errors**: In realtime async mode, check `rt.task_error` to detect if the clock task crashed. The `is_running` property accurately reflects task state --- it returns `False` when the underlying task has failed.
- **Thread errors**: Use the `on_error_callback` parameter in `start_threaded()`.

## Monitoring

```python
# Check if the runtime is active
rt.is_running  # True if clock is ticking

# Check for task failures
if rt.task_error is not None:
    print(f"Clock failed: {rt.task_error}")

# Access the underlying clock for detailed stats
stats = rt.clock.get_processor_stats(processor)
```
