# TickProcessor

**Module:** `chronopype.processors.base`

Base class for all tick processors. Subclass this to define custom logic that runs on each clock tick.

## Constructor

```python
TickProcessor(stats_window_size: int = 100)
```

| Parameter | Description |
|-----------|-------------|
| `stats_window_size` | Rolling window size for execution time tracking |

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `state` | `ProcessorState` | Current processor state. Delegates to the clock-managed state when registered to a clock, otherwise returns the processor's own internal state |
| `current_timestamp` | `float` | Last processed timestamp, or `0` if never called |

## Methods

### `tick(timestamp)`

Synchronous tick handler. Override this for synchronous processing logic.

```python
def tick(self, timestamp: float) -> None:
    ...
```

Default implementation is a no-op.

### `async_tick(timestamp)`

Async tick handler. Override this for async processing logic.

```python
async def async_tick(self, timestamp: float) -> None:
    ...
```

Default implementation calls `tick(timestamp)`.

!!! note
    The clock always calls `async_tick`. If you only need synchronous logic, override `tick` --- the default `async_tick` will call it.

### `start(timestamp)`

Called by the clock when the processor is started. Marks the processor as active and sets `last_timestamp`.

```python
def start(self, timestamp: float) -> None:
    ...
```

### `stop()`

Called by the clock when the processor is stopped. Marks the processor as inactive.

```python
def stop(self) -> None:
    ...
```

### `pause()`

Pause the processor. Override for processors with background tasks (e.g., `NetworkProcessor`). Default is a no-op.

```python
def pause(self) -> None:
    ...
```

### `resume()`

Resume the processor. Override for processors with background tasks. Default is a no-op.

```python
def resume(self) -> None:
    ...
```

### `record_execution(execution_time)`

Record a successful execution with its duration. Also resets `retry_count` via `reset_retries()`. Called automatically by the clock.

```python
def record_execution(self, execution_time: float) -> None:
    ...
```

### `record_error(error, timestamp)`

Record an error occurrence. Called automatically by the clock.

```python
def record_error(self, error: Exception, timestamp: float) -> None:
    ...
```

## Example

```python
from chronopype.processors import TickProcessor


class DataCollector(TickProcessor):
    def __init__(self) -> None:
        super().__init__(stats_window_size=200)
        self.data: list[tuple[float, dict]] = []

    async def async_tick(self, timestamp: float) -> None:
        result = await fetch_data(timestamp)
        self.data.append((timestamp, result))

    def start(self, timestamp: float) -> None:
        super().start(timestamp)
        self.data = []  # reset on start

    def stop(self) -> None:
        super().stop()
        save_data(self.data)
```
