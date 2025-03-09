import asyncio
from collections.abc import Callable

from chronopype.clocks.base import BaseClock, ClockTickEvent
from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.exceptions import ClockError
from chronopype.processors.base import TickProcessor


class BacktestClock(BaseClock):
    """Clock implementation for backtesting mode."""

    start_publication = BaseClock.start_publication
    tick_publication = BaseClock.tick_publication
    stop_publication = BaseClock.stop_publication

    def __init__(
        self,
        config: ClockConfig,
        error_callback: Callable[[TickProcessor, Exception], None] | None = None,
    ) -> None:
        """Initialize a new BacktestClock instance."""
        if config.clock_mode != ClockMode.BACKTEST:
            raise ClockError("BacktestClock requires BACKTEST mode")
        if config.end_time <= 0:
            raise ClockError("end_time must be set for backtest mode")
        super().__init__(config, error_callback)

    async def run(self) -> None:
        """Run the clock until end_time."""
        await self.run_til(self._config.end_time)

    async def run_til(self, target_time: float) -> None:
        """Run the clock until the target time."""
        if self._task is not None:
            raise ClockError("Clock is already running")

        if not self._current_context:
            raise ClockError("Clock must be started in a context")

        if target_time > self._config.end_time:
            raise ClockError("Cannot run past end_time in backtest mode")

        self._running = True
        self._started = True
        self._task = asyncio.create_task(
            self._run_til_impl(target_time, self._current_context)
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
            raise ClockError("Clock must be started in a context.")

        # Calculate number of ticks needed
        num_ticks = int((target_time - self._current_tick) / self._config.tick_size)
        if num_ticks <= 0:
            return

        # Execute ticks
        for _ in range(num_ticks):
            self._current_tick += self._config.tick_size
            processors = [p for p in processors if self._processor_states[p].is_active]
            await self._execute_tick(processors)

        # Set final timestamp to exactly match target_time
        if (
            abs(self._current_tick - target_time) > 1e-10
        ):  # Handle floating point precision
            self._current_tick = target_time
            processors = [p for p in processors if self._processor_states[p].is_active]
            await self._execute_tick(processors)

    async def _execute_tick(self, processors: list[TickProcessor]) -> None:
        """Execute a tick for all processors."""
        self._tick_counter += 1

        if self._config.concurrent_processors:
            # Execute processors concurrently
            tasks = []
            for processor in processors:
                task = asyncio.create_task(
                    self._execute_processor(processor, self._current_tick)
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = []

            # Update states for all processors first
            for processor, result in zip(processors, results, strict=False):
                if isinstance(result, Exception):
                    if self._error_callback:
                        self._error_callback(processor, result)
                    errors.append(result)
                else:
                    # Update processor state after successful execution
                    state = self._processor_states[processor]
                    self._processor_states[processor] = state.model_copy(
                        update={"last_timestamp": self._current_tick}
                    )

            # Emit tick event after all processors have been executed
            self.publish(
                self.tick_publication,
                ClockTickEvent(
                    timestamp=self._current_tick,
                    tick_counter=self._tick_counter,
                    processors=self.get_active_processors(),
                ),
            )

            # Raise the first error if any occurred
            if errors:
                raise errors[0]
        else:
            # Execute processors sequentially
            for processor in processors:
                try:
                    await self._execute_processor(processor, self._current_tick)
                    # Update processor state after successful execution
                    state = self._processor_states[processor]
                    self._processor_states[processor] = state.model_copy(
                        update={"last_timestamp": self._current_tick}
                    )
                except Exception as e:
                    if self._error_callback:
                        self._error_callback(processor, e)
                    raise e

            # Emit tick event after all processors have been executed
            self.publish(
                self.tick_publication,
                ClockTickEvent(
                    timestamp=self._current_tick,
                    tick_counter=self._tick_counter,
                    processors=self.get_active_processors(),
                ),
            )

    async def fast_forward(self, seconds: float) -> None:
        """Fast forward the clock by a specified number of seconds."""
        if not self._current_context:
            raise ClockError("Fast forward can only be used within a context")

        if seconds <= 0:
            return

        target_time = self._current_tick + seconds
        if target_time > self._config.end_time:
            raise ClockError("Cannot fast forward past end_time in backtest mode")

        await self.run_til(target_time)
