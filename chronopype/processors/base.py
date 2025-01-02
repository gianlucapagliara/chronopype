from abc import ABC, abstractmethod
from typing import Any

from chronopype.processors.models import ProcessorState


class TickProcessor(ABC):
    """Base class for tick processors."""

    def __init__(self, stats_window_size: int = 100) -> None:
        self._state = ProcessorState()
        self._stats_window_size = stats_window_size

    @property
    def state(self) -> ProcessorState:
        """Current state of the processor."""
        return self._state

    def _update_state(self, **kwargs: Any) -> None:
        """Update the processor state with new values."""
        self._state = self._state.model_copy(update=kwargs)

    def record_execution(self, execution_time: float) -> None:
        """Record a successful execution."""
        self._state = self._state.update_execution_time(
            execution_time, self._stats_window_size
        )
        self._state = self._state.reset_retries()

    def record_error(self, error: Exception, timestamp: float) -> None:
        """Record an error occurrence."""
        self._state = self._state.record_error(error, timestamp)

    @abstractmethod
    def start(self, timestamp: float) -> None:
        """Start the processor."""
        self._update_state(last_timestamp=timestamp, is_active=True)

    @abstractmethod
    def tick(self, timestamp: float) -> None:
        """Process a tick."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the processor."""
        self._update_state(is_active=False)

    async def async_tick(self, timestamp: float) -> None:
        """Async version of tick. Default implementation calls sync tick."""
        self.tick(timestamp)
