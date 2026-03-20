# Installation

## Requirements

- Python 3.13 or higher

## Install from PyPI

```bash
# Using pip
pip install chronopype

# Using uv
uv add chronopype

# Using poetry
poetry add chronopype
```

## Dependencies

Chronopype has minimal dependencies:

| Package | Version | Purpose |
|---------|---------|---------|
| [pydantic](https://docs.pydantic.dev/) | >= 2.10.4 | Configuration and state validation |
| [eventspype](https://github.com/gianlucapagliara/eventspype) | >= 1.0.1 | Event publication framework |

## Verify Installation

```python
import chronopype
from chronopype.clocks import RealtimeClock, BacktestClock
from chronopype.processors import TickProcessor

print("chronopype installed successfully")
```
