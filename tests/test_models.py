from datetime import datetime

import pytest
from pydantic import ValidationError

from chronopype.clocks.modes import ClockMode
from chronopype.models import ClockConfig, ProcessorState


def test_clock_config_validation() -> None:
    """Test ClockConfig validation."""
    # Test valid config
    config = ClockConfig(clock_mode=ClockMode.BACKTEST)
    assert config.tick_size == 1.0  # default value
    assert config.start_time == 0.0  # default value
    assert config.end_time == 0.0  # default value

    # Test invalid tick size
    with pytest.raises(ValidationError) as exc_info:
        ClockConfig(clock_mode=ClockMode.BACKTEST, tick_size=0)
    assert "tick_size" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        ClockConfig(clock_mode=ClockMode.BACKTEST, tick_size=-1)
    assert "tick_size" in str(exc_info.value)

    # Test invalid time range
    with pytest.raises(ValidationError) as exc_info:
        ClockConfig(clock_mode=ClockMode.BACKTEST, start_time=10.0, end_time=5.0)
    assert "end_time" in str(exc_info.value)


def test_clock_config_immutability() -> None:
    """Test that ClockConfig is immutable."""
    config = ClockConfig(clock_mode=ClockMode.BACKTEST)

    with pytest.raises(ValidationError) as exc_info:
        config.tick_size = 2.0
    assert "frozen_instance" in str(exc_info.value)

    # Test copy and update using model_copy
    new_config = config.model_copy(update={"tick_size": 2.0})
    assert new_config.tick_size == 2.0
    assert config.tick_size == 1.0  # Original unchanged


def test_processor_state_validation() -> None:
    """Test ProcessorState validation."""
    # Test valid state
    state = ProcessorState()
    assert state.last_timestamp is None
    assert not state.is_active
    assert state.retry_count == 0
    assert state.error_count == 0
    assert state.consecutive_errors == 0
    assert state.max_consecutive_retries == 0
    assert state.last_success_time is None

    # Test with values
    now = datetime.now()
    state = ProcessorState(
        last_timestamp=1000.0,
        is_active=True,
        retry_count=2,
        error_count=1,
        consecutive_errors=1,
        max_consecutive_retries=2,
        last_error="Test error",
        last_error_time=now,
        last_success_time=now,
    )
    assert state.last_timestamp == 1000.0
    assert state.is_active
    assert state.retry_count == 2
    assert state.error_count == 1
    assert state.consecutive_errors == 1
    assert state.max_consecutive_retries == 2
    assert state.last_error == "Test error"
    assert state.last_error_time == now
    assert state.last_success_time == now


def test_processor_state_immutability() -> None:
    """Test that ProcessorState is immutable."""
    state = ProcessorState(last_timestamp=1000.0)

    with pytest.raises(ValidationError) as exc_info:
        state.last_timestamp = 2000.0
    assert "frozen_instance" in str(exc_info.value)

    # Test copy and update using model_copy
    new_state = state.model_copy(update={"last_timestamp": 2000.0})
    assert new_state.last_timestamp == 2000.0
    assert state.last_timestamp == 1000.0  # Original unchanged


def test_processor_state_execution_times() -> None:
    """Test execution times list in ProcessorState."""
    state = ProcessorState(execution_times=[0.1, 0.2, 0.3])
    assert len(state.execution_times) == 3
    assert sum(state.execution_times) == 0.6

    # Test empty list
    state = ProcessorState()
    assert len(state.execution_times) == 0


def test_processor_state_statistics() -> None:
    """Test ProcessorState statistics calculations."""
    state = ProcessorState(execution_times=[0.1, 0.2, 0.3, 0.4, 0.5])

    # Test basic statistics
    assert state.total_ticks == 5
    assert state.successful_ticks == 5
    assert state.failed_ticks == 0
    assert state.total_execution_time == 1.5
    assert state.avg_execution_time == 0.3
    assert state.max_execution_time == 0.5
    assert pytest.approx(state.std_dev_execution_time, 0.01) == 0.1581
    assert state.error_rate == 0.0

    # Test with errors
    state = state.record_error(Exception("test"), 1000.0)
    assert state.total_ticks == 6
    assert state.successful_ticks == 5
    assert state.failed_ticks == 1
    assert state.error_rate == pytest.approx(16.67, 0.01)  # 1/6 * 100


def test_processor_state_percentiles() -> None:
    """Test ProcessorState percentile calculations."""
    state = ProcessorState(execution_times=[0.1, 0.2, 0.3, 0.4, 0.5])

    # Test various percentiles
    assert state.get_execution_percentile(0) == 0.1
    assert state.get_execution_percentile(50) == 0.3
    assert state.get_execution_percentile(100) == 0.5
    assert state.get_execution_percentile(25) == 0.2
    assert state.get_execution_percentile(75) == 0.4

    # Test empty state
    empty_state = ProcessorState()
    assert empty_state.get_execution_percentile(50) == 0.0

    # Test single value
    single_state = ProcessorState(execution_times=[0.1])
    assert single_state.get_execution_percentile(50) == 0.1


def test_processor_state_error_tracking() -> None:
    """Test ProcessorState error tracking."""
    state = ProcessorState()

    # Test error recording
    state = state.record_error(Exception("test1"), 1000.0)
    assert state.error_count == 1
    assert state.consecutive_errors == 1
    assert state.last_error == "test1"

    # Test consecutive errors
    state = state.record_error(Exception("test2"), 2000.0)
    assert state.error_count == 2
    assert state.consecutive_errors == 2

    # Test error reset on success
    state = state.update_execution_time(0.1, 100)
    assert state.error_count == 2  # Total errors unchanged
    assert state.consecutive_errors == 0  # Reset consecutive errors
    assert state.last_success_time is not None


def test_processor_state_retry_tracking() -> None:
    """Test ProcessorState retry tracking."""
    state = ProcessorState()

    # Test retry count update
    state = state.update_retry_count(1)
    assert state.retry_count == 1
    assert state.max_consecutive_retries == 1

    # Test max retries tracking
    state = state.update_retry_count(3)
    assert state.retry_count == 3
    assert state.max_consecutive_retries == 3

    # Test retry reset
    state = state.reset_retries()
    assert state.retry_count == 0
    assert state.max_consecutive_retries == 3  # Max value preserved


def test_clock_config_defaults() -> None:
    """Test ClockConfig default values."""
    config = ClockConfig(clock_mode=ClockMode.BACKTEST)

    assert config.tick_size == 1.0
    assert config.start_time == 0.0
    assert config.end_time == 0.0
    assert config.processor_timeout == 1.0
    assert config.max_retries == 3
    assert not config.concurrent_processors
    assert config.stats_window_size == 100
