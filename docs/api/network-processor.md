# NetworkProcessor

**Module:** `chronopype.processors.network`

**Inherits:** [`TickProcessor`](tick-processor.md)

Abstract base class for processors that depend on network connectivity. Provides automatic connection monitoring, reconnection with exponential backoff, and status transition callbacks.

## Constructor

```python
NetworkProcessor(stats_window_size: int = 100)
```

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `network_status` | `NetworkStatus` | Current connectivity status |
| `last_connected_timestamp` | `float` | Timestamp of last successful connection |
| `check_network_interval` | `float` | Seconds between connectivity checks (default: 10.0, min: 0.1) |
| `check_network_timeout` | `float` | Timeout for each `check_network()` call (default: 5.0, min: 0.1) |
| `network_error_wait_time` | `float` | Wait time after unexpected errors (default: 60.0, min: 0.1) |

All configurable properties have setters with minimum value enforcement of 0.1 seconds.

## Abstract Methods (must implement)

### `logger()` (classmethod)

Return a `logging.Logger` instance for this processor.

```python
@classmethod
@abstractmethod
def logger(cls) -> logging.Logger:
    ...
```

### `check_network()`

Check current network connectivity. Must return a `NetworkStatus` value.

```python
@abstractmethod
async def check_network(self) -> NetworkStatus:
    ...
```

## Optional Override Methods

| Method | Signature | Default | Description |
|--------|-----------|---------|-------------|
| `start_network` | `async () -> None` | No-op | Called when connection is established |
| `stop_network` | `async () -> None` | No-op | Called when disconnecting |
| `on_connected` | `() -> None` | Logs info | Transition to `CONNECTED` |
| `on_disconnected` | `() -> None` | Logs info | Transition from `CONNECTED` |
| `tick` | `(timestamp: float) -> None` | No-op | Sync tick handler |
| `async_tick` | `async (timestamp: float) -> None` | Calls `tick()` | Async tick handler |

## NetworkStatus

```python
class NetworkStatus(Enum):
    STOPPED = 0
    NOT_CONNECTED = 1
    CONNECTING = 2
    CONNECTED = 3
    DISCONNECTING = 4
    ERROR = 5
```

## Backoff Behavior

When reconnecting, the processor uses exponential backoff with jitter:

- **Base delay:** `min(1 * 2^retry_count, 300)` seconds
- **Jitter:** +/- 20% randomization
- **Min wait:** 1 second
- **Max wait:** 5 minutes (300 seconds)
- **Error wait:** 60 seconds for unexpected errors (configurable)

## Class Variable

| Variable | Default | Description |
|----------|---------|-------------|
| `LOGGER_NAME` | `"NetworkProcessor"` | Override in subclasses for distinct logging |

## Example

```python
import logging
from chronopype.processors.network import NetworkProcessor, NetworkStatus


class DatabaseProcessor(NetworkProcessor):
    LOGGER_NAME = "DatabaseProcessor"

    @classmethod
    def logger(cls) -> logging.Logger:
        return logging.getLogger(cls.LOGGER_NAME)

    async def check_network(self) -> NetworkStatus:
        try:
            await self.pool.execute("SELECT 1")
            return NetworkStatus.CONNECTED
        except Exception:
            return NetworkStatus.NOT_CONNECTED

    async def start_network(self) -> None:
        self.pool = await create_pool(dsn="postgres://...")

    async def stop_network(self) -> None:
        await self.pool.close()

    async def async_tick(self, timestamp: float) -> None:
        if self.network_status == NetworkStatus.CONNECTED:
            await self.pool.execute("INSERT INTO ticks ...")
```
