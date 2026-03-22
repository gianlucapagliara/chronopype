# ProcessorState

**Module:** `chronopype.processors.models`

A frozen Pydantic model that tracks processor execution statistics. Since it is immutable, state updates return new instances.

## Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `last_timestamp` | `float \| None` | `None` | Last processed timestamp |
| `is_active` | `bool` | `False` | Whether the processor is active |
| `retry_count` | `int` | `0` | Current retry count |
| `max_consecutive_retries` | `int` | `0` | Highest retry streak observed |
| `execution_times` | `list[float]` | `[]` | Rolling window of execution durations |
| `error_count` | `int` | `0` | Total errors recorded |
| `consecutive_errors` | `int` | `0` | Current consecutive error streak |
| `last_error` | `str \| None` | `None` | Last error message |
| `last_error_time` | `datetime \| None` | `None` | When the last error occurred |
| `last_success_time` | `datetime \| None` | `None` | When the last success occurred |

## Computed Properties

| Property | Type | Description |
|----------|------|-------------|
| `total_ticks` | `int` | `len(execution_times) + error_count` |
| `successful_ticks` | `int` | `len(execution_times)` |
| `failed_ticks` | `int` | Same as `error_count` |
| `total_execution_time` | `float` | Sum of all execution times |
| `avg_execution_time` | `float` | Average execution time (0 if no executions) |
| `max_execution_time` | `float` | Maximum execution time (0 if no executions) |
| `std_dev_execution_time` | `float` | Standard deviation of execution times |
| `error_rate` | `float` | Error percentage: `error_count / total_ticks * 100` |

## Methods

### `get_execution_percentile(percentile)`

Get the execution time at a given percentile (0-100).

```python
state.get_execution_percentile(50)   # median
state.get_execution_percentile(95)   # p95
state.get_execution_percentile(99)   # p99
```

Returns `0.0` if no execution times have been recorded.

### `update_execution_time(execution_time, window_size)`

Returns a new `ProcessorState` with the execution time appended. Maintains the rolling window by trimming oldest entries. Resets `consecutive_errors` on success (note: `retry_count` is reset separately via `reset_retries()`).

### `record_error(error, timestamp)`

Returns a new `ProcessorState` with updated error tracking (increments `error_count` and `consecutive_errors`).

### `update_retry_count(retry_count)`

Returns a new `ProcessorState` with updated retry count. Tracks `max_consecutive_retries`.

### `reset_retries()`

Returns a new `ProcessorState` with `retry_count` reset to 0.

## Immutability

`ProcessorState` is a frozen model. All mutation methods return new instances:

```python
state = ProcessorState()
new_state = state.update_execution_time(0.05, window_size=100)

# state is unchanged
assert len(state.execution_times) == 0
assert len(new_state.execution_times) == 1
```
