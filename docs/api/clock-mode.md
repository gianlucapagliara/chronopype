# ClockMode

**Module:** `chronopype.clocks.modes`

An enum that identifies the clock operating mode.

## Definition

```python
class ClockMode(Enum):
    REALTIME = 1
    BACKTEST = 2
```

## Values

| Value | Int | Description |
|-------|-----|-------------|
| `REALTIME` | `1` | Real-time processing synchronized with wall-clock time |
| `BACKTEST` | `2` | Deterministic historical time simulation |

## Usage

```python
from chronopype.clocks import ClockMode

mode = ClockMode.REALTIME

# Used in ClockConfig
config = ClockConfig(clock_mode=ClockMode.BACKTEST, ...)

# Used with the clock registry
from chronopype.clocks import get_clock_class
clock_class = get_clock_class(ClockMode.BACKTEST)  # BacktestClock
```
