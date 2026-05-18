"""Tests for request/command schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    ExtractCommand,
    FetchCommand,
    FollowCommand,
    GetCommand,
    PostCommand,
    RunRequest,
    StealthyFetchCommand,
)


# --------------------------------------------------------------------------- #
# GetCommand
# --------------------------------------------------------------------------- #

def test_get_command_valid():
    cmd = GetCommand(type="get", url="https://example.com")
    assert cmd.url == "https://example.com"


def test_get_command_rejects_non_http_scheme():
    with pytest.raises(ValidationError, match="http or https"):
        GetCommand(type="get", url="ftp://example.com/file")


def test_get_command_rejects_missing_host():
    with pytest.raises(ValidationError):
        GetCommand(type="get", url="https://")


def test_get_command_proxy_valid():
    cmd = GetCommand(type="get", url="https://example.com", proxy="http://proxy:8080")
    assert cmd.proxy == "http://proxy:8080"


def test_get_command_proxy_invalid_scheme():
    with pytest.raises(ValidationError, match="Proxy URL"):
        GetCommand(type="get", url="https://example.com", proxy="ftp://proxy:8080")


# --------------------------------------------------------------------------- #
# ExtractCommand
# --------------------------------------------------------------------------- #

def test_extract_requires_selector():
    with pytest.raises(ValidationError, match="css_selector or xpath"):
        ExtractCommand(type="extract")


def test_extract_css_valid():
    cmd = ExtractCommand(type="extract", css_selector=".title")
    assert cmd.css_selector == ".title"


def test_extract_xpath_valid():
    cmd = ExtractCommand(type="extract", xpath="//h1/text()")
    assert cmd.xpath == "//h1/text()"


def test_extract_limit_in_range():
    cmd = ExtractCommand(type="extract", css_selector="p", limit=10)
    assert cmd.limit == 10


def test_extract_limit_too_large():
    with pytest.raises(ValidationError):
        ExtractCommand(type="extract", css_selector="p", limit=9999)


# --------------------------------------------------------------------------- #
# RunRequest
# --------------------------------------------------------------------------- #

def test_run_request_discriminated_union():
    req = RunRequest.model_validate(
        {
            "commands": [
                {"type": "get", "url": "https://example.com"},
                {"type": "extract", "css_selector": "h1"},
            ]
        }
    )
    assert len(req.commands) == 2
    assert req.commands[0].type == "get"  # type: ignore[union-attr]
    assert req.commands[1].type == "extract"  # type: ignore[union-attr]


def test_run_request_empty_commands_rejected():
    with pytest.raises(ValidationError):
        RunRequest.model_validate({"commands": []})


def test_run_request_unknown_type_rejected():
    with pytest.raises(ValidationError):
        RunRequest.model_validate({"commands": [{"type": "shell_exec", "cmd": "ls"}]})


def test_run_request_cache_defaults_true():
    req = RunRequest.model_validate(
        {"commands": [{"type": "get", "url": "https://example.com"}]}
    )
    assert req.cache is True
    assert req.persist is True


# --------------------------------------------------------------------------- #
# PostCommand
# --------------------------------------------------------------------------- #

def test_post_command_valid():
    cmd = PostCommand(type="post", url="https://example.com", data="key=value")
    assert cmd.url == "https://example.com"
    assert cmd.data == "key=value"


def test_post_command_rejects_non_http_scheme():
    with pytest.raises(ValidationError, match="http or https"):
        PostCommand(type="post", url="ftp://example.com/file")


def test_post_command_proxy_socks5_valid():
    cmd = PostCommand(
        type="post",
        url="https://example.com",
        proxy="socks5://proxy.example.com:1080",
    )
    assert cmd.proxy is not None
    assert cmd.proxy.startswith("socks5://")


def test_post_command_json_body_valid():
    cmd = PostCommand(type="post", url="https://example.com", json_body={"key": "val"})
    assert cmd.json_body == {"key": "val"}


# --------------------------------------------------------------------------- #
# FetchCommand
# --------------------------------------------------------------------------- #

def test_fetch_command_valid_defaults():
    cmd = FetchCommand(type="fetch", url="https://example.com")
    assert cmd.url == "https://example.com"
    assert cmd.headless is True
    assert cmd.block_ads is False


def test_fetch_command_timeout_in_range():
    cmd = FetchCommand(type="fetch", url="https://example.com", timeout=5000)
    assert cmd.timeout == 5000


def test_fetch_command_timeout_too_low():
    with pytest.raises(ValidationError):
        FetchCommand(type="fetch", url="https://example.com", timeout=500)


def test_fetch_command_timeout_too_high():
    with pytest.raises(ValidationError):
        FetchCommand(type="fetch", url="https://example.com", timeout=200000)


def test_fetch_command_wait_in_range():
    cmd = FetchCommand(type="fetch", url="https://example.com", wait=2000)
    assert cmd.wait == 2000


def test_fetch_command_wait_too_high():
    with pytest.raises(ValidationError):
        FetchCommand(type="fetch", url="https://example.com", wait=60000)


# --------------------------------------------------------------------------- #
# StealthyFetchCommand
# --------------------------------------------------------------------------- #

def test_stealthy_fetch_command_valid_defaults():
    cmd = StealthyFetchCommand(type="stealthy_fetch", url="https://example.com")
    assert cmd.url == "https://example.com"
    assert cmd.solve_cloudflare is False
    assert cmd.block_webrtc is False
    assert cmd.allow_webgl is True
    assert cmd.hide_canvas is False


def test_stealthy_fetch_command_with_stealth_options():
    cmd = StealthyFetchCommand(
        type="stealthy_fetch",
        url="https://example.com",
        solve_cloudflare=True,
        block_webrtc=True,
        hide_canvas=True,
    )
    assert cmd.solve_cloudflare is True
    assert cmd.block_webrtc is True
    assert cmd.hide_canvas is True


# --------------------------------------------------------------------------- #
# FollowCommand
# --------------------------------------------------------------------------- #

def test_follow_command_valid_defaults():
    cmd = FollowCommand(type="follow", css_selector="a.next")
    assert cmd.css_selector == "a.next"
    assert cmd.attribute == "href"
    assert cmd.headless is True
    assert cmd.use_stealthy is False


def test_follow_command_custom_attribute():
    cmd = FollowCommand(type="follow", css_selector="img", attribute="src")
    assert cmd.attribute == "src"


# --------------------------------------------------------------------------- #
# GetCommand – additional edge cases
# --------------------------------------------------------------------------- #

def test_get_command_timeout_too_high():
    with pytest.raises(ValidationError):
        GetCommand(type="get", url="https://example.com", timeout=150)
