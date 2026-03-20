import asyncio
import logging
import time
from collections.abc import Callable

from chronopype.clocks.base import BaseClock
from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.exceptions import ClockError
from chronopype.processors.base import TickProcessor

logger = logging.getLogger(__name__)


class RealtimeClock(BaseClock):
    """Clock implementation for realtime mode."""

    start_publication = BaseClock.start_publication
    tick_publication = BaseClock.tick_publication
    stop_publication = BaseClock.stop_publication

    def __init__(
        self,
        config: ClockConfig,
        error_callback: Callable[[TickProcessor, Exception], None] | None = None,
    ) -> None:
        """Initialize a new RealtimeClock instance."""
        if config.clock_mode != ClockMode.REALTIME:
            raise ClockError("RealtimeClock requires REALTIME mode")
        super().__init__(config, error_callback)

    async def run(self) -> None:
        """Run the clock indefinitely."""
        try:
            await self.run_til(float("inf"))
        except asyncio.CancelledError:
            # Ensure we're properly cleaned up
            self._shutdown_event.set()
            if self._running:
                self._running = False
                self._task = None
            raise  # Re-raise to ensure proper cancellation

    async def run_til(self, target_time: float) -> None:
        """Run the clock until the target time."""
        if self._task is not None:
            raise ClockError("Clock is already running")

        if self._current_context is None:
            raise ClockError("Clock must be started in a context")

        self._running = True
        self._started = True

        # Ensure all processors in context have been started
        for processor in list(self._current_context):
            if processor._state.is_active:
                continue
            try:
                processor.start(self._current_tick)
            except Exception as e:
                self._processors.remove(processor)
                self._processor_states.pop(processor, None)
                raise ClockError(f"Failed to start processor: {str(e)}") from e

        # Calculate the actual target time based on current time
        current_time = time.time()
        duration = target_time - self._current_tick
        actual_target = current_time + duration

        self._task = asyncio.create_task(
            self._run_til_impl(actual_target, self._current_context)
        )

        # Activate all processors
        for processor in self._current_context:
            state = self._processor_states[processor]
            self._processor_states[processor] = state.model_copy(
                update={"is_active": True}
            )

        try:
            await self._task
        finally:
            self._task = None

    async def _run_til_impl(
        self, target_time: float, processors: list[TickProcessor]
    ) -> None:
        """Run the clock until a specific timestamp."""
        if not self._running:
            raise ClockError("Clock must be started.")

        while time.time() < target_time:
            processors = [p for p in processors if self._processor_states[p].is_active]
            await self._execute_tick(processors)
            await self._wait_next_tick()

    async def _wait_next_tick(self) -> float:
        """Wait until the next tick."""
        current_time = time.time()
        next_tick = (
            current_time // self._config.tick_size + 1
        ) * self._config.tick_size
        wait_time = next_tick - current_time

        if wait_time > 0:
            try:
                await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                raise

        # Account for any drift that occurred during sleep
        actual_time = time.time()
        if actual_time > next_tick:
            ticks_passed = int((actual_time - next_tick) / self._config.tick_size)
            if ticks_passed > 0:
                logger.debug(
                    "Clock drift detected: skipped %d ticks (drift=%.3fs)",
                    ticks_passed,
                    actual_time - next_tick,
                )
            next_tick += (ticks_passed + 1) * self._config.tick_size

        self._current_tick = actual_time
        return next_tick
