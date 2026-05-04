from __future__ import annotations

import hashlib
import logging
import re
import time
from collections.abc import Callable
from typing import Any, TypeVar


logger = logging.getLogger("ai_study_companion.agent")

SECRET_PATTERNS = [
    re.compile(r"(GROQ_API_KEY|SUPABASE_SERVICE_ROLE_KEY|SUPABASE_ANON_KEY|api[_-]?key)\s*[:=]\s*[^,\s}]+", re.I),
    re.compile(r"\b(gsk_[A-Za-z0-9_-]{12,}|sb_[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_-]{20,})\b"),
]
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b")

T = TypeVar("T")


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def redact_text(value: str, *, max_len: int = 500) -> str:
    text = value
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    text = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    text = PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    return text[:max_len]


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("key", "secret", "token", "password", "authorization")):
                redacted[key] = "[REDACTED_SECRET]"
            elif lowered in {"email", "phone", "name"}:
                redacted[key] = "[REDACTED_PII]"
            else:
                redacted[key] = redact_value(item)
        return redacted
    if isinstance(value, list):
        return [redact_value(item) for item in value[:20]]
    return value


def safe_log(
    event: str,
    *,
    request_id: str | None = None,
    user_id: str | None = None,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    payload = {
        "event": event,
        "request_id": request_id,
        "user_hash": stable_hash(user_id) if user_id else None,
        **redact_value(fields),
    }
    logger.log(level, "%s", payload)


def timed_call(
    event: str,
    fn: Callable[[], T],
    *,
    request_id: str,
    user_id: str,
    **fields: Any,
) -> T:
    start = time.perf_counter()
    safe_log(f"{event}_started", request_id=request_id, user_id=user_id, **fields)
    try:
        result = fn()
    except Exception as exc:
        safe_log(
            f"{event}_error",
            request_id=request_id,
            user_id=user_id,
            level=logging.ERROR,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            error_type=exc.__class__.__name__,
            error_message=str(exc),
            **fields,
        )
        raise
    safe_log(
        f"{event}_finished",
        request_id=request_id,
        user_id=user_id,
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
        **fields,
    )
    return result


__all__ = ["redact_text", "redact_value", "safe_log", "stable_hash", "timed_call"]
