"""Thread-safe fixed-interval rate limiter."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class RateLimiter:
    """Enforce a minimum interval between request starts."""

    def __init__(
        self,
        requests_per_second: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._interval = 1.0 / requests_per_second
        self._clock = clock
        self._sleeper = sleeper
        self._last_request: float | None = None
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Block only as long as required by the configured interval."""

        with self._lock:
            now = self._clock()
            if self._last_request is not None:
                delay = self._interval - (now - self._last_request)
                if delay > 0:
                    self._sleeper(delay)
                    now = self._clock()
            self._last_request = now
