"""ClockRuntime: manages clock lifecycle (init, async start/stop, threaded mode)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from typing import Any

from chronopype.clocks import get_clock_class
from chronopype.clocks.backtest import BacktestClock
from chronopype.clocks.base import BaseClock
from chronopype.clocks.config import ClockConfig
from chronopype.clocks.modes import ClockMode
from chronopype.clocks.realtime import RealtimeClock
from chronopype.exceptions import ClockRuntimeError
from chronopype.runtime.config import ClockRuntimeConfig

logger = logging.getLogger(__name__)


def start_clock_thread(
    runtime: ClockRuntime,
    clock: BaseClock,
    on_error_callback: Any = None,
    stop_event: threading.Event | None = None,
    poll_interval: float = 0.1,
) -> threading.Thread:
    """Start a clock in a dedicated daemon thread with its own event loop.

    The thread's event loop is stored on *runtime* (via ``_clock_loop_ref``)
    so callers can schedule coroutines from other threads.
    """

    def _run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runtime._clock_loop_ref = loop
        try:
            loop.run_until_complete(_clock_loop(clock, stop_event, poll_interval))
        except Exception as exc:
            logger.exception("Clock thread error")
            if on_error_callback is not None:
                try:
                    on_error_callback(str(exc))
                except Exception:
                    pass
        finally:
            loop.close()
            runtime._clock_loop_ref = None

    thread = threading.Thread(target=_run, name="clock-worker", daemon=True)
    thread.start()
    return thread


async def _clock_loop(
    clock: BaseClock,
    stop_event: threading.Event | None = None,
    poll_interval: float = 0.1,
) -> None:
    """Run *clock* inside its async context, polling *stop_event* for shutdown."""
    logger.info("Clock loop starting (%s)...", type(clock).__name__)

    run_task: asyncio.Task[None] | None = None
    try:
        async with clock:
            run_task = asyncio.create_task(clock.run())
            if stop_event is None:
                await run_task
                return

            while True:
                if run_task.done():
                    await run_task
                    return
                if stop_event.is_set():
                    run_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await run_task
                    return
                await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        logger.info("Clock loop cancelled.")
    except Exception:
        logger.exception("Clock loop error.")
        raise
    finally:
        logger.info("Clock loop stopped.")


class ClockRuntime:
    """Manages clock lifecycle: initialization, async start/stop, threaded mode.

    Can be used as an async context manager::

        async with ClockRuntime(config=my_config) as rt:
            # clock is running
            ...
        # clock is stopped

    Or with a pre-built clock::

        clock = BacktestClock(clock_config)
        async with ClockRuntime(clock=clock) as rt:
            await rt.backtest_til(target_time)
    """

    def __init__(
        self,
        config: ClockRuntimeConfig | None = None,
        clock: BaseClock | None = None,
    ) -> None:
        self._config = config or ClockRuntimeConfig()
        self._clock: BaseClock = clock if clock is not None else self._build_clock()
        self._clock_task: asyncio.Task[None] | None = None
        self._clock_thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._clock_loop_ref: asyncio.AbstractEventLoop | None = None
        self._backtest_context_active: bool = False

    # -- Construction helpers --------------------------------------------------

    def _build_clock(self) -> BaseClock:
        """Build a clock from the runtime config."""
        clock_cls = get_clock_class(self._config.clock_mode)
        clock_config = ClockConfig(
            clock_mode=self._config.clock_mode,
            tick_size=self._config.tick_size,
            start_time=self._config.start_time,
            end_time=self._config.end_time,
        )
        return clock_cls(clock_config)

    # -- Properties ------------------------------------------------------------

    @property
    def config(self) -> ClockRuntimeConfig:
        """Return the runtime configuration."""
        return self._config

    @property
    def clock(self) -> BaseClock:
        """Return the underlying clock instance."""
        return self._clock

    def get_clock_loop(self) -> asyncio.AbstractEventLoop | None:
        """Return the clock thread's event loop when in threaded mode, else None."""
        return self._clock_loop_ref

    @property
    def is_running(self) -> bool:
        """True if the clock is running (async task, thread, or backtest context)."""
        if self._backtest_context_active:
            return True
        if self._clock_task is not None and not self._clock_task.done():
            return True
        if self._clock_thread is not None and self._clock_thread.is_alive():
            return True
        return False

    # -- Async mode ------------------------------------------------------------

    async def start(self) -> None:
        """Start clock as async task, or enter backtest context.

        In backtest mode the clock context is entered so processors are
        initialized, but no background task is created — the clock is
        driven manually via :meth:`backtest_til`.
        """
        if self._clock_task is not None:
            return
        if self._config.clock_mode == ClockMode.BACKTEST:
            if not self._backtest_context_active:
                await self._clock.__aenter__()
                self._backtest_context_active = True
            return
        # Realtime: enter context then create run task
        if not self._backtest_context_active:
            await self._clock.__aenter__()
            self._backtest_context_active = True
        self._clock_task = asyncio.create_task(self._clock.run())

    async def stop(self) -> None:
        """Stop clock async task or exit backtest context."""
        if self._clock_task is not None:
            self._clock_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._clock_task
            self._clock_task = None
        if self._backtest_context_active:
            await self._clock.__aexit__(None, None, None)
            self._backtest_context_active = False

    async def backtest_til(self, target_time: float) -> None:
        """Advance the backtest clock to *target_time*.

        Delegates to :meth:`BacktestClock.step_to` when processors are
        registered, otherwise just updates the clock timestamp.

        Raises :class:`ClockRuntimeError` if the clock is not a
        :class:`BacktestClock`.
        """
        if not isinstance(self._clock, BacktestClock):
            raise ClockRuntimeError(
                f"backtest_til requires a BacktestClock, got {type(self._clock).__name__}"
            )
        if self._clock._current_context:  # noqa: SLF001
            await self._clock.step_to(target_time)
        else:
            self._clock._current_tick = target_time  # noqa: SLF001

    # -- Threaded mode ---------------------------------------------------------

    def start_threaded(self, on_error_callback: Any = None) -> None:
        """Start clock in a dedicated thread.

        Only supported for :class:`RealtimeClock`.  Raises
        :class:`ClockRuntimeError` for other clock types.
        """
        if self._clock_thread is not None and self._clock_thread.is_alive():
            return
        if not isinstance(self._clock, RealtimeClock):
            raise ClockRuntimeError(
                f"Threaded runtime requires RealtimeClock, got {type(self._clock).__name__}."
            )
        self._stop_event = threading.Event()
        self._clock_thread = start_clock_thread(
            runtime=self,
            clock=self._clock,
            on_error_callback=on_error_callback,
            stop_event=self._stop_event,
            poll_interval=self._config.clock_poll_interval_seconds,
        )

    def stop_threaded(self) -> None:
        """Stop clock thread."""
        if self._stop_event is not None:
            self._stop_event.set()
        if self._clock_thread is not None:
            self._clock_thread.join(timeout=self._config.thread_stop_timeout_seconds)
            self._clock_thread = None
        self._stop_event = None
        self._clock_loop_ref = None

    # -- Async context manager -------------------------------------------------

    async def __aenter__(self) -> ClockRuntime:
        """Start clock and return self."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Stop clock on exit."""
        await self.stop()
