import asyncio
import logging
import time
from abc import abstractmethod
from enum import Enum

from chronopype.processors.base import TickProcessor


class NetworkStatus(Enum):
    STOPPED = 0
    NOT_CONNECTED = 1
    CONNECTING = 2
    CONNECTED = 3
    DISCONNECTING = 4
    ERROR = 5


class NetworkProcessor(TickProcessor):
    LOGGER_NAME = "NetworkProcessor"
    _logger = None

    def __init__(self, stats_window_size: int = 100) -> None:
        super().__init__(stats_window_size=stats_window_size)
        self._network_status = NetworkStatus.STOPPED
        self._last_connected_timestamp = float("nan")
        self._check_network_interval = 10.0
        self._check_network_timeout = 5.0
        self._network_error_wait_time = 60.0
        self._check_network_task: asyncio.Task[None] | None = None
        self._min_backoff = 1.0
        self._max_backoff = 300.0  # 5 minutes
        self._backoff_factor = 2.0

    @classmethod
    def logger(cls) -> logging.Logger:
        raise NotImplementedError("logger() has not been implemented!")

    @property
    def network_status(self) -> NetworkStatus:
        return self._network_status

    @property
    def last_connected_timestamp(self) -> float:
        return self._last_connected_timestamp

    @property
    def check_network_interval(self) -> float:
        return self._check_network_interval

    @check_network_interval.setter
    def check_network_interval(self, interval: float) -> None:
        self._check_network_interval = max(0.1, interval)

    @property
    def check_network_timeout(self) -> float:
        return self._check_network_timeout

    @check_network_timeout.setter
    def check_network_timeout(self, timeout: float) -> None:
        self._check_network_timeout = max(0.1, timeout)

    @property
    def network_error_wait_time(self) -> float:
        return self._network_error_wait_time

    @network_error_wait_time.setter
    def network_error_wait_time(self, wait_time: float) -> None:
        self._network_error_wait_time = max(0.1, wait_time)

    def _calculate_backoff(self, retry_count: int) -> float:
        """Calculate backoff time using exponential backoff with jitter."""
        base_backoff = min(
            self._min_backoff * (self._backoff_factor**retry_count),
            self._max_backoff,
        )
        # Add some randomness (±20%)
        jitter = base_backoff * 0.2
        return max(self._min_backoff, base_backoff + (time.time() % 1.0 - 0.5) * jitter)

    async def start_network(self) -> None:
        """Override this method to implement network startup logic"""
        pass

    async def stop_network(self) -> None:
        """Override this method to implement network shutdown logic"""
        pass

    @abstractmethod
    async def check_network(self) -> NetworkStatus:
        """Override this method to implement network status checking"""
        raise NotImplementedError("check_network() has not been implemented!")

    async def _perform_network_check(self) -> tuple[NetworkStatus, bool, int, float]:
        start_time = time.time()
        retry_count = 0
        has_unexpected_error = False

        try:
            # Update status to show we're checking
            if self._network_status is NetworkStatus.NOT_CONNECTED:
                self._network_status = NetworkStatus.CONNECTING

            new_status = await asyncio.wait_for(
                self.check_network(), timeout=self._check_network_timeout
            )
            execution_time = time.time() - start_time
            self.record_execution(execution_time)

        except asyncio.CancelledError:
            raise
        except TimeoutError:
            self.logger().warning(
                "Check network call has timed out. Network status is not connected."
            )
            new_status = NetworkStatus.NOT_CONNECTED
            self.record_error(TimeoutError("Network check timed out"), time.time())
            retry_count = 1
        except Exception as e:
            self.logger().error(
                "Unexpected error while checking network status.", exc_info=True
            )
            new_status = NetworkStatus.ERROR
            has_unexpected_error = True
            self.record_error(e, time.time())
            retry_count = 1

        return new_status, has_unexpected_error, retry_count, time.time() - start_time

    async def _handle_status_transition(
        self, new_status: NetworkStatus, last_status: NetworkStatus
    ) -> None:
        if new_status != last_status:
            if new_status is NetworkStatus.CONNECTED:
                self._network_status = NetworkStatus.CONNECTED
                self.on_connected()
                await self.start_network()
            elif last_status is NetworkStatus.CONNECTED:
                self._network_status = NetworkStatus.DISCONNECTING
                self.on_disconnected()
                await self.stop_network()
                self._network_status = new_status

    def _calculate_wait_time(
        self, has_unexpected_error: bool, retry_count: int
    ) -> float:
        if has_unexpected_error:
            return self._network_error_wait_time
        elif retry_count > 0:
            return self._calculate_backoff(retry_count)
        return self._check_network_interval

    async def _check_network_loop(self) -> None:
        retry_count = 0
        while True:
            last_status = self._network_status

            (
                new_status,
                has_unexpected_error,
                new_retries,
                execution_time,
            ) = await self._perform_network_check()

            retry_count = (
                0
                if new_status is NetworkStatus.CONNECTED
                else retry_count + new_retries
            )
            self._state = self._state.update_retry_count(retry_count)

            await self._handle_status_transition(new_status, last_status)

            wait_time = self._calculate_wait_time(has_unexpected_error, retry_count)
            await asyncio.sleep(max(0.0, wait_time - execution_time))

    def start(self, timestamp: float) -> None:
        super().start(timestamp)
        self._check_network_task = asyncio.create_task(self._check_network_loop())
        self._network_status = NetworkStatus.NOT_CONNECTED

    def stop(self) -> None:
        if self._check_network_task is not None:
            self._check_network_task.cancel()
            self._check_network_task = None
        self._network_status = NetworkStatus.DISCONNECTING
        asyncio.create_task(self.stop_network())
        self._network_status = NetworkStatus.STOPPED
        super().stop()

    def tick(self, timestamp: float) -> None:
        """Override this method to implement synchronous tick processing"""
        pass

    def on_connected(self) -> None:
        """Override this method to implement logic when the network is connected"""
        self.logger().info(
            f"Network status has changed to {self._network_status}. Starting networking..."
        )
        self._last_connected_timestamp = time.time()

    def on_disconnected(self) -> None:
        """Override this method to implement logic when the network is disconnected"""
        pass

    async def async_tick(self, timestamp: float) -> None:
        """Override this method to implement asynchronous tick processing"""
        start_time = time.time()
        try:
            await super().async_tick(timestamp)
            execution_time = time.time() - start_time
            self.record_execution(execution_time)
        except Exception as e:
            self.record_error(e, timestamp)
            raise
