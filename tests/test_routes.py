"""Flask route integration tests (Redis and MongoDB are mocked)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# --------------------------------------------------------------------------- #
# /health
# --------------------------------------------------------------------------- #

def test_health_returns_ok(client):
    with (
        patch("app.routes.cache_svc.health_check", return_value={"status": "ok"}),
        patch("app.routes.store_svc.health_check", return_value={"status": "ok"}),
    ):
        resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["dependencies"]["redis"]["status"] == "ok"
    assert data["dependencies"]["mongodb"]["status"] == "ok"


# --------------------------------------------------------------------------- #
# POST /api/v1/runs – invalid body
# --------------------------------------------------------------------------- #

def test_run_no_body_returns_400(client):
    resp = client.post("/api/v1/runs", content_type="application/json", data="not-json")
    assert resp.status_code == 400


def test_run_empty_commands_returns_422(client):
    resp = client.post(
        "/api/v1/runs",
        json={"commands": []},
    )
    assert resp.status_code == 422


def test_run_invalid_command_type_returns_422(client):
    resp = client.post(
        "/api/v1/runs",
        json={"commands": [{"type": "shell_exec", "cmd": "ls"}]},
    )
    assert resp.status_code == 422


def test_run_too_many_commands_returns_422(client, app):
    app.config["MAX_COMMANDS"] = 2
    resp = client.post(
        "/api/v1/runs",
        json={
            "commands": [
                {"type": "get", "url": "https://example.com"},
                {"type": "get", "url": "https://example.com"},
                {"type": "get", "url": "https://example.com"},
            ]
        },
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# POST /api/v1/runs – successful execution
# --------------------------------------------------------------------------- #

def _mock_page(html="<html><body><h1>OK</h1></body></html>"):
    page = MagicMock()
    page.html = html
    css_mock = MagicMock()
    css_mock.getall.return_value = ["OK"]
    page.css.return_value = css_mock
    return page


def test_run_get_command_ok(client):
    mock_page = _mock_page()
    with patch("app.services.runner.Fetcher") as MockFetcher:
        MockFetcher.get.return_value = mock_page
        resp = client.post(
            "/api/v1/runs",
            json={"commands": [{"type": "get", "url": "https://example.com"}], "cache": False, "persist": False},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["commands_executed"] == 1
    assert data["cache_hit"] is False
    assert data["results"][0]["status"] == "ok"


def test_run_returns_cache_hit(client, app):
    app.config["CACHE_ENABLED"] = True
    cached_data = {
        "run_id": "abc123",
        "status": "ok",
        "cache_hit": False,
        "commands_executed": 1,
        "duration_ms": 50.0,
        "results": [],
        "final_output": "cached",
    }
    with (
        patch("app.routes.cache_svc.get_cached", return_value=cached_data),
        patch("app.routes.cache_svc.make_cache_key", return_value="key"),
    ):
        resp = client.post(
            "/api/v1/runs",
            json={"commands": [{"type": "get", "url": "https://example.com"}], "cache": True},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["cache_hit"] is True
    assert data["final_output"] == "cached"


# --------------------------------------------------------------------------- #
# GET /api/v1/runs/<run_id>
# --------------------------------------------------------------------------- #

def test_get_run_not_found(client, app):
    app.config["PERSIST_ENABLED"] = True
    with patch("app.routes.store_svc.get_run", return_value=None):
        resp = client.get("/api/v1/runs/000000000000000000000000")
    assert resp.status_code == 404


def test_get_run_found(client, app):
    app.config["PERSIST_ENABLED"] = True
    run_doc = {
        "run_id": "abc123",
        "status": "ok",
        "cache_hit": False,
        "commands_executed": 1,
        "duration_ms": 100.0,
        "results": [],
        "final_output": "test",
        "created_at": "2026-05-17T00:00:00+00:00",
    }
    with patch("app.routes.store_svc.get_run", return_value=run_doc):
        resp = client.get("/api/v1/runs/abc123")
    assert resp.status_code == 200
    assert resp.get_json()["run_id"] == "abc123"


def test_get_run_persist_disabled(client, app):
    app.config["PERSIST_ENABLED"] = False
    resp = client.get("/api/v1/runs/abc123")
    assert resp.status_code == 503
