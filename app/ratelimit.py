"""In-memory sliding-window rate limiting.

Keeps open, account-free posting viable by bounding what a single client can
submit per window. Per-process only — sufficient for the single-instance
deployment this repo currently targets; swap for a shared store (Redis)
before running multiple replicas.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, action: str, limit: int, window_seconds: float) -> bool:
        """Record one attempt and return whether it is within the limit."""
        now = time.monotonic()
        bucket_key = (key, action)
        with self._lock:
            bucket = self._events.setdefault(bucket_key, deque())
            cutoff = now - window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True
