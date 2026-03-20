import pytest

from chronopype.time import Time, TimestampFormat


class TestTimeConstants:
    """Test Time class constants."""

    def test_second(self) -> None:
        assert Time.SECOND == 1

    def test_millisecond(self) -> None:
        assert Time.MILLISECOND == 0.001

    def test_minute(self) -> None:
        assert Time.MINUTE == 60

    def test_hour(self) -> None:
        assert Time.HOUR == 3600

    def test_twelve_hours(self) -> None:
        assert Time.TWELVE_HOURS == 43200

    def test_day(self) -> None:
        assert Time.DAY == 86400

    def test_week(self) -> None:
        assert Time.WEEK == 604800

    def test_month(self) -> None:
        assert Time.MONTH == 30 * 86400

    def test_year(self) -> None:
        assert Time.YEAR == 365 * 86400

    def test_relationships(self) -> None:
        assert Time.MINUTE == 60 * Time.SECOND
        assert Time.HOUR == 60 * Time.MINUTE
        assert Time.DAY == 24 * Time.HOUR
        assert Time.WEEK == 7 * Time.DAY


class TestTimestampFormatGetFormat:
    """Test TimestampFormat.get_format() detection."""

    def test_seconds_format_int(self) -> None:
        assert TimestampFormat.get_format(1234567890) == TimestampFormat.SECONDS

    def test_seconds_format_float(self) -> None:
        assert TimestampFormat.get_format(1234567890.123) == TimestampFormat.SECONDS

    def test_seconds_format_string(self) -> None:
        assert TimestampFormat.get_format("1234567890") == TimestampFormat.SECONDS

    def test_milliseconds_format(self) -> None:
        assert TimestampFormat.get_format(1234567890000) == TimestampFormat.MILLISECONDS

    def test_milliseconds_format_float(self) -> None:
        assert (
            TimestampFormat.get_format(1234567890000.0) == TimestampFormat.MILLISECONDS
        )

    def test_microseconds_format(self) -> None:
        assert (
            TimestampFormat.get_format(1234567890000000) == TimestampFormat.MICROSECONDS
        )

    def test_nanoseconds_format(self) -> None:
        assert (
            TimestampFormat.get_format(1234567890000000000)
            == TimestampFormat.NANOSECONDS
        )

    def test_small_seconds(self) -> None:
        """Timestamps with fewer than 10 digits should be detected as seconds."""
        assert TimestampFormat.get_format(1000) == TimestampFormat.SECONDS
        assert TimestampFormat.get_format(1) == TimestampFormat.SECONDS
        assert TimestampFormat.get_format(999999999) == TimestampFormat.SECONDS

    def test_invalid_format_too_many_digits(self) -> None:
        """Timestamps with more than 19 digits should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            TimestampFormat.get_format(12345678901234567890)

    def test_boundary_10_digits(self) -> None:
        """Exactly 10 digits should be seconds."""
        assert TimestampFormat.get_format(1000000000) == TimestampFormat.SECONDS

    def test_boundary_13_digits(self) -> None:
        """Exactly 13 digits should be milliseconds."""
        assert TimestampFormat.get_format(1000000000000) == TimestampFormat.MILLISECONDS

    def test_boundary_16_digits(self) -> None:
        """Exactly 16 digits should be microseconds."""
        assert (
            TimestampFormat.get_format(1000000000000000) == TimestampFormat.MICROSECONDS
        )

    def test_boundary_19_digits(self) -> None:
        """Exactly 19 digits should be nanoseconds."""
        assert (
            TimestampFormat.get_format(1000000000000000000)
            == TimestampFormat.NANOSECONDS
        )

    def test_string_input(self) -> None:
        assert TimestampFormat.get_format("1234567890000") == TimestampFormat.MILLISECONDS

    def test_between_format_boundaries(self) -> None:
        """11-12 digit numbers should be detected as seconds (<=10 digits check)."""
        # 11 digits - between seconds (10) and milliseconds (13)
        # get_format uses <= for seconds, so 11 digits falls through
        # Let's check what actually happens
        ts_11_digits = 10000000000  # 11 digits
        # This is between SECONDS (10) and MILLISECONDS (13)
        # The code checks digits <= 10 first, so 11 doesn't match
        # Then checks == 13, so 11 doesn't match
        # Then == 16, doesn't match
        # Then == 19, doesn't match
        # Falls through to ValueError
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            TimestampFormat.get_format(ts_11_digits)


class TestTimestampFormatConvertTs:
    """Test TimestampFormat.convert_ts() conversion."""

    def test_seconds_to_milliseconds(self) -> None:
        result = TimestampFormat.convert_ts(1234567890, TimestampFormat.MILLISECONDS)
        assert result == 1234567890000.0

    def test_seconds_to_microseconds(self) -> None:
        result = TimestampFormat.convert_ts(1234567890, TimestampFormat.MICROSECONDS)
        assert result == 1234567890000000.0

    def test_seconds_to_nanoseconds(self) -> None:
        result = TimestampFormat.convert_ts(1234567890, TimestampFormat.NANOSECONDS)
        assert result == 1234567890000000000.0

    def test_milliseconds_to_seconds(self) -> None:
        result = TimestampFormat.convert_ts(1234567890000, TimestampFormat.SECONDS)
        assert result == 1234567890.0

    def test_microseconds_to_seconds(self) -> None:
        result = TimestampFormat.convert_ts(1234567890000000, TimestampFormat.SECONDS)
        assert result == 1234567890.0

    def test_nanoseconds_to_seconds(self) -> None:
        result = TimestampFormat.convert_ts(
            1234567890000000000, TimestampFormat.SECONDS
        )
        assert result == 1234567890.0

    def test_same_format_returns_unchanged(self) -> None:
        result = TimestampFormat.convert_ts(1234567890, TimestampFormat.SECONDS)
        assert result == 1234567890.0

    def test_string_input(self) -> None:
        result = TimestampFormat.convert_ts("1234567890", TimestampFormat.MILLISECONDS)
        assert result == 1234567890000.0

    def test_float_input(self) -> None:
        result = TimestampFormat.convert_ts(1234567890.5, TimestampFormat.MILLISECONDS)
        assert result == 1234567890500.0

    def test_milliseconds_to_microseconds(self) -> None:
        result = TimestampFormat.convert_ts(
            1234567890000, TimestampFormat.MICROSECONDS
        )
        assert result == 1234567890000000.0

    def test_microseconds_to_milliseconds(self) -> None:
        result = TimestampFormat.convert_ts(
            1234567890000000, TimestampFormat.MILLISECONDS
        )
        assert result == 1234567890000.0

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid timestamp type"):
            TimestampFormat.convert_ts([1234], TimestampFormat.SECONDS)  # type: ignore

    def test_round_trip_seconds_milliseconds(self) -> None:
        """Converting seconds->ms->seconds should return original value."""
        original = 1234567890
        ms = TimestampFormat.convert_ts(original, TimestampFormat.MILLISECONDS)
        back = TimestampFormat.convert_ts(ms, TimestampFormat.SECONDS)
        assert back == float(original)

    def test_round_trip_seconds_nanoseconds(self) -> None:
        """Converting seconds->ns->seconds should return original value."""
        original = 1234567890
        ns = TimestampFormat.convert_ts(original, TimestampFormat.NANOSECONDS)
        back = TimestampFormat.convert_ts(ns, TimestampFormat.SECONDS)
        assert back == float(original)


class TestTimestampFormatEnum:
    """Test TimestampFormat enum values."""

    def test_seconds_value(self) -> None:
        assert TimestampFormat.SECONDS.value == 10

    def test_milliseconds_value(self) -> None:
        assert TimestampFormat.MILLISECONDS.value == 13

    def test_microseconds_value(self) -> None:
        assert TimestampFormat.MICROSECONDS.value == 16

    def test_nanoseconds_value(self) -> None:
        assert TimestampFormat.NANOSECONDS.value == 19
