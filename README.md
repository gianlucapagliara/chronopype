# Chronopype

[![CI](https://github.com/gianlucapagliara/chronopype/actions/workflows/ci.yml/badge.svg)](https://github.com/gianlucapagliara/chronopype/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/gianlucapagliara/chronopype/branch/main/graph/badge.svg)](https://codecov.io/gh/gianlucapagliara/chronopype)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/chronopype)](https://pypi.org/project/chronopype/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://gianlucapagliara.github.io/chronopype/)

A flexible clock implementation for real-time and backtesting scenarios in Python. Chronopype provides a robust framework for managing time-based operations with support for both real-time processing and historical data backtesting.

## Features

- 🕒 **Flexible Clock System**: Support for both real-time and backtesting modes
- 🔄 **Processor Framework**: Extensible system for implementing time-based operations with retry and timeout support
- 🌐 **Network-Aware**: Built-in network processor with automatic reconnection and exponential backoff
- ⚡ **Async Support**: Full async/await support for efficient I/O operations
- 📊 **Performance Monitoring**: Built-in execution time tracking, percentile statistics, and lagging processor detection
- 🔒 **Type Safe**: Fully typed with MyPy strict mode
- 🧪 **Well Tested**: Comprehensive test suite with high coverage

## Installation

```bash
# Using pip
pip install chronopype

# Using uv
uv add chronopype
```

## Quick Start

Here's a simple example of using chronopype:

```python
import asyncio
import time

from chronopype import ClockConfig, ClockMode
from chronopype.clocks import RealtimeClock
from chronopype.processors import TickProcessor


class MyProcessor(TickProcessor):
    async def async_tick(self, timestamp: float) -> None:
        print(f"Processing at {timestamp}")


async def main():
    config = ClockConfig(
        clock_mode=ClockMode.REALTIME,
        start_time=time.time(),
        tick_size=1.0,  # 1 second ticks
    )

    async with RealtimeClock(config) as clock:
        clock.add_processor(MyProcessor())
        await clock.run_til(config.start_time + 10)


if __name__ == "__main__":
    asyncio.run(main())
```

## Core Components

- **Clocks**: Base implementations for time management
  - `RealtimeClock`: For real-time processing with drift compensation
  - `BacktestClock`: For deterministic historical data simulation

- **Processors**: Framework for implementing time-based operations
  - `TickProcessor`: Base class for all processors
  - `NetworkProcessor`: Network-aware processor with automatic reconnection

## Documentation

Full documentation is available at [gianlucapagliara.github.io/chronopype](https://gianlucapagliara.github.io/chronopype/).

## Development

Chronopype uses [uv](https://docs.astral.sh/uv/) for dependency management and packaging:

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run type checks
uv run mypy chronopype

# Run linting
uv run ruff check .

# Run pre-commit hooks
uv run pre-commit run --all-files
```
