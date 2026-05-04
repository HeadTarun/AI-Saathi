from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any, TypeVar


TRANSIENT_ERROR_HINTS = (
    "timeout",
    "temporarily unavailable",
    "connection reset",
    "connection aborted",
    "network",
    "rate limit",
    "too many requests",
    "503",
    "502",
    "504",
)

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"reveal\s+(the\s+)?(system|developer|hidden)\s+(prompt|instructions|reasoning)", re.I),
    re.compile(r"disregard\s+(the\s+)?(system|developer)\s+message", re.I),
]

T = TypeVar("T")


class WorkflowTimeoutError(TimeoutError):
    pass


class RateLimitExceeded(RuntimeError):
    pass


class InMemoryRateLimiter:
    """Isolated hook point; replace with Redis or API gateway limits in production."""

    def __init__(self, *, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.time()
        queue = self._requests[key]
        while queue and now - queue[0] > self.window_seconds:
            queue.popleft()
        if len(queue) >= self.max_requests:
            raise RateLimitExceeded("Rate limit exceeded for study agent workflow")
        queue.append(now)


_RATE_LIMITER = InMemoryRateLimiter()


def check_rate_limit(user_id: str) -> None:
    _RATE_LIMITER.check(user_id)


def is_transient_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(hint in message for hint in TRANSIENT_ERROR_HINTS)


def with_timeout(fn: Callable[[], T], *, timeout_seconds: float, label: str) -> T:
    start = time.perf_counter()
    result = fn()
    if time.perf_counter() - start > timeout_seconds:
        raise WorkflowTimeoutError(f"{label} exceeded timeout of {timeout_seconds:.1f}s")
    return result


def retry_transient(
    fn: Callable[[], T],
    *,
    attempts: int = 2,
    sleep_seconds: float = 0.05,
) -> T:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            if attempt >= attempts - 1 or not is_transient_error(exc):
                raise
            time.sleep(sleep_seconds)
    raise last_error or RuntimeError("Retry failed without an exception")


def sanitize_source_text(text: str) -> str:
    sanitized = text
    for pattern in INJECTION_PATTERNS:
        sanitized = pattern.sub("[REMOVED_PROMPT_INJECTION]", sanitized)
    return sanitized


def sanitize_tool_payload(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_source_text(value)
    if isinstance(value, dict):
        return {key: sanitize_tool_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_tool_payload(item) for item in value]
    return value


__all__ = [
    "RateLimitExceeded",
    "WorkflowTimeoutError",
    "check_rate_limit",
    "retry_transient",
    "sanitize_source_text",
    "sanitize_tool_payload",
    "with_timeout",
]
