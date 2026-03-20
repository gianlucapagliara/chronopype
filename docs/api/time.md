# Time & TimestampFormat

**Module:** `chronopype.time`

## Time

A class containing time duration constants in seconds.

| Constant | Value | Description |
|----------|-------|-------------|
| `Time.SECOND` | `1` | One second |
| `Time.MILLISECOND` | `0.001` | One millisecond |
| `Time.MINUTE` | `60` | One minute |
| `Time.HOUR` | `3600` | One hour |
| `Time.TWELVE_HOURS` | `43200` | Twelve hours |
| `Time.DAY` | `86400` | One day |
| `Time.WEEK` | `604800` | One week |
| `Time.MONTH` | `2592000` | 30 days |
| `Time.YEAR` | `31536000` | 365 days |

## TimestampFormat

An enum identifying timestamp precision by digit count.

| Value | Digits | Example |
|-------|--------|---------|
| `SECONDS` | 10 | `1700000000` |
| `MILLISECONDS` | 13 | `1700000000000` |
| `MICROSECONDS` | 16 | `1700000000000000` |
| `NANOSECONDS` | 19 | `1700000000000000000` |

### `TimestampFormat.get_format(ts)`

Detect the format of a timestamp.

```python
TimestampFormat.get_format(1700000000)      # SECONDS
TimestampFormat.get_format(1700000000000)    # MILLISECONDS
```

**Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `ts` | `float \| int \| str` | Timestamp to analyze |

**Returns:** `TimestampFormat`

**Raises:** `ValueError` if the format cannot be determined.

### `TimestampFormat.convert_ts(timestamp, out_format)`

Convert a timestamp between formats. Preserves the input type.

```python
TimestampFormat.convert_ts(1700000000, TimestampFormat.MILLISECONDS)
# Returns: 1700000000000 (int)

TimestampFormat.convert_ts("1700000000", TimestampFormat.MILLISECONDS)
# Returns: "1700000000000" (str)
```

**Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `timestamp` | `str \| int \| float` | Input timestamp |
| `out_format` | `TimestampFormat` | Desired output format |

**Returns:** `str | int | float` (same type as input)

**Raises:** `ValueError` if the input type or format is invalid.
