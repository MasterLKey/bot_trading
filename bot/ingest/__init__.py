from __future__ import annotations

import time
from collections import deque
from threading import Lock


class RateLimiter:
    """Simple sliding-window rate limiter (default: 200 calls / 60s for Alpaca Basic)."""

    def __init__(self, max_calls: int = 180, period_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.period = period_seconds
        self._times: deque[float] = deque()
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            while self._times and now - self._times[0] >= self.period:
                self._times.popleft()
            if len(self._times) >= self.max_calls:
                sleep_for = self.period - (now - self._times[0]) + 0.05
                if sleep_for > 0:
                    time.sleep(sleep_for)
                now = time.monotonic()
                while self._times and now - self._times[0] >= self.period:
                    self._times.popleft()
            self._times.append(time.monotonic())
