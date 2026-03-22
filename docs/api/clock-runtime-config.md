# ClockRuntimeConfig

**Module:** `chronopype.runtime.config`

Configuration for `ClockRuntime` lifecycle management. Composes a `ClockConfig` for clock-level parameters and adds runtime-specific settings.

## Constructor

```python
ClockRuntimeConfig(
    clock_config: ClockConfig = ClockConfig(clock_mode=ClockMode.REALTIME),
    thread_stop_timeout_seconds: float = 3.0,
    clock_poll_interval_seconds: float = 0.1,
)
```

## Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `clock_config` | `ClockConfig` | `ClockConfig(clock_mode=REALTIME)` | Clock configuration (mode, tick size, start/end time, processor settings). |
| `thread_stop_timeout_seconds` | `float` | `3.0` | Max seconds to wait for clock thread to stop. Must be > 0. |
| `clock_poll_interval_seconds` | `float` | `0.1` | Polling interval (seconds) for the clock loop stop-event check. Must be > 0. |

## Shortcut Properties

For convenience, the following properties delegate to `clock_config`:

| Property | Delegates to |
|----------|-------------|
| `clock_mode` | `clock_config.clock_mode` |
| `tick_size` | `clock_config.tick_size` |
| `start_time` | `clock_config.start_time` |
| `end_time` | `clock_config.end_time` |

## Immutability

`ClockRuntimeConfig` is a frozen Pydantic model --- fields cannot be modified after creation.

## Example

```python
from chronopype import ClockConfig, ClockMode, ClockRuntimeConfig

# Minimal
config = ClockRuntimeConfig()

# Full
config = ClockRuntimeConfig(
    clock_config=ClockConfig(
        clock_mode=ClockMode.BACKTEST,
        tick_size=0.5,
        start_time=1700000000.0,
        end_time=1700003600.0,
        processor_timeout=2.0,
        max_retries=5,
        concurrent_processors=True,
    ),
    thread_stop_timeout_seconds=5.0,
    clock_poll_interval_seconds=0.05,
)
```
