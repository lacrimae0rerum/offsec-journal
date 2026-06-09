"""Minimal in-memory rate limiter for admin mutations.

Keyed by user_id. Sliding window of 60 seconds, default 10 requests. Resets
on process restart — acceptable for a small-team deployment where the goal is
hygiene, not DDoS protection.

Thread-safety: the dict updates are non-atomic but CPython holds the GIL for
single list mutations, which is enough for the precision we need. If you
ever run uvicorn with multiple workers, swap this for a shared store.
"""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, status


class _Limiter:
    def __init__(self, max_per_window: int = 10, window_seconds: int = 60) -> None:
        self._max = max_per_window
        self._window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        """Raise HTTPException 429 if `key` has exceeded the window budget.

        Side effect: records this attempt on success.
        """
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            bucket = self._hits[key]
            # Drop hits older than the window
            bucket[:] = [t for t in bucket if t > cutoff]
            if len(bucket) >= self._max:
                retry_after = int(self._window - (now - bucket[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"rate limit exceeded; retry in ~{retry_after}s",
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(now)


# Module-level singletons. One limiter per scope so admin floods don't drown
# tenant writes and vice versa.
admin_mutations = _Limiter(max_per_window=10, window_seconds=60)
# Journal + notes mutations: 60/min ≈ 1/sec sustained, plenty for a human and
# enough headroom for refreshAll(). Caps abuse that could fill data/<team>/*.yaml
# or notes/<team>/* in tight loops.
tenant_writes = _Limiter(max_per_window=60, window_seconds=60)


def reset_for_tests() -> None:
    """Clear all buckets. Tests call this in their setUp to isolate runs."""
    for limiter in (admin_mutations, tenant_writes):
        with limiter._lock:
            limiter._hits.clear()
