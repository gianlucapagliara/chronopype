from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from chronopype.clocks.modes import ClockMode


class ClockConfig(BaseModel):
    """Configuration for Clock initialization."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    clock_mode: ClockMode
    tick_size: float = Field(
        default=1.0, gt=0, description="Time interval of each tick in seconds"
    )
    start_time: float = Field(default=0.0, description="Start time in UNIX timestamp")
    end_time: float = Field(
        default=0.0, description="End time in UNIX timestamp (0 for no end)"
    )
    processor_timeout: float = Field(
        default=1.0, description="Timeout for each processor execution in seconds"
    )
    max_retries: int = Field(
        default=3, description="Maximum number of retries for failed processors"
    )
    concurrent_processors: bool = Field(
        default=False, description="Whether to run processors concurrently"
    )
    stats_window_size: int = Field(
        default=100, description="Number of executions to keep for statistics"
    )

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v: float, info: ValidationInfo) -> float:
        """Validate that end_time is greater than or equal to start_time if specified."""
        if v != 0 and v < info.data.get("start_time", 0):
            raise ValueError("end_time must be greater than or equal to start_time")
        return v
