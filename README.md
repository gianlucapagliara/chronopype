# Chrono Pypeline

[![CI](https://github.com/gianlucapagliara/chronopype/actions/workflows/ci.yml/badge.svg)](https://github.com/gianlucapagliara/chronopype/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/gianlucapagliara/chronopype/branch/main/graph/badge.svg)](https://codecov.io/gh/gianlucapagliara/chronopype)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

A flexible clock implementation for real-time and backtesting scenarios in Python. chronopype provides a robust framework for managing time-based operations with support for both real-time processing and historical data backtesting.

## Features

- 🕒 **Flexible Clock System**: Support for both real-time and backtesting modes
- 🔄 **Processor Framework**: Extensible system for implementing time-based operations
- 🌐 **Network-Aware**: Built-in network processor with retry and backoff capabilities
- ⚡ **Async Support**: Full async/await support for efficient I/O operations
- 🛠️ **Easy to Use**: Simple API for managing time-based operations
- 📊 **Performance Monitoring**: Built-in performance tracking and statistics
- 🔒 **Type Safe**: Fully typed with MyPy strict mode
- 🧪 **Well Tested**: Comprehensive test suite with high coverage

## Installation

```bash
# Using pip
pip install chronopype

# Using poetry
poetry add chronopype
```

## Quick Start

Here's a simple example of using chronopype:

```python
import asyncio
from chronopype import ClockConfig
from chronopype.clocks import RealtimeClock
from chronopype.processors import TickProcessor

class MyProcessor(TickProcessor):
    async def async_tick(self, timestamp: float) -> None:
        print(f"Processing at {timestamp}")

async def main():
    # Configure the clock
    config = ClockConfig(
        start_time=time.time(),
        tick_size=1.0  # 1 second ticks
    )

    # Create and configure the clock
    async with RealtimeClock(config) as clock:
        # Add your processor
        clock.add_processor(MyProcessor())

        # Run for 10 seconds
        await clock.run_til(config.start_time + 10)

if __name__ == "__main__":
    asyncio.run(main())
```

## Core Components

- **Clocks**: Base implementations for time management
  - `RealtimeClock`: For real-time processing
  - `BacktestClock`: For historical data processing

- **Processors**: Framework for implementing time-based operations
  - `TickProcessor`: Base class for all processors
  - `NetworkProcessor`: Network-aware processor with retry capabilities

## Development

chronopype uses Poetry for dependency management and packaging:

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run type checks
poetry run mypy .

# Run linting
poetry run pre-commit run --all-files
```
