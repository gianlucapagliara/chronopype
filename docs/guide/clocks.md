# Clocks

Clocks are the central abstraction in chronopype. They manage time progression, coordinate processors, and emit events at each lifecycle stage.

## Clock Modes

Chronopype provides two clock implementations:

| Mode | Class | Use Case |
|------|-------|----------|
| `ClockMode.REALTIME` | `RealtimeClock` | Live systems, real-time data processing |
| `ClockMode.BACKTEST` | `BacktestClock` | Historical simulation, strategy backtesting |

Both share the same `BaseClock` interface, so processors work identically in either mode.

## Configuration

All clocks are configured via `ClockConfig`:

```python
from chronopype import ClockConfig, ClockMode

config = ClockConfig(
    clock_mode=ClockMode.REALTIME,
    tick_size=1.0,              # seconds between ticks
    start_time=1700000000.0,    # UNIX timestamp
    end_time=0.0,               # 0 = no end (required > 0 for BACKTEST)
    processor_timeout=1.0,      # max seconds per processor tick
    max_retries=3,              # retry count for failed processors
    concurrent_processors=False, # True = run processors in parallel
    stats_window_size=100,      # rolling window for execution stats
)
```

`ClockConfig` is a frozen Pydantic model --- it cannot be modified after creation.

## Clock Lifecycle

Clocks use the async context manager protocol:

```python
async with RealtimeClock(config) as clock:
    # 1. __aenter__: emits ClockStartEvent, starts all processors
    clock.add_processor(my_processor)

    # 2. Run: executes ticks, emits ClockTickEvent per tick
    await clock.run_til(target_time)

    # 3. __aexit__: stops all processors, emits ClockStopEvent
```

### Events

The clock emits three events via the [eventspype](https://github.com/gianlucapagliara/eventspype) publication system:

| Event | When | Data |
|-------|------|------|
| `ClockStartEvent` | Context entry | `timestamp`, `mode`, `tick_size` |
| `ClockTickEvent` | Each tick | `timestamp`, `tick_counter`, `processors` |
| `ClockStopEvent` | Context exit | `timestamp`, `total_ticks`, `final_states` |

## RealtimeClock

The realtime clock synchronizes with wall-clock time and handles drift:

```python
import time
from chronopype import ClockConfig, ClockMode
from chronopype.clocks import RealtimeClock

config = ClockConfig(
    clock_mode=ClockMode.REALTIME,
    start_time=time.time(),
    tick_size=0.5,  # tick every 500ms
)

async with RealtimeClock(config) as clock:
    clock.add_processor(my_processor)

    # Run until a target time
    await clock.run_til(config.start_time + 60)

    # Or run indefinitely (cancel with asyncio cancellation)
    # await clock.run()
```

**Drift handling**: If a tick takes longer than `tick_size`, the next tick fires immediately to catch up. The clock tracks and compensates for accumulated drift.

## BacktestClock

The backtest clock steps through a defined time range deterministically:

```python
from chronopype import ClockConfig, ClockMode
from chronopype.clocks import BacktestClock

config = ClockConfig(
    clock_mode=ClockMode.BACKTEST,
    start_time=1700000000.0,
    end_time=1700003600.0,  # 1 hour range
    tick_size=1.0,
)

async with BacktestClock(config) as clock:
    clock.add_processor(my_processor)
    await clock.run()  # processes all ticks from start to end
```

### Step-by-Step Execution

The backtest clock supports fine-grained control:

```python
async with BacktestClock(config) as clock:
    clock.add_processor(my_processor)

    # Advance by exactly 5 ticks
    new_time = await clock.step(5)

    # Advance to a specific timestamp
    new_time = await clock.step_to(1700001000.0)

    # Fast forward by N seconds
    await clock.fast_forward(3600.0)

    # Run to a target time (creates an internal task)
    await clock.run_til(1700002000.0)
```

This is useful for testing strategies where you need to inspect state between ticks.

## Processor Management

```python
async with RealtimeClock(config) as clock:
    processor = MyProcessor()

    # Add and remove processors
    clock.add_processor(processor)
    clock.remove_processor(processor)

    # Pause and resume (processor stays registered but skips ticks)
    clock.add_processor(processor)
    clock.pause_processor(processor)
    clock.resume_processor(processor)

    # Query processor state
    active = clock.get_active_processors()
    state = clock.get_processor_state(processor)
    all_states = clock.processor_states  # dict copy
```

## Clock Registry

Use the registry to get a clock class dynamically:

```python
from chronopype.clocks import get_clock_class, ClockMode

clock_class = get_clock_class(ClockMode.BACKTEST)  # returns BacktestClock
clock = clock_class(config)
```

## Shutdown

For graceful shutdown outside the context manager:

```python
await clock.shutdown(timeout=5.0)  # stops all processors with timeout
```
