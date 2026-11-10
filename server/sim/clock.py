"""Injectable time for the Sim, so tests can control timers without sleeping."""

import asyncio
import itertools
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def now(self) -> datetime: ...


class TimerHandle(Protocol):
    def cancel(self) -> None: ...


class Scheduler(Protocol):
    def call_later(
        self, delay: float, callback: Callable[[], None]
    ) -> TimerHandle: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def now(self) -> datetime:
        return datetime.now(UTC)


class AsyncioScheduler:
    """Schedules on the running event loop (the FastAPI server's loop)."""

    def call_later(self, delay: float, callback: Callable[[], None]) -> TimerHandle:
        return asyncio.get_running_loop().call_later(delay, callback)


@dataclass
class _ManualTimer:
    due: float
    order: int
    callback: Callable[[], None] = field(compare=False)
    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True


class ManualTime:
    """A Clock and Scheduler that moves only when ``advance`` is called."""

    def __init__(self, start: datetime = datetime(2026, 1, 1, tzinfo=UTC)) -> None:
        self._start = start
        self._elapsed = 0.0
        self._timers: list[_ManualTimer] = []
        self._order = itertools.count()

    def monotonic(self) -> float:
        return self._elapsed

    def now(self) -> datetime:
        return self._start + timedelta(seconds=self._elapsed)

    def call_later(self, delay: float, callback: Callable[[], None]) -> TimerHandle:
        due = self._elapsed + max(0.0, delay)
        timer = _ManualTimer(due, next(self._order), callback)
        self._timers.append(timer)
        return timer

    @property
    def pending_timers(self) -> int:
        return sum(not timer.cancelled for timer in self._timers)

    def advance(self, seconds: float) -> None:
        """Run due callbacks in order, including ones they schedule."""
        target = self._elapsed + seconds
        while True:
            self._timers = [t for t in self._timers if not t.cancelled]
            due = [t for t in self._timers if t.due <= target]
            if not due:
                break
            timer = min(due, key=lambda t: (t.due, t.order))
            self._timers.remove(timer)
            self._elapsed = timer.due
            timer.callback()
        self._elapsed = target
