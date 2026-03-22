# Chronopype

[![CI](https://github.com/gianlucapagliara/chronopype/actions/workflows/ci.yml/badge.svg)](https://github.com/gianlucapagliara/chronopype/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/gianlucapagliara/chronopype/branch/main/graph/badge.svg)](https://codecov.io/gh/gianlucapagliara/chronopype)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/chronopype)](https://pypi.org/project/chronopype/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A flexible, type-safe clock implementation for real-time and backtesting scenarios in Python. Chronopype provides a robust framework for managing time-based operations with async/await support, comprehensive performance monitoring, and an extensible processor framework.

## Features

- **Flexible Clock System** --- Support for both real-time and backtesting modes with a unified API
- **Processor Framework** --- Extensible system for implementing time-based operations with retry and timeout support
- **Network-Aware** --- Built-in network processor with automatic reconnection and exponential backoff
- **Async Support** --- Full async/await support for efficient I/O operations
- **Performance Monitoring** --- Built-in execution time tracking, percentile statistics, and lagging processor detection
- **Type Safe** --- Fully typed with MyPy strict mode compliance
- **Well Tested** --- Comprehensive test suite with high coverage

## Quick Example

```python
import asyncio
import time
from chronopype import ClockConfig, ClockMode
from chronopype.clocks import RealtimeClock
from chronopype.processors import TickProcessor


class MyProcessor(TickProcessor):
    async def async_tick(self, timestamp: float) -> None:
        print(f"Tick at {timestamp}")


async def main():
    config = ClockConfig(
        clock_mode=ClockMode.REALTIME,
        start_time=time.time(),
        tick_size=1.0,
    )
    async with RealtimeClock(config) as clock:
        clock.add_processor(MyProcessor())
        await clock.run_til(config.start_time + 10)


asyncio.run(main())
```

## Architecture Overview

Chronopype is organized around two core abstractions:

- **Clocks** manage time progression and coordinate processors. Choose `RealtimeClock` for live systems or `BacktestClock` for historical simulation.
- **Processors** implement the work that happens on each tick. The base `TickProcessor` handles sync/async execution, while `NetworkProcessor` adds connectivity management.

```
ClockRuntime         ── lifecycle management (async + threaded)
└── BaseClock (abstract)
    ├── RealtimeClock    ── real-time with drift correction
    └── BacktestClock    ── deterministic stepping through historical time

TickProcessor (base)
└── NetworkProcessor ── network-aware with auto-reconnection
```

## Next Steps

- [Installation](getting-started/installation.md) --- Set up chronopype in your project
- [Quick Start](getting-started/quickstart.md) --- Build your first clock and processor
- [User Guide](guide/clocks.md) --- Learn about clocks, processors, and monitoring
- [API Reference](api/clock-config.md) --- Full API documentation
