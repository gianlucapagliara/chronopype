import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from eventspype.publishers.multi import MultiPublisher
from eventspype.publishers.publications import EventPublication

from ..exceptions import ClockContextError, ClockError, ProcessorTimeoutError
from ..models import ClockConfig, ProcessorState
from ..processors.base import TickProcessor
from .modes import ClockMode


@dataclass
class ClockStartEvent:
    """Event emitted when the clock starts."""
    timestamp: float
    mode: ClockMode
    tick_size: float


@dataclass
class ClockTickEvent:
    """Event emitted on each clock tick."""
    timestamp: float
    tick_counter: int
    processors: list[TickProcessor]


@dataclass
class ClockStopEvent:
    """Event emitted when the clock stops."""
    timestamp: float
    total_ticks: int
    final_states: dict[TickProcessor, ProcessorState]


class AsyncContextManager(Protocol):
    async def __aenter__(self) -> Any: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None: ...


class BaseClock(AsyncContextManager, MultiPublisher, ABC):
    """Base abstract class for Clock implementations."""

    start_publication = EventPublication(event_class=ClockStartEvent, event_tag="clock_start")
    tick_publication = EventPublication(event_class=ClockTickEvent, event_tag="clock_tick")
    stop_publication = EventPublication(event_class=ClockStopEvent, event_tag="clock_stop")

    def __init__(
        self,
        config: ClockConfig,
        error_callback: Callable[[TickProcessor, Exception], None] | None = None,
    ) -> None:
        """Initialize a new Clock instance."""
        MultiPublisher.__init__(self)  # Initialize MultiPublisher

        self._config = config
        self._tick_counter = 0
        self._current_tick = (
            config.start_time
            if config.clock_mode is ClockMode.BACKTEST
            else (time.time() // config.tick_size) * config.tick_size
        )
        self._processors: list[TickProcessor] = []
        self._processor_states: dict[TickProcessor, ProcessorState] = {}
        self._current_context: list[TickProcessor] | None = None
        self._started = False
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()
        self._error_callback = error_callback

    @property
    def config(self) -> ClockConfig:
        """Get the clock configuration."""
        return self._config

    @property
    def clock_mode(self) -> ClockMode:
        """Get the clock mode."""
        return self._config.clock_mode

    @property
    def start_time(self) -> float:
        """Get the start time."""
        return self._config.start_time

    @property
    def end_time(self) -> float:
        """Get the end time."""
        return self._config.end_time

    @property
    def tick_size(self) -> float:
        """Get the tick size."""
        return self._config.tick_size

    @property
    def processors(self) -> list[TickProcessor]:
        """Get all registered processors."""
        return self._processors

    @property
    def current_timestamp(self) -> float:
        """Get the current timestamp."""
        return self._current_tick

    @property
    def tick_counter(self) -> int:
        """Get the number of ticks processed."""
        return self._tick_counter

    @property
    def processor_states(self) -> dict[TickProcessor, ProcessorState]:
        """Get the current states of all processors."""
        return self._processor_states.copy()

    def get_processor_performance(
        self, processor: TickProcessor
    ) -> tuple[float, float, float]:
        """Get performance metrics for a processor."""
        state = self._processor_states.get(processor)
        if not state or not state.execution_times:
            return 0.0, 0.0, 0.0

        return (
            state.avg_execution_time,
            state.std_dev_execution_time,
            state.get_execution_percentile(95),
        )

    @abstractmethod
    def start(self) -> None:
        """Start the clock."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the clock."""
        pass

    @abstractmethod
    def tick(self) -> None:
        """Process a clock tick."""
        pass

    @abstractmethod
    async def run(self) -> None:
        """Run the clock."""
        pass

    @abstractmethod
    async def run_til(self, target_time: float) -> None:
        """Run the clock until the target time."""
        pass

    async def shutdown(self, timeout: float | None = None) -> None:
        """Shutdown the clock and all processors with a timeout."""
        if not self._running and not self._started:
            return

        self._running = False
        self._started = False
        self._shutdown_event.set()

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

        if self._current_context:
            for processor in self._current_context:
                try:
                    processor.stop()
                    state = self._processor_states[processor]
                    self._processor_states[processor] = state.model_copy(
                        update={"is_active": False}
                    )
                except Exception:
                    pass  # Ignore errors during cleanup

        # Emit stop event
        self.trigger_event(
            self.stop_publication,
            ClockStopEvent(
                timestamp=self._current_tick,
                total_ticks=self._tick_counter,
                final_states=self.processor_states,
            ),
        )

    def add_processor(self, processor: TickProcessor) -> None:
        """Add a processor to the clock."""
        if processor in self._processors:
            raise ClockError("Processor already registered")

        self._processors.append(processor)
        self._processor_states[processor] = ProcessorState(
            last_timestamp=self._current_tick,
            is_active=False,
            retry_count=0,
            max_consecutive_retries=0,
            execution_times=[],
            error_count=0,
            consecutive_errors=0,
            last_error=None,
            last_error_time=None,
            last_success_time=None,
        )

    def remove_processor(self, processor: TickProcessor) -> None:
        """Remove a processor from the clock."""
        if processor not in self._processors:
            raise ClockError("Processor not registered")

        self._processors.remove(processor)
        self._processor_states.pop(processor, None)

    def pause_processor(self, processor: TickProcessor) -> None:
        """Pause a processor."""
        if processor not in self._processor_states:
            raise ClockError("Processor not registered")

        state = self._processor_states[processor]
        if state.is_active:
            self._processor_states[processor] = state.model_copy(
                update={"is_active": False}
            )

    def resume_processor(self, processor: TickProcessor) -> None:
        """Resume a paused processor."""
        if processor not in self._processor_states:
            raise ClockError("Processor not registered")

        state = self._processor_states[processor]
        if not state.is_active:
            self._processor_states[processor] = state.model_copy(
                update={"is_active": True}
            )

    def get_processor_state(self, processor: TickProcessor) -> ProcessorState | None:
        """Get the state of a specific processor."""
        return self._processor_states.get(processor)

    def get_active_processors(self) -> list[TickProcessor]:
        """Get all currently active processors."""
        return [p for p, state in self._processor_states.items() if state.is_active]

    def get_lagging_processors(self, threshold: float) -> list[TickProcessor]:
        """Get processors that are lagging behind the threshold."""
        lagging = []
        for processor in self._processors:
            state = self._processor_states[processor]
            if state.execution_times:
                avg_time = sum(state.execution_times) / len(state.execution_times)
                if avg_time > threshold:
                    lagging.append(processor)
        return lagging

    async def _execute_processor(
        self, processor: TickProcessor, timestamp: float
    ) -> None:
        """Execute a single processor."""
        state = self._processor_states[processor]
        if not state.is_active:
            return

        retry_count = 0
        last_error: ProcessorTimeoutError | Exception | None = None
        max_consecutive_retries = state.max_consecutive_retries

        while retry_count <= self._config.max_retries:
            try:
                start_time = time.perf_counter()
                try:
                    # Always enforce the processor timeout in both modes
                    # The difference is that realtime mode can skip ticks if needed
                    await asyncio.wait_for(
                        processor.async_tick(timestamp),
                        timeout=self._config.processor_timeout,
                    )
                except TimeoutError as e:
                    error = ProcessorTimeoutError(
                        f"Processor execution timed out after {self._config.processor_timeout}s"
                    )
                    last_error = error
                    # Don't raise the error immediately, let the retry logic handle it
                    retry_count += 1
                    max_consecutive_retries = max(max_consecutive_retries, retry_count)
                    if retry_count <= self._config.max_retries:
                        await asyncio.sleep(0.1 * (2 ** (retry_count - 1)))
                        continue
                    raise error from e

                execution_time = time.perf_counter() - start_time

                # Update execution time stats
                execution_times = list(state.execution_times)
                execution_times.append(execution_time)
                if len(execution_times) > self._config.stats_window_size:
                    execution_times.pop(0)

                # Update processor state after successful execution
                self._processor_states[processor] = state.model_copy(
                    update={
                        "execution_times": execution_times,
                        "consecutive_errors": 0,
                        "retry_count": 0,
                        "last_success_time": time.time(),
                        "last_timestamp": timestamp,
                        "max_consecutive_retries": max_consecutive_retries,
                    }
                )

                # Emit tick event after successful execution
                self.trigger_event(
                    self.tick_publication,
                    ClockTickEvent(
                        timestamp=timestamp,
                        tick_counter=self._tick_counter,
                        processors=self.get_active_processors(),
                    ),
                )

                return

            except ProcessorTimeoutError:
                # Don't retry on timeout errors after all retries are exhausted
                break

            except Exception as e:
                last_error = e
                retry_count += 1
                max_consecutive_retries = max(max_consecutive_retries, retry_count)

                if retry_count <= self._config.max_retries:
                    await asyncio.sleep(0.1 * (2 ** (retry_count - 1)))
                else:
                    break

        if last_error:
            # Update processor state with error
            self._processor_states[processor] = state.model_copy(
                update={
                    "error_count": state.error_count + 1,
                    "consecutive_errors": state.consecutive_errors + 1,
                    "last_error": last_error,
                    "last_error_time": time.time(),
                    "last_timestamp": timestamp,
                    "retry_count": retry_count,
                    "max_consecutive_retries": max_consecutive_retries,
                }
            )
            raise last_error

    def _cleanup(self, error_occurred: bool = False) -> None:
        """Clean up the clock state."""
        # Reset all processor states while preserving error information
        for processor in self._processors:
            state = self._processor_states[processor]
            self._processor_states[processor] = state.model_copy(
                update={
                    "is_active": False,
                    "retry_count": 0,
                    "consecutive_errors": 0,
                }
            )

        # If an error occurred, mark the clock as running to prevent re-entry
        if error_occurred:
            self._running = True
        else:
            self._running = False

        self._current_context = None
        self._started = False
        self._task = None

    async def __aenter__(self) -> "BaseClock":
        """Enter the clock context."""
        if self._current_context is not None or self._running or self._started:
            raise ClockContextError("Clock is already in a context or running")

        try:
            self._current_context = []
            self._started = False
            self._running = False
            self._tick_counter = 0
            self._current_tick = (
                self._config.start_time
                if self._config.clock_mode is ClockMode.BACKTEST
                else (time.time() // self._config.tick_size) * self._config.tick_size
            )

            # Emit clock start event
            self.trigger_event(
                self.start_publication,
                ClockStartEvent(
                    timestamp=self._current_tick,
                    mode=self._config.clock_mode,
                    tick_size=self._config.tick_size,
                ),
            )

            # Add all registered processors to the context
            for processor in self._processors:
                try:
                    self._current_context.append(processor)
                    processor.start(self._current_tick)
                    state = self._processor_states.get(processor, ProcessorState())
                    self._processor_states[processor] = state.model_copy(
                        update={
                            "is_active": True,
                            "last_timestamp": self._current_tick,
                            "retry_count": 0,
                            "consecutive_errors": 0,
                        }
                    )
                except Exception as e:
                    # Clean up any processors that were started
                    for p in self._current_context:
                        try:
                            p.stop()
                        except Exception:
                            pass
                    self._cleanup(error_occurred=True)
                    raise ClockError(f"Failed to start processor: {e}") from e

            return self
        except:
            self._cleanup(error_occurred=True)
            raise

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the clock context."""
        if self._current_context is None:
            raise ClockContextError("Clock is not in a context")

        error_occurred = exc_type is not None
        try:
            if not error_occurred:
                await self.shutdown()
        except:
            error_occurred = True
            raise
        finally:
            # Stop all processors in the context
            if self._current_context:
                for processor in self._current_context:
                    try:
                        processor.stop()
                        state = self._processor_states[processor]
                        # Preserve error information when stopping
                        self._processor_states[processor] = state.model_copy(
                            update={
                                "is_active": False,
                                "retry_count": 0,
                                "consecutive_errors": 0,
                            }
                        )
                    except Exception:
                        error_occurred = True
                        pass  # Ignore errors during cleanup

            self._cleanup(error_occurred=error_occurred)

    def get_processor_stats(self, processor: TickProcessor) -> dict[str, Any]:
        """Get detailed statistics for a processor."""
        state = self._processor_states.get(processor)
        if not state:
            return {}

        execution_times = state.execution_times
        avg_execution_time = (
            sum(execution_times) / len(execution_times) if execution_times else 0
        )

        return {
            "execution_times": execution_times,
            "error_count": state.error_count,
            "consecutive_errors": state.consecutive_errors,
            "retry_count": state.retry_count,
            "max_consecutive_retries": state.max_consecutive_retries,
            "last_error": str(state.last_error) if state.last_error else None,
            "last_error_time": state.last_error_time,
            "last_success_time": state.last_success_time,
            "total_ticks": len(execution_times),
            "successful_ticks": len(execution_times) - state.error_count,
            "failed_ticks": state.error_count,
            "avg_execution_time": avg_execution_time,
            "max_execution_time": max(execution_times) if execution_times else 0,
        }
