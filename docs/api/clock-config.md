# ClockConfig

::: chronopype.clocks.config

`ClockConfig` is a frozen Pydantic model that holds all configuration for a clock instance.

**Module:** `chronopype.clocks.config`

## Definition

```python
class ClockConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
```

## Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `clock_mode` | `ClockMode` | *required* | `REALTIME` or `BACKTEST` |
| `tick_size` | `float` | `1.0` | Interval between ticks in seconds. Must be > 0 |
| `start_time` | `float` | `0.0` | Start time as UNIX timestamp |
| `end_time` | `float` | `0.0` | End time as UNIX timestamp. `0` means no end. Required > 0 for `BACKTEST` mode |
| `processor_timeout` | `float` | `1.0` | Maximum seconds allowed per processor execution |
| `max_retries` | `int` | `3` | Number of retries for failed processor executions |
| `concurrent_processors` | `bool` | `False` | Run processors concurrently via `asyncio.gather` |
| `stats_window_size` | `int` | `100` | Rolling window size for execution time statistics |

## Validation

- `end_time` must be >= `start_time` when both are specified
- The model is frozen (immutable) after creation

## Example

```python
from chronopype.clocks import ClockMode
from chronopype.clocks.config import ClockConfig

config = ClockConfig(
    clock_mode=ClockMode.BACKTEST,
    start_time=1700000000.0,
    end_time=1700003600.0,
    tick_size=0.5,
    max_retries=5,
    concurrent_processors=True,
    stats_window_size=200,
)

# Immutable - this raises an error:
# config.tick_size = 2.0  # ValidationError
```
