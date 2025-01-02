import statistics
from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class ProcessorState(BaseModel):
    """State and statistics of a tick processor within the clock."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, arbitrary_types_allowed=True
    )

    # State fields
    last_timestamp: float | None = Field(
        default=None, description="Last timestamp processed"
    )
    is_active: bool = Field(
        default=False, description="Whether the processor is active"
    )
    retry_count: int = Field(default=0, description="Number of consecutive retries")
    max_consecutive_retries: int = Field(
        default=0, description="Maximum number of consecutive retries reached"
    )
    execution_times: list[float] = Field(
        default_factory=list, description="Recent execution times"
    )
    error_count: int = Field(default=0, description="Number of errors encountered")
    consecutive_errors: int = Field(
        default=0, description="Number of consecutive errors"
    )
    last_error: str | None = Field(default=None, description="Last error message")
    last_error_time: datetime | None = Field(
        default=None, description="Time of last error"
    )
    last_success_time: datetime | None = Field(
        default=None, description="Time of last successful execution"
    )

    @property
    def total_ticks(self) -> int:
        """Get the total number of ticks processed."""
        return len(self.execution_times) + self.error_count

    @property
    def successful_ticks(self) -> int:
        """Number of successful ticks."""
        return len(self.execution_times)

    @property
    def failed_ticks(self) -> int:
        """Number of failed ticks."""
        return self.error_count

    @property
    def total_execution_time(self) -> float:
        """Total execution time of successful ticks."""
        return sum(self.execution_times) if self.execution_times else 0.0

    @property
    def avg_execution_time(self) -> float:
        """Average execution time of successful ticks."""
        return (
            self.total_execution_time / len(self.execution_times)
            if self.execution_times
            else 0.0
        )

    @property
    def max_execution_time(self) -> float:
        """Maximum execution time of successful ticks."""
        return max(self.execution_times) if self.execution_times else 0.0

    @property
    def std_dev_execution_time(self) -> float:
        """Standard deviation of execution times."""
        return (
            statistics.stdev(self.execution_times)
            if len(self.execution_times) > 1
            else 0.0
        )

    @property
    def error_rate(self) -> float:
        """Error rate as a percentage of total ticks."""
        total = self.total_ticks
        return (self.error_count / total * 100) if total > 0 else 0.0

    def get_execution_percentile(self, percentile: float) -> float:
        """Get a specific percentile of execution times.

        Args:
            percentile: The percentile to calculate (0-100)

        Returns:
            The execution time at the specified percentile
        """
        if not self.execution_times:
            return 0.0
        if len(self.execution_times) == 1:
            return self.execution_times[0]

        # Convert percentile to quantile (e.g., 95 -> 0.95)
        quantile = percentile / 100
        sorted_times = sorted(self.execution_times)
        idx = quantile * (len(sorted_times) - 1)
        if idx.is_integer():
            return sorted_times[int(idx)]
        # Interpolate between two values
        lower_idx = int(idx)
        fraction = idx - lower_idx
        return (1 - fraction) * sorted_times[lower_idx] + fraction * sorted_times[
            lower_idx + 1
        ]

    def update_execution_time(
        self, execution_time: float, window_size: int
    ) -> "ProcessorState":
        """Update execution times list while maintaining window size."""
        execution_times = list(self.execution_times)
        if len(execution_times) >= window_size:
            execution_times = execution_times[-window_size + 1 :]
        execution_times.append(execution_time)

        # Reset error tracking on successful execution
        return ProcessorState(
            **self.model_copy(
                update={
                    "execution_times": execution_times,
                    "consecutive_errors": 0,
                    "last_success_time": datetime.now(),
                }
            ).model_dump()
        )

    def record_error(self, error: Exception, timestamp: float) -> "ProcessorState":
        """Record an error occurrence."""
        now = datetime.fromtimestamp(timestamp)
        return ProcessorState(
            **self.model_copy(
                update={
                    "error_count": self.error_count + 1,
                    "consecutive_errors": self.consecutive_errors + 1,
                    "last_error": str(error),
                    "last_error_time": now,
                }
            ).model_dump()
        )

    def update_retry_count(self, retry_count: int) -> "ProcessorState":
        """Update retry count and track maximum consecutive retries."""
        return ProcessorState(
            **self.model_copy(
                update={
                    "retry_count": retry_count,
                    "max_consecutive_retries": max(
                        self.max_consecutive_retries, retry_count
                    ),
                }
            ).model_dump()
        )

    def reset_retries(self) -> "ProcessorState":
        """Reset retry count after successful execution."""
        return ProcessorState(**self.model_copy(update={"retry_count": 0}).model_dump())
