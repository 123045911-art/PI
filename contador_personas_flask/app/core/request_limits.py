from __future__ import annotations

from collections import defaultdict, deque
from threading import RLock
from time import monotonic


class SlidingWindowRateLimiter:
    """Small local safeguard for the demo server; production can replace it externally."""

    def __init__(self, per_client: int, global_limit: int, window_seconds: float) -> None:
        self.per_client = max(1, per_client)
        self.global_limit = max(self.per_client, global_limit)
        self.window_seconds = max(1.0, window_seconds)
        self._lock = RLock()
        self._clients: dict[str, deque[float]] = defaultdict(deque)
        self._global: deque[float] = deque()

    def allow(self, client_key: str) -> tuple[bool, int, int]:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            while self._global and self._global[0] <= cutoff:
                self._global.popleft()
            client = self._clients[client_key]
            while client and client[0] <= cutoff:
                client.popleft()

            remaining = max(0, self.per_client - len(client))
            if len(client) >= self.per_client or len(self._global) >= self.global_limit:
                return False, remaining, max(1, round(self.window_seconds))

            client.append(now)
            self._global.append(now)
            return True, max(0, self.per_client - len(client)), max(1, round(self.window_seconds))


class StreamLimiter:
    """Limits viewers while keeping the single camera capture shared."""

    def __init__(self, global_limit: int, per_client: int = 1) -> None:
        self.global_limit = max(1, global_limit)
        self.per_client = max(1, per_client)
        self._lock = RLock()
        self._active_total = 0
        self._active_by_client: dict[str, int] = defaultdict(int)

    def acquire(self, client_key: str) -> bool:
        with self._lock:
            if self._active_total >= self.global_limit:
                return False
            if self._active_by_client[client_key] >= self.per_client:
                return False
            self._active_total += 1
            self._active_by_client[client_key] += 1
            return True

    def release(self, client_key: str) -> None:
        with self._lock:
            if self._active_by_client.get(client_key, 0) <= 0:
                return
            self._active_total = max(0, self._active_total - 1)
            self._active_by_client[client_key] -= 1
            if self._active_by_client[client_key] <= 0:
                self._active_by_client.pop(client_key, None)

    @property
    def active_total(self) -> int:
        with self._lock:
            return self._active_total
