"""Configuration for ClockRuntime."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from chronopype.clocks.modes import ClockMode


class ClockRuntimeConfig(BaseModel):
    """Configuration for ClockRuntime lifecycle management.

    Contains both clock-level parameters (used to build a ``ClockConfig``
    when no pre-built clock is provided) and runtime-level parameters
    (thread timeouts, poll intervals).
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    clock_mode: ClockMode = Field(
        default=ClockMode.REALTIME,
        description="Clock mode (REALTIME or BACKTEST)",
    )
    tick_size: float = Field(
        default=1.0,
        gt=0,
        description="Time interval of each tick in seconds",
    )
    start_time: float = Field(
        default=0.0,
        description="Start time in UNIX timestamp",
    )
    end_time: float = Field(
        default=0.0,
        description="End time in UNIX timestamp (0 for no end)",
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
