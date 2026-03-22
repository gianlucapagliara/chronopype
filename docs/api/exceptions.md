# Exceptions

**Module:** `chronopype.exceptions`

## Exception Hierarchy

```
Exception
└── ClockError
    ├── ClockContextError
    ├── ClockRuntimeError
    └── ProcessorError
        └── ProcessorTimeoutError
```

## ClockError

```python
class ClockError(Exception)
```

Base exception for all clock-related errors. Raised when:

- Adding a processor that is already registered
- Removing a processor that is not registered
- Pausing/resuming an unregistered processor
- Running a clock that is already running
- Clock configuration is invalid for the operation

## ClockContextError

```python
class ClockContextError(ClockError)
```

Raised when the clock context manager is misused:

- Entering context when already in context
- Entering context when the clock is running
- Performing operations that require context when not in context

## ClockRuntimeError

```python
class ClockRuntimeError(ClockError)
```

Raised when a `ClockRuntime` operation fails:

- Using `backtest_til()` on a non-backtest clock
- Using `start_threaded()` on a non-realtime clock
- Advancing past `end_time` without context

## ProcessorError

```python
class ProcessorError(ClockError)
```

Raised when a processor encounters an error during execution.

## ProcessorTimeoutError

```python
class ProcessorTimeoutError(ProcessorError)
```

Raised when a processor execution exceeds the configured `processor_timeout`.
