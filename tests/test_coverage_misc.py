"""Tests for miscellaneous uncovered lines."""

import importlib
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

import pytest

from chronopype.clocks import BacktestClock, RealtimeClock, get_clock_class
from chronopype.clocks.modes import ClockMode


# --- chronopype/__init__.py lines 17-18: PackageNotFoundError fallback ---


def test_version_fallback():
    with patch("importlib.metadata.version", side_effect=PackageNotFoundError):
        import chronopype

        importlib.reload(chronopype)
        assert chronopype.__version__ == "0.0.0"
    # Restore normal state
    importlib.reload(chronopype)


# --- chronopype/clocks/__init__.py lines 27-29: get_clock_class ---


def test_get_clock_class_backtest():
    assert get_clock_class(ClockMode.BACKTEST) is BacktestClock


def test_get_clock_class_realtime():
    assert get_clock_class(ClockMode.REALTIME) is RealtimeClock


def test_get_clock_class_invalid():
    with pytest.raises(ValueError, match="No clock implementation"):
        get_clock_class("invalid")  # type: ignore
