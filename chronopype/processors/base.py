from typing import Any

from chronopype.processors.models import ProcessorState


class TickProcessor:
    """Base class for tick processors.

    When registered to a clock, the clock is the single source of truth for
    processor state (execution times, error counts, etc.). The ``state``
    property delegates to the clock's copy of the state automatically.
    """

    def __init__(self, stats_window_size: int = 100) -> None:
        self._state = ProcessorState()
        self._stats_window_size = stats_window_size
        self._owner_clock: Any = None  # Set by BaseClock.add_processor()

    @property
    def state(self) -> ProcessorState:
        """Current state of the processor.

        Returns the clock-managed state when registered to a clock,
        otherwise returns the processor's own internal state.
        """
        if self._owner_clock is not None:
            clock_state: ProcessorState | None = (
                self._owner_clock._processor_states.get(self)
            )
            if clock_state is not None:
                return clock_state
        return self._state

    @property
    def current_timestamp(self) -> float:
        """Current timestamp of the processor."""
        return self.state.last_timestamp or 0

    def record_execution(self, execution_time: float) -> None:
        """Record a successful execution."""
        self._state = self._state.update_execution_time(
            execution_time, self._stats_window_size
        )
        self._state = self._state.reset_retries()

    def record_error(self, error: Exception, timestamp: float) -> None:
        """Record an error occurrence."""
        self._state = self._state.record_error(error, timestamp)

    def start(self, timestamp: float) -> None:
        """Start the processor."""
        self._state = self._state.model_copy(
            update={"last_timestamp": timestamp, "is_active": True}
        )

    def tick(self, timestamp: float) -> None:
        """Process a tick."""
        pass

    def stop(self) -> None:
        """Stop the processor."""
        self._state = self._state.model_copy(update={"is_active": False})

    async def async_tick(self, timestamp: float) -> None:
        """Async version of tick. Default implementation calls sync tick."""
        self.tick(timestamp)
