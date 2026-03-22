# Performance Monitoring

Chronopype includes built-in performance tracking for all processors. Use it to detect slow processors, track execution trends, and diagnose bottlenecks.

## Execution Statistics

Each processor automatically records execution times in a rolling window:

```python
async with RealtimeClock(config) as clock:
    processor = MyProcessor()
    clock.add_processor(processor)
    await clock.run_til(config.start_time + 60)

    # Get performance tuple: (avg, std_dev, p95)
    avg, std, p95 = clock.get_processor_performance(processor)
    print(f"Avg: {avg:.4f}s, StdDev: {std:.4f}s, P95: {p95:.4f}s")
```

## Detailed Statistics

Get a full stats dictionary for any processor:

```python
stats = clock.get_processor_stats(processor)
```

The returned dictionary contains:

| Key | Type | Description |
|-----|------|-------------|
| `total_ticks` | `int` | Total tick attempts |
| `successful_ticks` | `int` | Successful executions |
| `failed_ticks` | `int` | Failed executions |
| `error_count` | `int` | Total errors encountered |
| `consecutive_errors` | `int` | Current consecutive error streak |
| `retry_count` | `int` | Current retry count |
| `max_consecutive_retries` | `int` | Highest retry streak observed |
| `avg_execution_time` | `float` | Average execution time |
| `max_execution_time` | `float` | Maximum execution time |
| `std_dev_execution_time` | `float` | Standard deviation of execution times |
| `error_rate` | `float` | Error percentage (`error_count / total_ticks * 100`) |
| `last_error` | `str \| None` | Most recent error message |
| `last_error_time` | `datetime \| None` | When the last error occurred |
| `last_success_time` | `datetime \| None` | When the last success occurred |

## Detecting Lagging Processors

Identify processors whose average execution time exceeds a threshold:

```python
# Find processors averaging more than 0.5 seconds per tick
lagging = clock.get_lagging_processors(threshold=0.5)
for processor in lagging:
    avg, _, _ = clock.get_processor_performance(processor)
    print(f"{processor}: avg {avg:.4f}s")
```

This is useful for monitoring production systems and detecting degradation.

## Percentile Statistics

The `ProcessorState` model supports arbitrary percentile calculations:

```python
state = processor.state
p50 = state.get_execution_percentile(50)   # median
p90 = state.get_execution_percentile(90)
p99 = state.get_execution_percentile(99)
```

## Rolling Window

Execution times are stored in a rolling window controlled by `stats_window_size`:

```python
# In ClockConfig (applies to all processors added to this clock)
config = ClockConfig(
    clock_mode=ClockMode.REALTIME,
    start_time=time.time(),
    tick_size=1.0,
    stats_window_size=500,  # track last 500 execution times
)

# Or per-processor
class MyProcessor(TickProcessor):
    def __init__(self) -> None:
        super().__init__(stats_window_size=500)
```

A larger window gives more stable statistics but uses more memory. The default of 100 is suitable for most use cases.

## Error Rate Monitoring

Track processor reliability:

```python
state = processor.state
print(f"Error rate: {state.error_rate:.1f}%")
print(f"Total: {state.total_ticks}, Success: {state.successful_ticks}, Failed: {state.failed_ticks}")
```
