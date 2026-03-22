# ProcessorStats

**Module:** `chronopype.clocks.base`

A `TypedDict` providing a type-safe statistics dictionary for a processor. Returned by [`BaseClock.get_processor_stats()`](base-clock.md#get_processor_statsprocessor).

## Definition

```python
class ProcessorStats(TypedDict):
    total_ticks: int
    successful_ticks: int
    failed_ticks: int
    error_count: int
    consecutive_errors: int
    retry_count: int
    max_consecutive_retries: int
    avg_execution_time: float
    max_execution_time: float
    std_dev_execution_time: float
    error_rate: float
    last_error: str | None
    last_error_time: datetime | None
    last_success_time: datetime | None
```

## Fields

| Key | Type | Description |
|-----|------|-------------|
| `total_ticks` | `int` | Total tick attempts (successful + failed) |
| `successful_ticks` | `int` | Number of successful executions |
| `failed_ticks` | `int` | Number of failed executions |
| `error_count` | `int` | Total errors encountered |
| `consecutive_errors` | `int` | Current consecutive error streak |
| `retry_count` | `int` | Current retry count |
| `max_consecutive_retries` | `int` | Highest retry streak observed |
| `avg_execution_time` | `float` | Average execution time in seconds |
| `max_execution_time` | `float` | Maximum execution time in seconds |
| `std_dev_execution_time` | `float` | Standard deviation of execution times |
| `error_rate` | `float` | Error percentage (`error_count / total_ticks * 100`) |
| `last_error` | `str \| None` | Most recent error message |
| `last_error_time` | `datetime \| None` | When the last error occurred |
| `last_success_time` | `datetime \| None` | When the last success occurred |

## Example

```python
from chronopype import ClockConfig, ClockMode
from chronopype.clocks import RealtimeClock

async with RealtimeClock(config) as clock:
    clock.add_processor(processor)
    await clock.run_til(config.start_time + 60)

    stats = clock.get_processor_stats(processor)
    if stats is not None:
        print(f"Total ticks: {stats['total_ticks']}")
        print(f"Avg time: {stats['avg_execution_time']:.4f}s")
        print(f"Error rate: {stats['error_rate']:.1f}%")
```
