"""Optional API-key auth + in-memory sliding-window rate limiting.

Auth is disabled entirely when API_KEYS is unset (the dev default): every
caller is identified by IP instead of a key, purely for rate-limit bucketing.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from . import config


def _extract_key(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return request.headers.get("x-api-key")


async def require_identity(request: Request) -> str:
    """Resolves the caller's rate-limit identity. Raises 401 if API_KEYS is
    set and the caller didn't supply one of them."""
    if config.API_KEYS:
        key = _extract_key(request)
        if not key or key not in config.API_KEYS:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key — pass it as 'Authorization: Bearer <key>' or 'X-API-Key'.",
            )
        return f"key:{key}"
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


class SlidingWindowLimiter:
    """One (timestamp, weight) deque per identity. Swap this out for a
    Redis-backed implementation to share limits across processes/replicas —
    `check()` is the whole interface callers rely on."""

    def __init__(self, limit: int, window_s: float):
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[tuple[float, int]]] = defaultdict(deque)

    def check(self, identity: str, weight: int = 1) -> float | None:
        """Records the hit and returns None if within limit, else the
        number of seconds the caller should wait before retrying."""
        now = time.time()
        q = self._hits[identity]
        while q and now - q[0][0] > self.window_s:
            q.popleft()
        used = sum(w for _, w in q)
        if used + weight > self.limit:
            retry_after = self.window_s - (now - q[0][0]) if q else self.window_s
            return max(1.0, retry_after)
        q.append((now, weight))
        return None


request_limiter = SlidingWindowLimiter(config.RATE_LIMIT_PER_MIN, 60.0)
char_limiter = SlidingWindowLimiter(config.RATE_LIMIT_CHARS_PER_HOUR, 3600.0)


def _rate_limited(detail: str, retry_after: float) -> HTTPException:
    return HTTPException(status_code=429, detail=detail, headers={"Retry-After": str(int(retry_after))})


def enforce_request_rate(identity: str) -> None:
    retry_after = request_limiter.check(identity, weight=1)
    if retry_after is not None:
        raise _rate_limited(
            f"Rate limit exceeded ({config.RATE_LIMIT_PER_MIN} requests/min). Try again in {retry_after:.0f}s.",
            retry_after,
        )


def enforce_char_rate(identity: str, chars: int) -> None:
    retry_after = char_limiter.check(identity, weight=chars)
    if retry_after is not None:
        raise _rate_limited(
            f"Hourly text-length limit exceeded ({config.RATE_LIMIT_CHARS_PER_HOUR} characters/hour). "
            f"Try again in {retry_after:.0f}s.",
            retry_after,
        )
