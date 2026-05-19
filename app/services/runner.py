"""
Sequential Scrapling command runner.

Execution model
---------------
Commands are executed strictly in array order.  Each command operates on an
execution context that carries:

* ``page``     – the current Scrapling Response/page object (may be None)
* ``url``      – the URL that produced the current page
* ``outputs``  – accumulated list of CommandResult dicts

Supported command types
-----------------------
get             → Fetcher (plain HTTP, no browser)
post            → Fetcher (plain HTTP POST, no browser)
fetch           → DynamicFetcher (headless Playwright browser)
stealthy_fetch  → StealthyFetcher (stealth Playwright browser)
extract         → apply CSS / XPath selector to the current page
follow          → pull a link from the current page, then fetch it
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from flask import current_app

from app.schemas import (
    AnyCommand,
    CommandResult,
    ExtractCommand,
    FetchCommand,
    FollowCommand,
    GetCommand,
    InteractCommand,
    PostCommand,
    StealthyFetchCommand,
)

# Module-level imports allow tests to patch app.services.runner.Fetcher etc.
# The try/except makes the module importable in environments where scrapling is
# not installed (e.g. a CI environment that only installs test dependencies).
try:
    from scrapling.fetchers import DynamicFetcher, Fetcher, StealthyFetcher
except ImportError:  # pragma: no cover
    Fetcher = None  # type: ignore[assignment,misc]
    DynamicFetcher = None  # type: ignore[assignment,misc]
    StealthyFetcher = None  # type: ignore[assignment,misc]


# --------------------------------------------------------------------------- #
# Security helpers
# --------------------------------------------------------------------------- #

def _check_host(url: str) -> None:
    """Raise ValueError if the URL host is blocked or not on the allowlist."""
    host = urlparse(url).hostname or ""

    blocked: list[str] = current_app.config.get("BLOCKED_HOSTS", [])
    if any(host == b or host.endswith(f".{b}") for b in blocked):
        raise ValueError(f"Host '{host}' is blocked by server policy")

    allowed: list[str] = current_app.config.get("ALLOWED_HOSTS", [])
    if allowed and not any(host == a or host.endswith(f".{a}") for a in allowed):
        raise ValueError(f"Host '{host}' is not on the allowed list")


def _truncate(value: Any, max_len: int) -> Any:
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + f"… [truncated, total {len(value)} chars]"
    if isinstance(value, list):
        result = []
        remaining = max_len
        for item in value:
            if remaining <= 0:
                result.append("[more items truncated]")
                break
            if isinstance(item, str):
                item = item[:remaining]
                remaining -= len(item)
            result.append(item)
        return result
    return value


# --------------------------------------------------------------------------- #
# Execution context
# --------------------------------------------------------------------------- #

@dataclass
class _Context:
    page: Any = None
    url: str = ""
    results: list[CommandResult] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Individual command handlers
# --------------------------------------------------------------------------- #

def _run_get(cmd: GetCommand, ctx: _Context, cfg: dict) -> CommandResult:
    _check_host(cmd.url)

    kwargs: dict[str, Any] = {
        "stealthy_headers": cmd.stealthy_headers,
        "timeout": cmd.timeout or cfg["DEFAULT_TIMEOUT_SECONDS"],
        "follow_redirects": cmd.follow_redirects,
    }
    if cmd.headers:
        kwargs["headers"] = cmd.headers
    if cmd.cookies:
        kwargs["cookies"] = cmd.cookies
    if cmd.params:
        kwargs["params"] = cmd.params
    if cmd.proxy:
        kwargs["proxy"] = cmd.proxy
    if cmd.impersonate:
        kwargs["impersonate"] = cmd.impersonate
    if not cmd.verify_ssl:
        kwargs["verify"] = False

    page = Fetcher.get(cmd.url, **kwargs)
    ctx.page = page
    ctx.url = cmd.url

    output: Any
    if cmd.css_selector:
        output = _truncate(
            page.css(cmd.css_selector + "::text").getall(),
            cfg["MAX_OUTPUT_LENGTH"],
        )
    else:
        output = _truncate(page.text, cfg["MAX_OUTPUT_LENGTH"])

    return _ok(output)


def _run_post(cmd: PostCommand, ctx: _Context, cfg: dict) -> CommandResult:
    _check_host(cmd.url)

    kwargs: dict[str, Any] = {
        "stealthy_headers": cmd.stealthy_headers,
        "timeout": cmd.timeout or cfg["DEFAULT_TIMEOUT_SECONDS"],
        "follow_redirects": cmd.follow_redirects,
    }
    if cmd.headers:
        kwargs["headers"] = cmd.headers
    if cmd.cookies:
        kwargs["cookies"] = cmd.cookies
    if cmd.params:
        kwargs["params"] = cmd.params
    if cmd.proxy:
        kwargs["proxy"] = cmd.proxy
    if cmd.data:
        kwargs["data"] = cmd.data
    if cmd.json_body:
        kwargs["json"] = cmd.json_body
    if cmd.impersonate:
        kwargs["impersonate"] = cmd.impersonate
    if not cmd.verify_ssl:
        kwargs["verify"] = False

    page = Fetcher.post(cmd.url, **kwargs)
    ctx.page = page
    ctx.url = cmd.url

    output: Any
    if cmd.css_selector:
        output = _truncate(
            page.css(cmd.css_selector + "::text").getall(),
            cfg["MAX_OUTPUT_LENGTH"],
        )
    else:
        output = _truncate(page.text, cfg["MAX_OUTPUT_LENGTH"])

    return _ok(output)


def _run_fetch(cmd: FetchCommand, ctx: _Context, cfg: dict) -> CommandResult:
    _check_host(cmd.url)

    kwargs: dict[str, Any] = {
        "headless": cmd.headless,
        "disable_resources": cmd.disable_resources,
        "network_idle": cmd.network_idle,
        "timeout": cmd.timeout or cfg["DEFAULT_BROWSER_TIMEOUT_MS"],
        "block_ads": cmd.block_ads,
        "dns_over_https": cmd.dns_over_https,
    }
    if cmd.wait:
        kwargs["wait"] = cmd.wait
    if cmd.wait_selector:
        kwargs["wait_selector"] = cmd.wait_selector
    if cmd.proxy:
        kwargs["proxy"] = cmd.proxy
    if cmd.extra_headers:
        kwargs["extra_headers"] = cmd.extra_headers
    if cmd.locale:
        kwargs["locale"] = cmd.locale

    page = DynamicFetcher.fetch(cmd.url, **kwargs)
    ctx.page = page
    ctx.url = cmd.url

    output: Any
    if cmd.css_selector:
        output = _truncate(
            page.css(cmd.css_selector + "::text").getall(),
            cfg["MAX_OUTPUT_LENGTH"],
        )
    else:
        output = _truncate(page.text, cfg["MAX_OUTPUT_LENGTH"])

    return _ok(output)


def _run_stealthy_fetch(cmd: StealthyFetchCommand, ctx: _Context, cfg: dict) -> CommandResult:
    _check_host(cmd.url)

    kwargs: dict[str, Any] = {
        "headless": cmd.headless,
        "disable_resources": cmd.disable_resources,
        "network_idle": cmd.network_idle,
        "timeout": cmd.timeout or cfg["DEFAULT_BROWSER_TIMEOUT_MS"],
        "block_ads": cmd.block_ads,
        "dns_over_https": cmd.dns_over_https,
        "block_webrtc": cmd.block_webrtc,
        "solve_cloudflare": cmd.solve_cloudflare,
        "allow_webgl": cmd.allow_webgl,
        "hide_canvas": cmd.hide_canvas,
    }
    if cmd.wait:
        kwargs["wait"] = cmd.wait
    if cmd.wait_selector:
        kwargs["wait_selector"] = cmd.wait_selector
    if cmd.proxy:
        kwargs["proxy"] = cmd.proxy
    if cmd.extra_headers:
        kwargs["extra_headers"] = cmd.extra_headers

    page = StealthyFetcher.fetch(cmd.url, **kwargs)
    ctx.page = page
    ctx.url = cmd.url

    output: Any
    if cmd.css_selector:
        output = _truncate(
            page.css(cmd.css_selector + "::text").getall(),
            cfg["MAX_OUTPUT_LENGTH"],
        )
    else:
        output = _truncate(page.text, cfg["MAX_OUTPUT_LENGTH"])

    return _ok(output)


def _run_extract(cmd: ExtractCommand, ctx: _Context, cfg: dict) -> CommandResult:
    if ctx.page is None:
        raise ValueError("extract command requires a prior fetch command")

    elements: Any
    if cmd.css_selector:
        if cmd.attribute:
            selector = f"{cmd.css_selector}::attr({cmd.attribute})"
            elements = ctx.page.css(selector).getall()
        elif cmd.html:
            elements = ctx.page.css(cmd.css_selector).getall()
        else:
            selector = f"{cmd.css_selector}::text"
            elements = ctx.page.css(selector).getall()
    else:
        # XPath
        elements = ctx.page.xpath(cmd.xpath).getall()  # type: ignore[arg-type]

    if cmd.first_only:
        elements = elements[:1]
    elif cmd.limit:
        elements = elements[: cmd.limit]

    output = _truncate(elements, cfg["MAX_OUTPUT_LENGTH"])
    return _ok(output)


def _run_follow(cmd: FollowCommand, ctx: _Context, cfg: dict) -> CommandResult:
    if ctx.page is None:
        raise ValueError("follow command requires a prior fetch command")

    links = ctx.page.css(f"{cmd.css_selector}::attr({cmd.attribute})").getall()
    if not links:
        raise ValueError(f"follow: no elements matched '{cmd.css_selector}'")

    raw_url = links[0]
    # Resolve relative URLs against the current page URL
    target_url = urljoin(ctx.url, raw_url)
    _check_host(target_url)

    browser_kwargs: dict[str, Any] = {
        "headless": cmd.headless,
        "disable_resources": cmd.disable_resources,
        "network_idle": cmd.network_idle,
        "timeout": cmd.timeout or cfg["DEFAULT_BROWSER_TIMEOUT_MS"],
    }

    if cmd.use_stealthy:
        page = StealthyFetcher.fetch(target_url, **browser_kwargs)
    else:
        page = DynamicFetcher.fetch(target_url, **browser_kwargs)

    ctx.page = page
    ctx.url = target_url

    output = _truncate(page.html, cfg["MAX_OUTPUT_LENGTH"])
    return _ok(output)


def _run_interact(cmd: InteractCommand, ctx: _Context, cfg: dict) -> CommandResult:
    """Navigate to a URL and perform interactive browser actions via Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("playwright is required for the 'interact' command") from exc

    try:
        from scrapling.parser import Selector as ScraplingSelector
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("scrapling is required for the 'interact' command") from exc

    _check_host(cmd.url)
    timeout_ms = cmd.timeout or cfg["DEFAULT_BROWSER_TIMEOUT_MS"]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=cmd.headless)
        try:
            page = browser.new_page()
            page.goto(cmd.url, wait_until="domcontentloaded", timeout=timeout_ms)

            for act in cmd.actions:
                act_timeout = act.timeout or timeout_ms
                if act.action == "fill":
                    page.fill(act.selector, act.value or "", timeout=act_timeout)  # type: ignore[arg-type]
                elif act.action == "click":
                    page.click(act.selector, timeout=act_timeout)  # type: ignore[arg-type]
                    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
                elif act.action == "wait_for_selector":
                    page.wait_for_selector(act.selector, timeout=act_timeout)  # type: ignore[arg-type]
                elif act.action == "wait_for_load_state":
                    page.wait_for_load_state(act.state or "load", timeout=act_timeout)
                elif act.action == "hover":
                    page.hover(act.selector, timeout=act_timeout)  # type: ignore[arg-type]
                elif act.action == "press":
                    page.press(act.selector, act.value or "Enter", timeout=act_timeout)  # type: ignore[arg-type]

            html = page.content()
            final_url = page.url
        finally:
            browser.close()

    scrapling_page = ScraplingSelector(html)
    ctx.page = scrapling_page
    ctx.url = final_url

    output: Any
    if cmd.css_selector:
        output = _truncate(
            scrapling_page.css(cmd.css_selector + "::text").getall(),
            cfg["MAX_OUTPUT_LENGTH"],
        )
    else:
        output = _truncate(html, cfg["MAX_OUTPUT_LENGTH"])

    return _ok(output)


