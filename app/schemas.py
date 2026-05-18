"""
Pydantic schemas for request/response validation.

Command DSL
-----------
Each command in the ``commands`` array has a required ``type`` field and
command-specific optional fields.  The supported types are:

* ``get``           – plain HTTP GET via Fetcher
* ``post``          – plain HTTP POST via Fetcher
* ``fetch``         – browser fetch via DynamicFetcher
* ``stealthy_fetch``– stealth browser fetch via StealthyFetcher
* ``extract``       – apply CSS/XPath selector to the current page
* ``follow``        – select an attribute (href/src) from the current page
                     and issue a new fetch for that URL

All URL fields are validated to only accept http / https schemes.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _validate_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must use http or https scheme")
    if not parsed.netloc:
        raise ValueError("URL must include a valid host")
    return value


# --------------------------------------------------------------------------- #
# Command models
# --------------------------------------------------------------------------- #

class HttpMethod(str, Enum):
    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"


class GetCommand(BaseModel):
    type: Literal["get"]
    url: str
    headers: Optional[dict[str, str]] = None
    cookies: Optional[str] = None
    params: Optional[dict[str, str]] = None
    timeout: Optional[int] = Field(default=None, ge=1, le=120)
    proxy: Optional[str] = None
    follow_redirects: bool = True
    verify_ssl: bool = True
    impersonate: Optional[str] = None
    stealthy_headers: bool = True
    css_selector: Optional[str] = None

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        return _validate_url(v)

    @field_validator("proxy")
    @classmethod
    def proxy_scheme(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        parsed = urlparse(v)
        if parsed.scheme not in {"http", "https", "socks5", "socks5h"}:
            raise ValueError("Proxy URL must use http, https, socks5 or socks5h scheme")
        return v


class PostCommand(BaseModel):
    type: Literal["post"]
    url: str
    data: Optional[str] = None
    json_body: Optional[dict[str, Any]] = None
    headers: Optional[dict[str, str]] = None
    cookies: Optional[str] = None
    params: Optional[dict[str, str]] = None
    timeout: Optional[int] = Field(default=None, ge=1, le=120)
    proxy: Optional[str] = None
    follow_redirects: bool = True
    verify_ssl: bool = True
    impersonate: Optional[str] = None
    stealthy_headers: bool = True
    css_selector: Optional[str] = None

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        return _validate_url(v)


class FetchCommand(BaseModel):
    type: Literal["fetch"]
    url: str
    headless: bool = True
    disable_resources: bool = False
    network_idle: bool = False
    timeout: Optional[int] = Field(default=None, ge=1000, le=120000, description="ms")
    wait: Optional[int] = Field(default=None, ge=0, le=30000, description="extra wait ms")
    css_selector: Optional[str] = None
    wait_selector: Optional[str] = None
    proxy: Optional[str] = None
    extra_headers: Optional[dict[str, str]] = None
    dns_over_https: bool = False
    block_ads: bool = False
    locale: Optional[str] = None

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        return _validate_url(v)


class StealthyFetchCommand(BaseModel):
    type: Literal["stealthy_fetch"]
    url: str
    headless: bool = True
    disable_resources: bool = False
    network_idle: bool = False
    timeout: Optional[int] = Field(default=None, ge=1000, le=120000, description="ms")
    wait: Optional[int] = Field(default=None, ge=0, le=30000, description="extra wait ms")
    css_selector: Optional[str] = None
    wait_selector: Optional[str] = None
    proxy: Optional[str] = None
    extra_headers: Optional[dict[str, str]] = None
    dns_over_https: bool = False
    block_ads: bool = False
    block_webrtc: bool = False
    solve_cloudflare: bool = False
    allow_webgl: bool = True
    hide_canvas: bool = False

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        return _validate_url(v)


class ExtractCommand(BaseModel):
    type: Literal["extract"]
    css_selector: Optional[str] = None
    xpath: Optional[str] = None
    attribute: Optional[str] = None
    html: bool = False
    first_only: bool = False
    limit: Optional[int] = Field(default=None, ge=1, le=1000)

    @model_validator(mode="after")
    def at_least_one_selector(self) -> "ExtractCommand":
        if not self.css_selector and not self.xpath:
            raise ValueError("extract command requires either css_selector or xpath")
        return self


class FollowCommand(BaseModel):
    type: Literal["follow"]
    css_selector: str
    attribute: str = "href"
    headless: bool = True
    disable_resources: bool = False
    network_idle: bool = False
    timeout: Optional[int] = Field(default=None, ge=1000, le=120000, description="ms")
    use_stealthy: bool = False


# Union of all commands – Pydantic uses the ``type`` discriminator
from typing import Union, Annotated

AnyCommand = Annotated[
    Union[
        GetCommand,
        PostCommand,
        FetchCommand,
        StealthyFetchCommand,
        ExtractCommand,
        FollowCommand,
    ],
    Field(discriminator="type"),
]


# --------------------------------------------------------------------------- #
# Top-level request / response
# --------------------------------------------------------------------------- #

class RunRequest(BaseModel):
    commands: list[AnyCommand] = Field(..., min_length=1)
    cache: bool = True
    persist: bool = True

    @field_validator("commands")
    @classmethod
    def commands_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("commands must contain at least one entry")
        return v


class CommandResult(BaseModel):
    index: int
    type: str
    status: Literal["ok", "error"]
    duration_ms: float
    output: Optional[Any] = None
    error: Optional[str] = None


class RunResponse(BaseModel):
    run_id: str
    status: Literal["ok", "error"]
    cache_hit: bool = False
    commands_executed: int
    duration_ms: float
    results: list[CommandResult]
    final_output: Optional[Any] = None
