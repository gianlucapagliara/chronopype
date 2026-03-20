import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, TypedDict

from eventspype.pub.multipublisher import MultiPublisher
from eventspype.pub.publication import EventPublication

from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.exceptions import ClockContextError, ClockError, ProcessorTimeoutError
from chronopype.processors.base import TickProcessor
from chronopype.processors.models import ProcessorState

logger = logging.getLogger(__name__)


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


class ProcessorStats(TypedDict):
    """Type-safe statistics dictionary for a processor."""

    total_ticks: int
    successful_ticks: int
    failed_ticks: int
    error_count: int
    consecutive_errors: int
    retry_count: int
    max_consecutive_retries: int
    avg_execution_time: float
    max_execution_time: float
    std_dev_execution_time: float
    error_rate: float
    last_error: str | None
    last_error_time: datetime | None
    last_success_time: datetime | None


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

    start_publication = EventPublication(
        event_class=ClockStartEvent, event_tag="clock_start"
    )
    tick_publication = EventPublication(
        event_class=ClockTickEvent, event_tag="clock_tick"
    )
    stop_publication = EventPublication(
        event_class=ClockStopEvent, event_tag="clock_stop"
    )

    def __init__(
        self,
        config: ClockConfig,
        error_callback: Callable[[TickProcessor, Exception], None] | None = None,
    ) -> None:
        """Initialize a new Clock instance."""
        MultiPublisher.__init__(self)  # Initialize MultiPublisher
        logger.debug(
            "Initializing %s (mode=%s, tick_size=%s)",
            type(self).__name__,
            config.clock_mode.name,
            config.tick_size,
        )

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

        logger.info("Shutting down clock after %d ticks", self._tick_counter)
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
        self.publish(
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

        logger.debug("Adding processor %s", processor)
        # Sync stats window size from clock config to processor
        processor._stats_window_size = self._config.stats_window_size
        self._processors.append(processor)
        self._processor_states[processor] = ProcessorState(
            last_timestamp=self._current_tick,
            is_active=self._started,  # Set active if clock is started
            retry_count=0,
            max_consecutive_retries=0,
            execution_times=[],
            error_count=0,
            consecutive_errors=0,
            last_error=None,
            last_error_time=None,
            last_success_time=None,
        )

        # If clock is already started, initialize the processor
        if self._started:
            try:
                processor.start(self._current_tick)
            except Exception as e:
                # Clean up if initialization fails
                self._processors.remove(processor)
                self._processor_states.pop(processor)
                raise ClockError(f"Failed to start processor: {str(e)}") from e

    def remove_processor(self, processor: TickProcessor) -> None:
        """Remove a processor from the clock."""
        if processor not in self._processors:
            raise ClockError("Processor not registered")
        logger.debug("Removing processor %s", processor)

        # Stop the processor if it's active
        state = self._processor_states[processor]
        if state.is_active:
            try:
                processor.stop()
            except Exception as e:
                # Still remove the processor but propagate the error
                self._processors.remove(processor)
                self._processor_states.pop(processor, None)
                raise ClockError(f"Failed to stop processor: {str(e)}") from e

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
                    retry_count += 1
                    max_consecutive_retries = max(max_consecutive_retries, retry_count)
                    logger.warning(
                        "Processor %s timed out (retry %d/%d)",
                        processor,
                        retry_count,
                        self._config.max_retries,
                    )
                    if retry_count <= self._config.max_retries:
                        await asyncio.sleep(0.1 * (2 ** (retry_count - 1)))
                        continue
                    raise error from e

                execution_time = time.perf_counter() - start_time

                # Update processor state after successful execution
                new_state = state.update_execution_time(
                    execution_time, self._config.stats_window_size
                )
                self._processor_states[processor] = new_state.model_copy(
                    update={
                        "retry_count": 0,
                        "last_timestamp": timestamp,
                        "max_consecutive_retries": max_consecutive_retries,
                    }
                )

                return

            except ProcessorTimeoutError:
                # Don't retry on timeout errors after all retries are exhausted
                break

            except Exception as e:
                last_error = e
                retry_count += 1
                max_consecutive_retries = max(max_consecutive_retries, retry_count)
                logger.warning(
                    "Processor %s error (retry %d/%d): %s",
                    processor,
                    retry_count,
                    self._config.max_retries,
                    e,
                )

                if retry_count <= self._config.max_retries:
                    await asyncio.sleep(0.1 * (2 ** (retry_count - 1)))
                else:
                    break

        if last_error:
            logger.error(
                "Processor %s failed after %d retries: %s",
                processor,
                retry_count,
                last_error,
            )
            new_state = state.record_error(last_error, timestamp)
            self._processor_states[processor] = new_state.model_copy(
                update={
                    "last_timestamp": timestamp,
                    "retry_count": retry_count,
                    "max_consecutive_retries": max_consecutive_retries,
                }
            )
            raise last_error

    async def _execute_tick(self, processors: list[TickProcessor]) -> None:
        """Execute a tick for all processors.

        Handles both concurrent and sequential execution based on config.
        Publishes a ClockTickEvent after all processors have been executed.
        """
        self._tick_counter += 1

        if self._config.concurrent_processors:
            tasks = [
                asyncio.create_task(
                    self._execute_processor(processor, self._current_tick)
                )
                for processor in processors
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors: list[Exception] = []

            for processor, result in zip(processors, results, strict=False):
                if isinstance(result, Exception):
                    if self._error_callback:
                        self._error_callback(processor, result)
                    errors.append(result)
                else:
                    state = self._processor_states[processor]
                    self._processor_states[processor] = state.model_copy(
                        update={"last_timestamp": self._current_tick}
                    )

            self.publish(
                self.tick_publication,
                ClockTickEvent(
                    timestamp=self._current_tick,
                    tick_counter=self._tick_counter,
                    processors=self.get_active_processors(),
                ),
            )

            if errors:
                raise errors[0]
        else:
            for processor in processors:
                try:
                    await self._execute_processor(processor, self._current_tick)
                    state = self._processor_states[processor]
                    self._processor_states[processor] = state.model_copy(
                        update={"last_timestamp": self._current_tick}
                    )
                except Exception as e:
                    if self._error_callback:
                        self._error_callback(processor, e)
                    raise

            self.publish(
                self.tick_publication,
                ClockTickEvent(
                    timestamp=self._current_tick,
                    tick_counter=self._tick_counter,
                    processors=self.get_active_processors(),
                ),
            )

    def _cleanup(self, error_occurred: bool = False) -> None:
        """Clean up the clock state.

        Resets all internal state so the clock can be reused after errors.
        Processor error information (error_count, last_error, etc.) is preserved
        across cleanup for diagnostics.
        """
        # Reset all processor states while preserving error information
        for processor in self._processors:
            state = self._processor_states.get(processor)
            if state is not None:
                self._processor_states[processor] = state.model_copy(
                    update={
                        "is_active": False,
                        "retry_count": 0,
                        "consecutive_errors": 0,
                    }
                )

        # Always fully reset clock state so it can be reused
        self._running = False
        self._started = False
        self._current_context = None
        self._task = None
        self._shutdown_event.clear()

    async def __aenter__(self) -> "BaseClock":
        """Enter the clock context."""
        if self._current_context is not None or self._running or self._started:
            raise ClockContextError("Clock is already in a context or running")

        logger.info(
            "Starting clock context (mode=%s, processors=%d)",
            self._config.clock_mode.name,
            len(self._processors),
        )
        try:
            self._current_context = []
            self._started = True
            self._running = False
            self._tick_counter = 0
            self._current_tick = (
                self._config.start_time
                if self._config.clock_mode is ClockMode.BACKTEST
                else (time.time() // self._config.tick_size) * self._config.tick_size
            )

            # Emit clock start event
            self.publish(
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

                # Await cleanup for processors that need async teardown
                for processor in self._current_context:
                    if hasattr(processor, "await_cleanup"):
                        try:
                            await processor.await_cleanup()
                        except Exception:
                            pass

            self._cleanup(error_occurred=error_occurred)

    def get_processor_stats(self, processor: TickProcessor) -> ProcessorStats | None:
        """Get detailed statistics for a processor.

        Returns None if the processor is not registered.
        Uses ProcessorState properties for correct calculations.
        """
        state = self._processor_states.get(processor)
        if not state:
            return None

        return ProcessorStats(
            total_ticks=state.total_ticks,
            successful_ticks=state.successful_ticks,
            failed_ticks=state.failed_ticks,
            error_count=state.error_count,
            consecutive_errors=state.consecutive_errors,
            retry_count=state.retry_count,
            max_consecutive_retries=state.max_consecutive_retries,
            avg_execution_time=state.avg_execution_time,
            max_execution_time=state.max_execution_time,
            std_dev_execution_time=state.std_dev_execution_time,
            error_rate=state.error_rate,
            last_error=state.last_error,
            last_error_time=state.last_error_time,
            last_success_time=state.last_success_time,
        )
