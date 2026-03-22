# BaseClock

**Module:** `chronopype.clocks.base`

Abstract base class for all clock implementations. Inherits from `AsyncContextManager` and `MultiPublisher` (from eventspype).

## Events

```python
start_publication: EventPublication  # emits ClockStartEvent
tick_publication: EventPublication   # emits ClockTickEvent
stop_publication: EventPublication   # emits ClockStopEvent
```

### Event Dataclasses

```python
@dataclass
class ClockStartEvent:
    timestamp: float
    mode: ClockMode
    tick_size: float

@dataclass
class ClockTickEvent:
    timestamp: float
    tick_counter: int
    processors: list[TickProcessor]

@dataclass
class ClockStopEvent:
    timestamp: float
    total_ticks: int
    final_states: dict[TickProcessor, ProcessorState]
```

## Constructor

```python
BaseClock(
    config: ClockConfig,
    error_callback: Callable[[TickProcessor, Exception], None] | None = None
)
```

| Parameter | Description |
|-----------|-------------|
| `config` | Clock configuration |
| `error_callback` | Optional callback invoked when a processor fails after all retries |

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `config` | `ClockConfig` | The clock configuration |
| `clock_mode` | `ClockMode` | Current mode (`REALTIME` or `BACKTEST`) |
| `start_time` | `float` | Configured start time |
| `end_time` | `float` | Configured end time |
| `tick_size` | `float` | Interval between ticks |
| `processors` | `list[TickProcessor]` | All registered processors |
| `current_timestamp` | `float` | Current clock timestamp |
| `tick_counter` | `int` | Number of ticks processed |
| `processor_states` | `dict[TickProcessor, ProcessorState]` | Copy of all processor states |
| `is_in_context` | `bool` | Whether the clock is currently inside an async context |

## Processor Management

### `add_processor(processor)`

Add a processor to the clock. If the clock is already in context, `start()` is called on the processor immediately.

**Raises:** `ClockError` if the processor is already registered, already belongs to another clock, or fails to start.

### `remove_processor(processor)`

Remove a processor from the clock. Calls `stop()` on the processor.

**Raises:** `ClockError` if the processor is not registered or fails to stop.

### `pause_processor(processor)`

Pause a processor. It remains registered but is skipped during tick execution. Calls `processor.pause()` to allow processors with background tasks (e.g., `NetworkProcessor`) to suspend them.

**Raises:** `ClockError` if the processor is not registered.

### `resume_processor(processor)`

Resume a paused processor. Calls `processor.resume()` to allow processors with background tasks to restart them.

**Raises:** `ClockError` if the processor is not registered.

### `get_processor_state(processor)`

Returns the `ProcessorState` for a processor, or `None` if not registered.

### `get_active_processors()`

Returns a list of all processors currently marked as active.

### `get_lagging_processors(threshold)`

Returns processors whose average execution time exceeds `threshold` seconds.

## Execution

### `run()` (abstract)

Run the clock. Implementation-specific behavior:

- `RealtimeClock`: runs indefinitely until cancelled
- `BacktestClock`: runs from `start_time` to `end_time`

### `run_til(target_time)` (abstract)

Run the clock until `target_time` is reached.

**Raises:** `ClockError` if the clock is already running.

### `shutdown(timeout=None)`

Shutdown the clock and stop all processors. Awaits async cleanup for processors that support it (e.g., `NetworkProcessor`).

!!! note
    The `timeout` parameter is accepted but currently unused.

## Performance

### `get_processor_performance(processor)`

Returns a tuple `(avg_time, std_dev, p95)` for the processor's execution times.

### `get_processor_stats(processor)`

Returns a `ProcessorStats` typed dictionary with detailed statistics, or `None` if the processor is not registered. See [Performance Monitoring](../guide/performance.md) for the full list of keys.

## Context Manager

```python
async with clock as c:
    # __aenter__: starts all processors, emits ClockStartEvent
    ...
# __aexit__: stops all processors, emits ClockStopEvent
```

**Raises:** `ClockContextError` if already in context or running.
