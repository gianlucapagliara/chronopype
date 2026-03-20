# Processors

Processors define the work that executes on each clock tick. They are the primary extension point in chronopype.

## Creating a Processor

Subclass `TickProcessor` and override `async_tick` (or `tick` for synchronous work):

```python
from chronopype.processors import TickProcessor


class MyProcessor(TickProcessor):
    async def async_tick(self, timestamp: float) -> None:
        # Your logic here --- runs on every clock tick
        await self.fetch_data(timestamp)
        await self.process(timestamp)
```

For synchronous processors, override `tick` instead:

```python
class SyncProcessor(TickProcessor):
    def tick(self, timestamp: float) -> None:
        print(f"Processing at {timestamp}")
```

!!! note
    The default `async_tick` calls `tick()`, so you only need to override one.

## Processor Lifecycle

A processor goes through the following states:

1. **Created** --- instantiated but not yet attached to a clock
2. **Started** --- `start(timestamp)` is called when the clock context opens
3. **Active** --- receiving ticks from the clock
4. **Paused** --- registered but skipping ticks
5. **Stopped** --- `stop()` is called when the clock context closes

```python
processor = MyProcessor()

# The clock manages the lifecycle automatically:
async with RealtimeClock(config) as clock:
    clock.add_processor(processor)   # start() is called
    # ... processor receives ticks ...
# stop() is called on context exit
```

## State Tracking

Every processor maintains a `ProcessorState` (a frozen Pydantic model) that tracks execution statistics:

```python
processor = MyProcessor()

# After running with a clock:
state = processor.state

# Execution stats
state.total_ticks           # total tick attempts
state.successful_ticks      # successful executions
state.failed_ticks          # failed executions
state.avg_execution_time    # average execution time
state.max_execution_time    # maximum execution time
state.error_rate            # error percentage

# Error tracking
state.error_count           # total errors
state.consecutive_errors    # current error streak
state.last_error            # last error message
state.last_error_time       # when last error occurred

# Retry tracking
state.retry_count           # current retry count
state.max_consecutive_retries  # highest retry streak
```

## Error Handling and Retries

The clock automatically retries failed processors with exponential backoff:

```python
config = ClockConfig(
    clock_mode=ClockMode.REALTIME,
    start_time=time.time(),
    tick_size=1.0,
    max_retries=3,          # retry up to 3 times
    processor_timeout=2.0,  # timeout per execution
)
```

The backoff formula is `0.1 * 2^(retry - 1)` seconds. If all retries are exhausted, the error callback is invoked (if set) and execution continues to the next tick.

## Concurrent Execution

By default, processors execute sequentially. Enable concurrent execution for independent processors:

```python
config = ClockConfig(
    clock_mode=ClockMode.REALTIME,
    start_time=time.time(),
    tick_size=1.0,
    concurrent_processors=True,
)
```

With concurrent execution, all active processors run in parallel using `asyncio.gather`.

!!! warning
    Ensure your processors are safe for concurrent execution. Avoid shared mutable state between processors without proper synchronization.

## Custom Initialization

Pass `stats_window_size` to control the rolling window for execution time statistics:

```python
class MyProcessor(TickProcessor):
    def __init__(self) -> None:
        super().__init__(stats_window_size=200)  # track last 200 ticks

    async def async_tick(self, timestamp: float) -> None:
        ...
```

## Accessing Timestamp

The `current_timestamp` property returns the last timestamp the processor was called with:

```python
processor = MyProcessor()
# After ticks have been processed:
print(processor.current_timestamp)  # last tick timestamp
```
