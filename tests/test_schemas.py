"""Tests for request/command schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    ExtractCommand,
    FetchCommand,
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
