import asyncio
from collections.abc import Callable

from ..exceptions import ClockError
from ..models import ClockConfig
from ..processors.base import TickProcessor
from .base import BaseClock
from .modes import ClockMode


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

    def start(self) -> None:
        """Start the clock."""
        if not self._current_context:
            raise ClockError("Clock must be started in a context")
        self._started = True

    def stop(self) -> None:
        """Stop the clock."""
        self._started = False
        self._running = False

    def tick(self) -> None:
        """Process a clock tick."""
        if not self._started:
            raise ClockError("Clock not started")
        self._tick_counter += 1
        self._current_tick += self._config.tick_size

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

        processors = [p for p in processors if self._processor_states[p].is_active]
        if not processors:
            return

        # Calculate number of ticks needed
        num_ticks = int((target_time - self._current_tick) / self._config.tick_size)
        if num_ticks <= 0:
            return

        # Execute ticks
        for _ in range(num_ticks):
            self._current_tick += self._config.tick_size
            await self._execute_tick(processors)
            self._tick_counter += 1

        # Set final timestamp to exactly match target_time
        if (
            abs(self._current_tick - target_time) > 1e-10
        ):  # Handle floating point precision
            self._current_tick = target_time
            await self._execute_tick(processors)
            self._tick_counter += 1

    async def _execute_tick(self, processors: list[TickProcessor]) -> None:
        """Execute a tick for all processors."""
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