# --------------------------------------------------------------------------- #
# Dispatcher map
# --------------------------------------------------------------------------- #

_HANDLERS = {
    "get": _run_get,
    "post": _run_post,
    "fetch": _run_fetch,
    "stealthy_fetch": _run_stealthy_fetch,
    "extract": _run_extract,
    "follow": _run_follow,
    "interact": _run_interact,
}


def _ok(output: Any) -> CommandResult:
    # A sentinel; duration is filled in by the caller
    return CommandResult(index=0, type="", status="ok", duration_ms=0.0, output=output)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def execute_commands(commands: list[AnyCommand]) -> list[CommandResult]:
    """
    Execute *commands* sequentially and return a list of :class:`CommandResult`.

    Raises nothing — errors are captured per-command and execution halts on
    the first failed command.
    """
    cfg = {
        "MAX_OUTPUT_LENGTH": current_app.config["MAX_OUTPUT_LENGTH"],
        "DEFAULT_TIMEOUT_SECONDS": current_app.config["DEFAULT_TIMEOUT_SECONDS"],
        "DEFAULT_BROWSER_TIMEOUT_MS": current_app.config["DEFAULT_BROWSER_TIMEOUT_MS"],
    }

    ctx = _Context()
    results: list[CommandResult] = []

    for idx, cmd in enumerate(commands):
        cmd_type = cmd.type  # type: ignore[union-attr]
        handler = _HANDLERS.get(cmd_type)
        if handler is None:
            results.append(
                CommandResult(
                    index=idx,
                    type=cmd_type,
                    status="error",
                    duration_ms=0.0,
                    error=f"Unknown command type: {cmd_type}",
                )
            )
            break

        t0 = time.perf_counter()
        try:
            result = handler(cmd, ctx, cfg)  # type: ignore[call-arg]
            elapsed = (time.perf_counter() - t0) * 1000
            result.index = idx
            result.type = cmd_type
            result.duration_ms = round(elapsed, 2)
            results.append(result)
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(
                CommandResult(
                    index=idx,
                    type=cmd_type,
                    status="error",
                    duration_ms=round(elapsed, 2),
                    error=str(exc),
                )
            )
            break  # Halt on first error

    return results
