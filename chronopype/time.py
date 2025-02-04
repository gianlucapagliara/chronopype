from enum import Enum


class Time:
    """Time constants for various time units in seconds.

    This class provides a collection of commonly used time unit constants,
    all expressed in seconds for consistent time calculations.

    Attributes:
        SECOND (float): One second (1.0)
        MILLISECOND (float): One millisecond (0.001 seconds)
        MINUTE (float): One minute (60 seconds)
        HOUR (float): One hour (3600 seconds)
        TWELVE_HOURS (float): Twelve hours (43200 seconds)
        DAY (float): One day (86400 seconds)
        WEEK (float): One week (604800 seconds)
        MONTH (float): One month, approximated as 30 days (2592000 seconds)
        YEAR (float): One year, approximated as 365 days (31536000 seconds)
    """

    SECOND = 1
    MILLISECOND = SECOND / 1000
    MINUTE = 60 * SECOND
    HOUR = 60 * MINUTE
    TWELVE_HOURS = HOUR * 12
    DAY = 24 * HOUR
    WEEK = 7 * DAY
    MONTH = 30 * DAY
    YEAR = 365 * DAY


class TimestampFormat(Enum):
    """Enumeration of timestamp formats based on their digit length.

    This enum defines different timestamp formats and provides utilities
    for format detection and conversion between formats.

    Attributes:
        SECONDS (int): Format for timestamps in seconds (10 digits)
        MILLISECONDS (int): Format for timestamps in milliseconds (13 digits)
        MICROSECONDS (int): Format for timestamps in microseconds (16 digits)
        NANOSECONDS (int): Format for timestamps in nanoseconds (19 digits)
    """

    SECONDS = 10
    MILLISECONDS = 13
    MICROSECONDS = 16
    NANOSECONDS = 19

    @staticmethod
    def get_format(ts: float | int | str) -> "TimestampFormat":
        """Determine the timestamp format based on the number of digits.

        Args:
            ts: The timestamp to analyze. Can be a float, int, or string.

        Returns:
            TimestampFormat: The detected timestamp format.

        Raises:
            ValueError: If the timestamp format cannot be determined based on its digits.
        """
        digits = len(str(int(ts)))

        if digits <= TimestampFormat.SECONDS.value:
            return TimestampFormat.SECONDS
        elif digits == TimestampFormat.MILLISECONDS.value:
            return TimestampFormat.MILLISECONDS
        elif digits == TimestampFormat.MICROSECONDS.value:
            return TimestampFormat.MICROSECONDS
        elif digits == TimestampFormat.NANOSECONDS.value:
            return TimestampFormat.NANOSECONDS
        else:
            raise ValueError(
                f"Invalid timestamp format: {ts}. Expected s, ms, us or ns timestamp"
            )

    @staticmethod
    def convert_ts(
        timestamp: str | int | float,
        out_format: "TimestampFormat",
    ) -> str | int | float:
        """Convert a timestamp from one format to another.

        This method detects the input timestamp format and converts it to the
        specified output format by applying the appropriate scaling factor.

        Args:
            timestamp: The timestamp to convert. Can be a string, integer, or float.
            out_format: The desired output TimestampFormat.

        Returns:
            The converted timestamp in the specified format, preserving the input type.

        Raises:
            ValueError: If the input timestamp is of an invalid type or format.

        Examples:
            >>> TimestampFormat.convert_ts(1234567890, TimestampFormat.MILLISECONDS)
            1234567890000
            >>> TimestampFormat.convert_ts("1234567890000", TimestampFormat.SECONDS)
            1234567890
        """
        if isinstance(timestamp, str):
            timestamp = float(timestamp)
        elif isinstance(timestamp, int):
            timestamp = float(timestamp)
        elif isinstance(timestamp, float):
            pass
        else:
            raise ValueError(f"Invalid timestamp type: {type(timestamp)}")

        in_format = TimestampFormat.get_format(timestamp)

        if in_format == out_format:
            return timestamp

        if in_format.value < out_format.value:
            return timestamp * (10 ** (out_format.value - in_format.value))
        else:
            return timestamp / (10 ** (in_format.value - out_format.value))
