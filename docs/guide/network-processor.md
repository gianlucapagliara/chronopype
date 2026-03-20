# Network Processor

`NetworkProcessor` extends `TickProcessor` with built-in network connectivity management, automatic reconnection, and exponential backoff. Use it for processors that depend on external services.

## Creating a Network Processor

Subclass `NetworkProcessor` and implement the required abstract methods:

```python
import logging
from chronopype.processors.network import NetworkProcessor, NetworkStatus


class ApiProcessor(NetworkProcessor):
    LOGGER_NAME = "ApiProcessor"

    @classmethod
    def logger(cls) -> logging.Logger:
        return logging.getLogger(cls.LOGGER_NAME)

    async def check_network(self) -> NetworkStatus:
        """Check if the API is reachable."""
        try:
            response = await self.client.health_check()
            if response.ok:
                return NetworkStatus.CONNECTED
            return NetworkStatus.NOT_CONNECTED
        except Exception:
            return NetworkStatus.ERROR

    async def start_network(self) -> None:
        """Called when connection is established."""
        self.client = await create_api_client()

    async def stop_network(self) -> None:
        """Called when disconnecting."""
        await self.client.close()

    def tick(self, timestamp: float) -> None:
        """Only runs when network is connected."""
        self.client.process(timestamp)
```

## Required Methods

| Method | Purpose |
|--------|---------|
| `logger()` | Class method returning a `logging.Logger` |
| `check_network()` | Return current `NetworkStatus` |

## Optional Override Methods

| Method | Purpose | Default |
|--------|---------|---------|
| `start_network()` | Setup when connection is established | No-op |
| `stop_network()` | Cleanup when disconnecting | No-op |
| `on_connected()` | Callback on `CONNECTED` transition | Logs info |
| `on_disconnected()` | Callback on disconnect from `CONNECTED` | Logs info |
| `tick(timestamp)` | Synchronous tick processing | No-op |
| `async_tick(timestamp)` | Async tick processing | Calls `tick()` |

## Network Status

The processor tracks its connectivity state:

```python
class NetworkStatus(Enum):
    STOPPED = 0        # Processor not running
    NOT_CONNECTED = 1  # Not connected to network
    CONNECTING = 2     # Connection in progress
    CONNECTED = 3      # Connected and operational
    DISCONNECTING = 4  # Disconnection in progress
    ERROR = 5          # Error state
```

Access the current status:

```python
processor = ApiProcessor()
print(processor.network_status)  # NetworkStatus.STOPPED initially
```

## Automatic Reconnection

The network processor runs a background loop that periodically checks connectivity and manages reconnection with exponential backoff:

- **Check interval**: 10 seconds (configurable)
- **Check timeout**: 5 seconds (configurable)
- **Backoff**: Exponential with jitter, min 1s, max 5 minutes
- **Error wait**: 60 seconds for unexpected errors (configurable)

The jitter is +/-20% to avoid thundering herd problems when multiple processors reconnect simultaneously.

## Configuration

Adjust network behavior via properties:

```python
processor = ApiProcessor()

# How often to check connectivity (minimum 0.1s)
processor.check_network_interval = 5.0

# Timeout for each check_network() call (minimum 0.1s)
processor.check_network_timeout = 3.0

# Wait time after unexpected errors (minimum 0.1s)
processor.network_error_wait_time = 30.0
```

## Status Transitions

The processor handles status transitions and fires callbacks:

```
STOPPED ──start()──> NOT_CONNECTED
                         │
                    check_network()
                         │
                    ┌────▼────┐
                    │CONNECTING│
                    └────┬────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         CONNECTED  NOT_CONNECTED  ERROR
              │                     │
         on_connected()       backoff + retry
              │
         ──stop()──> DISCONNECTING ──> STOPPED
                     on_disconnected()
```

## Full Example

```python
import asyncio
import logging
from chronopype.clocks import RealtimeClock, ClockMode
from chronopype.clocks.config import ClockConfig
from chronopype.processors.network import NetworkProcessor, NetworkStatus


class WebSocketProcessor(NetworkProcessor):
    LOGGER_NAME = "WebSocketProcessor"

    @classmethod
    def logger(cls) -> logging.Logger:
        return logging.getLogger(cls.LOGGER_NAME)

    async def check_network(self) -> NetworkStatus:
        if self.ws and self.ws.open:
            return NetworkStatus.CONNECTED
        return NetworkStatus.NOT_CONNECTED

    async def start_network(self) -> None:
        self.ws = await websockets.connect("wss://example.com/feed")

    async def stop_network(self) -> None:
        if self.ws:
            await self.ws.close()

    def on_connected(self) -> None:
        super().on_connected()
        self.logger().info("WebSocket connected, subscribing to feed")

    async def async_tick(self, timestamp: float) -> None:
        if self.network_status == NetworkStatus.CONNECTED:
            data = await self.ws.recv()
            self.process_message(data, timestamp)


async def main():
    config = ClockConfig(
        clock_mode=ClockMode.REALTIME,
        start_time=asyncio.get_event_loop().time(),
        tick_size=0.1,
    )

    processor = WebSocketProcessor()
    processor.check_network_interval = 5.0

    async with RealtimeClock(config) as clock:
        clock.add_processor(processor)
        await clock.run_til(config.start_time + 300)


asyncio.run(main())
```
