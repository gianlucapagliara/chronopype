import asyncio
import logging
from collections.abc import Callable

from chronopype.clocks.base import BaseClock
from chronopype.clocks.config import FLOAT_EPSILON, ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.exceptions import ClockError
from chronopype.processors.base import TickProcessor

logger = logging.getLogger(__name__)


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

        logger.debug(
            "Backtest running %d ticks (%.1f -> %.1f)",
            num_ticks,
            self._current_tick,
            target_time,
        )

        # Execute ticks
        for _ in range(num_ticks):
            self._current_tick += self._config.tick_size
            processors = [p for p in processors if self._processor_states[p].is_active]
            await self._execute_tick(processors)

        # Set final timestamp to exactly match target_time
        if (
            abs(self._current_tick - target_time) > FLOAT_EPSILON
        ):  # Handle floating point precision
            self._current_tick = target_time
            processors = [p for p in processors if self._processor_states[p].is_active]
            await self._execute_tick(processors)

    async def step(self, n: int = 1) -> float:
        """Advance the clock by exactly n ticks.

        Executes all registered processors for each tick. Unlike run_til(),
        this method does not create an internal asyncio.Task or set the clock
        to a "running" state, allowing the caller to control tick advancement.

        Args:
            n: Number of ticks to advance. Must be >= 1.

        Returns:
            The new current timestamp after advancing.

        Raises:
            ClockError: If the clock is not in a context, if n < 1, or if
                advancing n ticks would exceed end_time.
        """
        if not self._current_context:
            raise ClockError("Clock must be started in a context")

        if n < 1:
            raise ClockError("Number of ticks must be at least 1")

        target_tick = self._current_tick + n * self._config.tick_size
        if target_tick > self._config.end_time + FLOAT_EPSILON:
            raise ClockError("Cannot step past end_time")

        for _ in range(n):
            self._current_tick += self._config.tick_size
            processors = [
                p for p in self._current_context if self._processor_states[p].is_active
            ]
            await self._execute_tick(processors)

        return self._current_tick

    async def step_to(self, target_time: float) -> float:
        """Advance the clock to the given timestamp.

        Unlike run_til(), this method does not create an internal asyncio.Task
        or set the clock to a "running" state. It simply executes ticks
        sequentially until the target time is reached.

        Args:
            target_time: The timestamp to advance to.

        Returns:
            The new current timestamp after advancing.

        Raises:
            ClockError: If the clock is not in a context, or if target_time
                exceeds end_time.
        """
        if not self._current_context:
            raise ClockError("Clock must be started in a context")

        if target_time > self._config.end_time + FLOAT_EPSILON:
            raise ClockError("Cannot step past end_time")

        num_ticks = int((target_time - self._current_tick) / self._config.tick_size)
        if num_ticks <= 0:
            return self._current_tick

        for _ in range(num_ticks):
            self._current_tick += self._config.tick_size
            processors = [
                p for p in self._current_context if self._processor_states[p].is_active
            ]
            await self._execute_tick(processors)

        # Handle floating-point remainder: align to target_time if needed
        if abs(self._current_tick - target_time) > FLOAT_EPSILON:
            self._current_tick = target_time
            processors = [
                p for p in self._current_context if self._processor_states[p].is_active
            ]
            await self._execute_tick(processors)

        return self._current_tick

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
