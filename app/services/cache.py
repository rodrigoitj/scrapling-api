"""
Redis cache helpers.

Cache key is a SHA-256 digest of the normalised (sorted keys) JSON of the
RunRequest body, prefixed with the API version.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

import redis
from flask import current_app

log = logging.getLogger(__name__)

_client: Optional[redis.Redis] = None


def get_client() -> Optional[redis.Redis]:
    global _client
    if _client is not None:
        return _client
    try:
        url: str = current_app.config["REDIS_URL"]
        _client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        _client.ping()
        return _client
    except Exception as exc:
        log.warning("Redis unavailable: %s", exc)
        return None


def make_cache_key(payload: dict[str, Any]) -> str:
    """Return a stable cache key for the given request payload."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"scrapling_api:v1:{digest}"


def get_cached(key: str) -> Optional[Any]:
    client = get_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        log.warning("Cache get failed: %s", exc)
        return None


def set_cached(key: str, value: Any, ttl: int) -> None:
    client = get_client()
    if client is None:
        return
    try:
        client.setex(key, ttl, json.dumps(value, default=str))
    except Exception as exc:
        log.warning("Cache set failed: %s", exc)


def health_check() -> dict[str, Any]:
    client = get_client()
    if client is None:
        return {"status": "unavailable"}
    try:
        client.ping()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
