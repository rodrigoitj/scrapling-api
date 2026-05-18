"""Tests for the command runner (Scrapling calls are mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.schemas import (
    ExtractCommand,
    FetchCommand,
    FollowCommand,
    GetCommand,
    PostCommand,
    StealthyFetchCommand,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_mock_page(html: str = "<html><body><h1>Hello</h1></body></html>") -> MagicMock:
    page = MagicMock()
    page.html = html
    page.text = html
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


# --------------------------------------------------------------------------- #
# post command
# --------------------------------------------------------------------------- #

def test_runner_post_returns_text(app):
    mock_page = _make_mock_page()
    mock_page.text = "<html>POST response</html>"
    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.post.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [PostCommand(type="post", url="https://example.com", data="q=test")]
            )

    assert results[0].status == "ok"
    assert results[0].type == "post"
    assert results[0].output == "<html>POST response</html>"


def test_runner_post_with_css_selector(app):
    mock_page = _make_mock_page()
    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.post.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [PostCommand(type="post", url="https://example.com", css_selector="h1")]
            )

    assert results[0].status == "ok"
    assert results[0].output == ["Hello"]


# --------------------------------------------------------------------------- #
# fetch command
# --------------------------------------------------------------------------- #

def test_runner_fetch_returns_text(app):
    mock_page = _make_mock_page()
    mock_page.text = "<html>Dynamic page</html>"
    with app.app_context():
        with patch("app.services.runner.DynamicFetcher") as MockDynamicFetcher:
            MockDynamicFetcher.fetch.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [FetchCommand(type="fetch", url="https://example.com")]
            )

    assert results[0].status == "ok"
    assert results[0].type == "fetch"
    assert results[0].output == "<html>Dynamic page</html>"


def test_runner_fetch_with_css_selector(app):
    mock_page = _make_mock_page()
    with app.app_context():
        with patch("app.services.runner.DynamicFetcher") as MockDynamicFetcher:
            MockDynamicFetcher.fetch.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [FetchCommand(type="fetch", url="https://example.com", css_selector="h1")]
            )

    assert results[0].status == "ok"
    assert results[0].output == ["Hello"]


# --------------------------------------------------------------------------- #
# stealthy_fetch command
# --------------------------------------------------------------------------- #

def test_runner_stealthy_fetch_returns_text(app):
    mock_page = _make_mock_page()
    mock_page.text = "<html>Stealth page</html>"
    with app.app_context():
        with patch("app.services.runner.StealthyFetcher") as MockStealthyFetcher:
            MockStealthyFetcher.fetch.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [StealthyFetchCommand(type="stealthy_fetch", url="https://example.com")]
            )

    assert results[0].status == "ok"
    assert results[0].type == "stealthy_fetch"
    assert results[0].output == "<html>Stealth page</html>"


# --------------------------------------------------------------------------- #
# follow command
# --------------------------------------------------------------------------- #

def test_runner_follow_after_get(app):
    # Page returned by initial GET – also provides the link
    get_page = _make_mock_page()
    get_page.text = "<html><a href='https://example.com/p2'>link</a></html>"
    link_result = MagicMock()
    link_result.getall.return_value = ["https://example.com/p2"]
    get_page.css.return_value = link_result

    # Page returned by DynamicFetcher.fetch after following the link
    followed_page = MagicMock()
    followed_page.html = "<html><h1>Page 2</h1></html>"

    with app.app_context():
        with (
            patch("app.services.runner.Fetcher") as MockFetcher,
            patch("app.services.runner.DynamicFetcher") as MockDynamicFetcher,
        ):
            MockFetcher.get.return_value = get_page
            MockDynamicFetcher.fetch.return_value = followed_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [
                    GetCommand(type="get", url="https://example.com"),
                    FollowCommand(type="follow", css_selector="a"),
                ]
            )

    assert len(results) == 2
    assert results[1].status == "ok"
    assert results[1].output == "<html><h1>Page 2</h1></html>"


def test_runner_follow_without_prior_fetch_fails(app):
    with app.app_context():
        from app.services.runner import execute_commands

        results = execute_commands(
            [FollowCommand(type="follow", css_selector="a")]
        )

    assert results[0].status == "error"
    assert "prior fetch" in results[0].error


def test_runner_follow_no_links_fails(app):
    get_page = _make_mock_page()
    get_page.text = "<html></html>"
    no_links = MagicMock()
    no_links.getall.return_value = []
    get_page.css.return_value = no_links

    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = get_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [
                    GetCommand(type="get", url="https://example.com"),
                    FollowCommand(type="follow", css_selector="a.missing"),
                ]
            )

    assert results[1].status == "error"
    assert "no elements matched" in results[1].error


# --------------------------------------------------------------------------- #
# extract – additional variants
# --------------------------------------------------------------------------- #

def test_runner_extract_with_xpath(app):
    mock_page = _make_mock_page()
    # _make_mock_page already sets page.xpath().getall() → ["Hello"]
    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [
                    GetCommand(type="get", url="https://example.com"),
                    ExtractCommand(type="extract", xpath="//h1/text()"),
                ]
            )

    assert results[1].status == "ok"
    assert results[1].output == ["Hello"]


def test_runner_extract_attribute(app):
    mock_page = _make_mock_page()
    attr_result = MagicMock()
    attr_result.getall.return_value = ["https://example.com/link"]
    mock_page.css.return_value = attr_result

    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [
                    GetCommand(type="get", url="https://example.com"),
                    ExtractCommand(type="extract", css_selector="a", attribute="href"),
                ]
            )

    assert results[1].status == "ok"
    assert results[1].output == ["https://example.com/link"]
    # Verify the ::attr() selector was passed
    mock_page.css.assert_called_with("a::attr(href)")


def test_runner_extract_html_output(app):
    mock_page = _make_mock_page()
    html_result = MagicMock()
    html_result.getall.return_value = ["<h1>Hello</h1>"]
    mock_page.css.return_value = html_result

    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [
                    GetCommand(type="get", url="https://example.com"),
                    ExtractCommand(type="extract", css_selector="h1", html=True),
                ]
            )

    assert results[1].status == "ok"
    assert results[1].output == ["<h1>Hello</h1>"]
    # html=True: selector used without ::text suffix
    mock_page.css.assert_called_with("h1")


def test_runner_extract_first_only(app):
    mock_page = _make_mock_page()
    multi_result = MagicMock()
    multi_result.getall.return_value = ["first", "second", "third"]
    mock_page.css.return_value = multi_result

    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [
                    GetCommand(type="get", url="https://example.com"),
                    ExtractCommand(type="extract", css_selector="p", first_only=True),
                ]
            )

    assert results[1].status == "ok"
    assert results[1].output == ["first"]


def test_runner_extract_limit(app):
    mock_page = _make_mock_page()
    many_result = MagicMock()
    many_result.getall.return_value = ["a", "b", "c", "d", "e"]
    mock_page.css.return_value = many_result

    with app.app_context():
        with patch("app.services.runner.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            from app.services.runner import execute_commands

            results = execute_commands(
                [
                    GetCommand(type="get", url="https://example.com"),
                    ExtractCommand(type="extract", css_selector="li", limit=3),
                ]
            )

    assert results[1].status == "ok"
    assert results[1].output == ["a", "b", "c"]


# --------------------------------------------------------------------------- #
# Host policy – subdomain blocking
# --------------------------------------------------------------------------- #

def test_runner_blocked_subdomain_rejected(app):
    app.config["BLOCKED_HOSTS"] = ["blocked.com"]
    with app.app_context():
        from app.services.runner import execute_commands

        results = execute_commands(
            [GetCommand(type="get", url="https://sub.blocked.com/page")]
        )

    assert results[0].status == "error"
    assert "blocked" in results[0].error.lower()


# --------------------------------------------------------------------------- #
# _truncate helper
# --------------------------------------------------------------------------- #

def test_truncate_short_string_unchanged():
    from app.services.runner import _truncate

    assert _truncate("hello", 100) == "hello"


def test_truncate_long_string_truncated():
    from app.services.runner import _truncate

    result = _truncate("x" * 200, 100)
    assert result.startswith("x" * 100)
    assert "truncated" in result
    assert "200 chars" in result


def test_truncate_list_items_trimmed_by_budget():
    from app.services.runner import _truncate

    # Single long string item exceeds budget; should be cut at max_len chars
    result = _truncate(["a" * 200, "b"], 100)
    assert result[0] == "a" * 100
    assert result[1] == "[more items truncated]"


def test_truncate_list_excess_items_replaced():
    from app.services.runner import _truncate

    items = ["hi"] * 50
    result = _truncate(items, 10)
    assert "[more items truncated]" in result


def test_truncate_non_string_non_list_passthrough():
    from app.services.runner import _truncate

    obj = {"key": "value"}
    assert _truncate(obj, 100) is obj
