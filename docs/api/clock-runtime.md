# ClockRuntime

**Module:** `chronopype.runtime.clock_runtime`

Manages clock lifecycle: initialization, async start/stop, and threaded mode. Can be used as an async context manager or with explicit `start()`/`stop()` calls.

## Constructor

```python
ClockRuntime(
    config: ClockRuntimeConfig | None = None,
    clock: BaseClock | None = None,
)
```

| Parameter | Description |
|-----------|-------------|
| `config` | Runtime configuration. Defaults to `ClockRuntimeConfig()` (realtime, 1s tick). |
| `clock` | Pre-built clock instance. Takes precedence over the config's `clock_config` for clock construction. |

## Properties

### `config`

```python
@property
def config(self) -> ClockRuntimeConfig
```

Return the runtime configuration.

### `clock`

```python
@property
def clock(self) -> BaseClock
```

Return the underlying clock instance.

### `is_running`

```python
@property
def is_running(self) -> bool
```

`True` if the clock is running. Checks the actual state of async tasks, threads, and context --- a crashed task correctly returns `False`.

### `task_error`

```python
@property
def task_error(self) -> BaseException | None
```

Return the exception from a failed clock task (realtime async mode), or `None` if the task is healthy or not started.

## Methods

### `start()`

```python
async def start(self) -> None
```

Start the clock. Behavior depends on the clock type (determined via `isinstance`, not the config):

- **BacktestClock**: Enters the clock context (initializes processors) but does not create a background task. Drive the clock manually with `backtest_til()`.
- **RealtimeClock**: Enters the clock context and creates an async task that runs `clock.run()`.

Idempotent --- calling `start()` on an already-started runtime is a no-op.

### `stop(timeout=None)`

```python
async def stop(self, timeout: float | None = None) -> None
```

Stop the clock. Cancels any async task and exits the clock context. Safe to call without a prior `start()`, and safe to call multiple times.

| Parameter | Description |
|-----------|-------------|
| `timeout` | Max seconds to wait for task cancellation. Defaults to `config.thread_stop_timeout_seconds`. |

### `backtest_til(target_time)`

```python
async def backtest_til(self, target_time: float) -> None
```

Advance a backtest clock to `target_time`. When the clock context is active, delegates to `BacktestClock.step_to()`. Without context, updates the raw timestamp (with end-time validation).

**Raises:**

- `ClockRuntimeError` if the clock is not a `BacktestClock`.
- `ClockRuntimeError` if `target_time` exceeds `end_time` (without context).
- `ClockError` if `target_time` exceeds `end_time` (with context, via `step_to`).

### `start_threaded(on_error_callback=None)`

```python
def start_threaded(
    self,
    on_error_callback: Callable[[str], None] | None = None,
) -> None
```

Start the clock in a dedicated daemon thread with its own event loop. Only supported for `RealtimeClock`. The event loop is available via `get_clock_loop()` immediately after this method returns.

Idempotent --- calling on an already-running thread is a no-op.

**Raises:** `ClockRuntimeError` if the clock is not a `RealtimeClock`.

### `stop_threaded()`

```python
def stop_threaded(self) -> None
```

Stop the clock thread. Signals the stop event and joins the thread with a timeout. Logs a warning if the thread does not stop within the timeout. Safe to call without a prior `start_threaded()`.

### `get_clock_loop()`

```python
def get_clock_loop(self) -> asyncio.AbstractEventLoop | None
```

Return the clock thread's event loop when in threaded mode, else `None`. Use with `asyncio.run_coroutine_threadsafe()` to schedule work on the clock thread.

## Async Context Manager

```python
async with ClockRuntime(config=config) as rt:
    # clock is running
    ...
# clock is stopped
```

Equivalent to calling `start()` on entry and `stop()` on exit.

## Example

```python
import asyncio
from chronopype import (
    ClockConfig, ClockMode, ClockRuntime, ClockRuntimeConfig,
)
from chronopype.processors import TickProcessor


class Logger(TickProcessor):
    async def async_tick(self, timestamp: float) -> None:
        print(f"tick {timestamp:.1f}")


async def main():
    config = ClockRuntimeConfig(
        clock_config=ClockConfig(
            clock_mode=ClockMode.BACKTEST,
            tick_size=1.0,
            start_time=100.0,
            end_time=200.0,
        )
    )

    async with ClockRuntime(config=config) as rt:
        rt.clock.add_processor(Logger())
        await rt.backtest_til(110.0)
        print(f"Current: {rt.clock.current_timestamp}")


asyncio.run(main())
```
