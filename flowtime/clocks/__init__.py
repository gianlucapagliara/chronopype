"""Clock implementations package."""

from .backtest import BacktestClock
from .base import BaseClock
from .modes import ClockMode
from .realtime import RealtimeClock

# Registry mapping clock modes to their implementations
CLOCK_REGISTRY: dict[ClockMode, type[BaseClock]] = {
    ClockMode.BACKTEST: BacktestClock,
    ClockMode.REALTIME: RealtimeClock,
}


def get_clock_class(mode: ClockMode) -> type[BaseClock]:
    """Get the clock class for a given mode.

    Args:
        mode: The clock mode to get the implementation for.

    Returns:
        The clock class for the given mode.

    Raises:
        ValueError: If no implementation exists for the given mode.
    """
    if mode not in CLOCK_REGISTRY:
        raise ValueError(f"No clock implementation found for mode: {mode}")
    return CLOCK_REGISTRY[mode]


__all__ = ["BaseClock", "BacktestClock", "RealtimeClock", "ClockMode"]
