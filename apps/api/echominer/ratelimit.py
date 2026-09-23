"""Small in-process, per-IP sliding-window rate limiter.

The VM deployment rate-limits in nginx. Single-service hosting (Render) has no
nginx in front of the app, so the same limits are enforced here instead. State
is per process, which is exact for the single-process service it is meant for.
"""
from __future__ import annotations

import threading
import time
from collections import deque

# (path prefix, methods, requests allowed, per seconds) -- first match wins.
RULES: list[tuple[str, frozenset[str], int, int]] = [
    ("/api/v1/admin/auth", frozenset({"POST"}), 10, 60),
    ("/api/v1/auth/", frozenset({"POST"}), 10, 60),
    ("/api/v1/registrations", frozenset({"POST"}), 10, 60),
    ("/api/v1/jobs", frozenset({"POST"}), 10, 60),
    ("/api/", frozenset({"GET", "POST", "DELETE"}), 120, 60),
]


class RateLimiter:
    def __init__(self, rules=RULES, clock=time.monotonic):
        self.rules = rules
        self.clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def rule_for(self, path: str, method: str):
        for prefix, methods, limit, window in self.rules:
            if path.startswith(prefix) and method in methods:
                return prefix, limit, window
        return None

    def check(self, ip: str, path: str, method: str) -> int | None:
        """None if allowed, else the number of seconds to wait."""
        rule = self.rule_for(path, method)
        if rule is None:
            return None
        prefix, limit, window = rule
        now = self.clock()
        with self._lock:
            q = self._hits.setdefault((ip, prefix), deque())
            while q and now - q[0] >= window:
                q.popleft()
            if len(q) >= limit:
                return max(1, int(window - (now - q[0])))
            q.append(now)
            if len(self._hits) > 50_000:          # bound memory under abuse
                for key in [k for k, v in self._hits.items() if not v][:10_000]:
                    del self._hits[key]
        return None
