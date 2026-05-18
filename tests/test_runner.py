"""Tests for the command runner (Scrapling calls are mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.schemas import ExtractCommand, GetCommand


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_mock_page(html: str = "<html><body><h1>Hello</h1></body></html>") -> MagicMock:
    page = MagicMock()
    page.html = html
    # css().getall() chain
    css_result = MagicMock()
    css_result.getall.return_value = ["Hello"]
    page.css.return_value = css_result
    # xpath().getall() chain
    xpath_result = MagicMock()
    xpath_result.getall.return_value = ["Hello"]
    page.xpath.return_value = xpath_result
    return page


# --------------------------------------------------------------------------- #
# get command
# --------------------------------------------------------------------------- #

def test_runner_get_returns_html(app):
    mock_page = _make_mock_page()
    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            # Inline import to ensure patch applies
            from app.services.runner import execute_commands

            results = execute_commands(
                [GetCommand(type="get", url="https://example.com")]
            )

    assert len(results) == 1
    assert results[0].status == "ok"
    assert results[0].type == "get"
    assert results[0].output == mock_page.html


def test_runner_get_with_css_selector(app):
    mock_page = _make_mock_page()
    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [GetCommand(type="get", url="https://example.com", css_selector="h1")]
            )

    assert results[0].status == "ok"
    assert results[0].output == ["Hello"]


def test_runner_halts_on_error(app):
    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.get.side_effect = RuntimeError("network error")
            from app.services.runner import execute_commands

            results = execute_commands(
                [
                    GetCommand(type="get", url="https://example.com"),
                    ExtractCommand(type="extract", css_selector="h1"),
                ]
            )

    # Only the first command ran, extract was never attempted
    assert len(results) == 1
    assert results[0].status == "error"
    assert "network error" in results[0].error


# --------------------------------------------------------------------------- #
# extract command
# --------------------------------------------------------------------------- #

def test_runner_extract_after_get(app):
    mock_page = _make_mock_page()
    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [
                    GetCommand(type="get", url="https://example.com"),
                    ExtractCommand(type="extract", css_selector="h1"),
                ]
            )

    assert len(results) == 2
    assert results[1].status == "ok"
    assert results[1].output == ["Hello"]


def test_runner_extract_without_fetch_fails(app):
    with app.app_context():
        from app.services.runner import execute_commands

        results = execute_commands(
            [ExtractCommand(type="extract", css_selector="h1")]
        )

    assert results[0].status == "error"
    assert "prior fetch" in results[0].error


# --------------------------------------------------------------------------- #
# Host policy
# --------------------------------------------------------------------------- #

def test_runner_blocked_host_rejected(app):
    app.config["BLOCKED_HOSTS"] = ["blocked.com"]
    with app.app_context():
        from app.services.runner import execute_commands

        results = execute_commands(
            [GetCommand(type="get", url="https://blocked.com/page")]
        )

    assert results[0].status == "error"
    assert "blocked" in results[0].error.lower()


def test_runner_allowed_host_accepted(app):
    mock_page = _make_mock_page()
    app.config["ALLOWED_HOSTS"] = ["example.com"]
    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [GetCommand(type="get", url="https://example.com")]
            )

    assert results[0].status == "ok"


def test_runner_non_allowed_host_rejected(app):
    app.config["ALLOWED_HOSTS"] = ["example.com"]
    with app.app_context():
        from app.services.runner import execute_commands

        results = execute_commands(
            [GetCommand(type="get", url="https://other.com")]
        )

    assert results[0].status == "error"
    assert "allowed" in results[0].error.lower()
