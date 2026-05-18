"""Tests for cache key generation and helpers."""

from __future__ import annotations

from app.services.cache import make_cache_key


def test_cache_key_stable():
    payload = {"commands": [{"type": "get", "url": "https://example.com"}], "cache": True}
    assert make_cache_key(payload) == make_cache_key(payload)


def test_cache_key_order_independent():
    a = {"cache": True, "commands": [{"url": "https://example.com", "type": "get"}]}
    b = {"commands": [{"type": "get", "url": "https://example.com"}], "cache": True}
    assert make_cache_key(a) == make_cache_key(b)


def test_cache_key_differs_for_different_payloads():
    p1 = {"commands": [{"type": "get", "url": "https://example.com"}]}
    p2 = {"commands": [{"type": "get", "url": "https://other.com"}]}
    assert make_cache_key(p1) != make_cache_key(p2)


def test_cache_key_has_prefix():
    key = make_cache_key({"commands": []})
    assert key.startswith("scrapling_api:v1:")
