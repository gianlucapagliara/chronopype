"""Configuration for ClockRuntime."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode


class ClockRuntimeConfig(BaseModel):
    """Configuration for ClockRuntime lifecycle management.

    Composes a ``ClockConfig`` for clock-level parameters and adds
    runtime-level parameters (thread timeouts, poll intervals).
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    clock_config: ClockConfig = Field(
        default_factory=lambda: ClockConfig(clock_mode=ClockMode.REALTIME),
        description="Clock configuration (mode, tick size, start/end time, etc.)",
    )
    thread_stop_timeout_seconds: float = Field(
        default=3.0,
        gt=0,
        description="Max seconds to wait for clock thread to stop",
    )
    clock_poll_interval_seconds: float = Field(
        default=0.1,
        gt=0,
        description="Polling interval (seconds) for clock loop stop-event check",
    )

    @property
    def clock_mode(self) -> ClockMode:
        """Shortcut for ``clock_config.clock_mode``."""
        return self.clock_config.clock_mode

    @property
    def tick_size(self) -> float:
        """Shortcut for ``clock_config.tick_size``."""
        return self.clock_config.tick_size

    @property
    def start_time(self) -> float:
        """Shortcut for ``clock_config.start_time``."""
        return self.clock_config.start_time

    @property
    def end_time(self) -> float:
        """Shortcut for ``clock_config.end_time``."""
        return self.clock_config.end_time
