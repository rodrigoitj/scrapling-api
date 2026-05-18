"""Tests for cache key generation and helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

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


# --------------------------------------------------------------------------- #
# get_cached
# --------------------------------------------------------------------------- #

def test_get_cached_returns_none_when_no_client():
    with patch("app.services.cache.get_client", return_value=None):
        from app.services.cache import get_cached

        result = get_cached("some-key")
    assert result is None


def test_get_cached_returns_none_for_missing_key():
    mock_client = MagicMock()
    mock_client.get.return_value = None

    with patch("app.services.cache.get_client", return_value=mock_client):
        from app.services.cache import get_cached

        result = get_cached("missing-key")
    assert result is None


def test_get_cached_returns_parsed_value():
    payload = {"status": "ok", "final_output": "hello"}
    mock_client = MagicMock()
    mock_client.get.return_value = json.dumps(payload)

    with patch("app.services.cache.get_client", return_value=mock_client):
        from app.services.cache import get_cached

        result = get_cached("some-key")

    assert result == payload


def test_get_cached_swallows_redis_exception():
    mock_client = MagicMock()
    mock_client.get.side_effect = Exception("connection lost")

    with patch("app.services.cache.get_client", return_value=mock_client):
        from app.services.cache import get_cached

        result = get_cached("some-key")
    assert result is None


# --------------------------------------------------------------------------- #
# set_cached
# --------------------------------------------------------------------------- #

def test_set_cached_no_op_without_client():
    with patch("app.services.cache.get_client", return_value=None):
        from app.services.cache import set_cached

        # Must not raise
        set_cached("key", {"data": 1}, 60)


def test_set_cached_calls_setex_with_correct_args():
    mock_client = MagicMock()

    with patch("app.services.cache.get_client", return_value=mock_client):
        from app.services.cache import set_cached

        set_cached("my-key", {"result": "ok"}, 300)

    args = mock_client.setex.call_args[0]
    assert args[0] == "my-key"
    assert args[1] == 300
    stored = json.loads(args[2])
    assert stored == {"result": "ok"}


def test_set_cached_swallows_redis_exception():
    mock_client = MagicMock()
    mock_client.setex.side_effect = Exception("write failed")

    with patch("app.services.cache.get_client", return_value=mock_client):
        from app.services.cache import set_cached

        # Must not raise
        set_cached("key", {"data": 1}, 60)


# --------------------------------------------------------------------------- #
# health_check
# --------------------------------------------------------------------------- #

def test_cache_health_check_unavailable():
    with patch("app.services.cache.get_client", return_value=None):
        from app.services.cache import health_check

        result = health_check()
    assert result["status"] == "unavailable"


def test_cache_health_check_ok():
    mock_client = MagicMock()

    with patch("app.services.cache.get_client", return_value=mock_client):
        from app.services.cache import health_check

        result = health_check()
    assert result["status"] == "ok"
    mock_client.ping.assert_called_once()


def test_cache_health_check_error_on_ping_failure():
    mock_client = MagicMock()
    mock_client.ping.side_effect = Exception("connection refused")

    with patch("app.services.cache.get_client", return_value=mock_client):
        from app.services.cache import health_check

        result = health_check()
    assert result["status"] == "error"
    assert "connection refused" in result["detail"]
