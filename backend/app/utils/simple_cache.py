"""Lightweight in-process cache helpers with TTL support.

The production system is expected to use Redis, but for developer and
unit-test scenarios we provide an in-memory fallback that offers
explicit set/get/invalidate primitives.  The helpers are intentionally
async-agnostic so they can be safely reused from sync or async code.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional, Tuple

_CacheValue = Tuple[Optional[float], Any]
_CACHE: Dict[str, _CacheValue] = {}
_LOCK = threading.RLock()


def cache_get(key: str) -> Any:
    """Return a cached value if it exists and has not expired."""
    with _LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at is not None and expires_at < time.monotonic():
            _CACHE.pop(key, None)
            return None
        return value


def cache_set(key: str, value: Any, ttl: int) -> None:
    """Store ``value`` under ``key`` with an optional TTL (seconds)."""
    expires_at = time.monotonic() + ttl if ttl > 0 else None
    with _LOCK:
        _CACHE[key] = (expires_at, value)


def cache_invalidate(prefix: str) -> None:
    """Invalidate every cache entry that starts with ``prefix``."""
    with _LOCK:
        for key in list(_CACHE.keys()):
            if key.startswith(prefix):
                _CACHE.pop(key, None)


def cache_clear() -> None:
    """Remove all cached entries (primarily for tests)."""
    with _LOCK:
        _CACHE.clear()


__all__ = ["cache_get", "cache_set", "cache_invalidate", "cache_clear"]
