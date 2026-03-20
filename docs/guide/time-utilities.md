# Time Utilities

Chronopype provides time constants and timestamp format conversion utilities.

## Time Constants

The `Time` class provides commonly used time durations in seconds:

```python
from chronopype import Time

Time.SECOND        # 1
Time.MILLISECOND   # 0.001
Time.MINUTE        # 60
Time.HOUR          # 3600
Time.TWELVE_HOURS  # 43200
Time.DAY           # 86400
Time.WEEK          # 604800
Time.MONTH         # 2592000  (30 days)
Time.YEAR          # 31536000 (365 days)
```

Use these for readable clock configuration:

```python
from chronopype import ClockConfig, ClockMode, Time

config = ClockConfig(
    clock_mode=ClockMode.BACKTEST,
    start_time=1700000000.0,
    end_time=1700000000.0 + 7 * Time.DAY,  # 1 week
    tick_size=5 * Time.MINUTE,               # 5-minute ticks
)
```

## Timestamp Formats

The `TimestampFormat` enum identifies timestamp precision by digit count:

```python
from chronopype import TimestampFormat

TimestampFormat.SECONDS       # 10 digits
TimestampFormat.MILLISECONDS  # 13 digits
TimestampFormat.MICROSECONDS  # 16 digits
TimestampFormat.NANOSECONDS   # 19 digits
```

## Detecting Timestamp Format

Automatically detect the format of a timestamp:

```python
from chronopype import TimestampFormat

fmt = TimestampFormat.get_format(1700000000)       # SECONDS
fmt = TimestampFormat.get_format(1700000000000)     # MILLISECONDS
fmt = TimestampFormat.get_format(1700000000000000)  # MICROSECONDS
```

Works with `int`, `float`, and `str` inputs.

## Converting Timestamps

Convert between timestamp formats:

```python
from chronopype import TimestampFormat

# Seconds to milliseconds
ms = TimestampFormat.convert_ts(1700000000, TimestampFormat.MILLISECONDS)
# Result: 1700000000000

# Milliseconds to seconds
sec = TimestampFormat.convert_ts(1700000000000, TimestampFormat.SECONDS)
# Result: 1700000000

# Preserves input type (str in = str out)
result = TimestampFormat.convert_ts("1700000000", TimestampFormat.MILLISECONDS)
# Result: "1700000000000"
```

The conversion preserves the input type: if you pass a `str`, you get a `str` back; same for `int` and `float`.
