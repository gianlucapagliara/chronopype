# Quick Start

This guide walks through the basics of chronopype: creating a processor, configuring a clock, and running it.

## Your First Processor

A processor defines work that runs on each clock tick. Create one by subclassing `TickProcessor`:

```python
from chronopype.processors import TickProcessor


class PrintProcessor(TickProcessor):
    async def async_tick(self, timestamp: float) -> None:
        print(f"Tick at {timestamp:.2f}")
```

Override `async_tick` for async work, or `tick` for synchronous work. By default, `async_tick` calls `tick`.

## Configuring a Clock

Every clock requires a `ClockConfig`:

```python
import time
from chronopype import ClockConfig, ClockMode

config = ClockConfig(
    clock_mode=ClockMode.REALTIME,
    start_time=time.time(),
    tick_size=1.0,           # 1 second between ticks
    processor_timeout=5.0,   # timeout per processor execution
    max_retries=3,           # retry failed processors
)
```

## Running a Realtime Clock

Use the clock as an async context manager, add processors, and run:

```python
import asyncio
import time
from chronopype import ClockConfig, ClockMode
from chronopype.clocks import RealtimeClock
from chronopype.processors import TickProcessor


class PrintProcessor(TickProcessor):
    async def async_tick(self, timestamp: float) -> None:
        print(f"Tick at {timestamp:.2f}")


async def main():
    config = ClockConfig(
        clock_mode=ClockMode.REALTIME,
        start_time=time.time(),
        tick_size=1.0,
    )

    async with RealtimeClock(config) as clock:
        clock.add_processor(PrintProcessor())
        await clock.run_til(config.start_time + 5)  # run for 5 seconds


asyncio.run(main())
```

## Running a Backtest Clock

For backtesting, use `BacktestClock` with a defined time range:

```python
import asyncio
from chronopype import ClockConfig, ClockMode
from chronopype.clocks import BacktestClock
from chronopype.processors import TickProcessor


class DataProcessor(TickProcessor):
    async def async_tick(self, timestamp: float) -> None:
        print(f"Processing historical data at {timestamp:.2f}")


async def main():
    config = ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        start_time=1000.0,
        end_time=1010.0,    # required for backtest mode
        tick_size=1.0,
    )

    async with BacktestClock(config) as clock:
        clock.add_processor(DataProcessor())
        await clock.run()  # runs from start_time to end_time


asyncio.run(main())
```

## Multiple Processors

You can add multiple processors to a single clock. They execute sequentially by default, or concurrently with `concurrent_processors=True`:

```python
config = ClockConfig(
    clock_mode=ClockMode.REALTIME,
    start_time=time.time(),
    tick_size=1.0,
    concurrent_processors=True,  # run processors in parallel
)

async with RealtimeClock(config) as clock:
    clock.add_processor(ProcessorA())
    clock.add_processor(ProcessorB())
    await clock.run_til(config.start_time + 10)
```

## Error Handling

Provide an error callback to handle processor failures:

```python
def on_error(processor: TickProcessor, error: Exception) -> None:
    print(f"Processor {processor} failed: {error}")

async with RealtimeClock(config, error_callback=on_error) as clock:
    clock.add_processor(MyProcessor())
    await clock.run_til(config.start_time + 10)
```

## Next Steps

- [Clocks Guide](../guide/clocks.md) --- Deep dive into clock modes and lifecycle
- [Processors Guide](../guide/processors.md) --- Advanced processor patterns
- [Network Processor](../guide/network-processor.md) --- Build connectivity-aware processors
