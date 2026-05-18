from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class Config:
    # ------------------------------------------------------------------ Flask
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "change-me-in-production")
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # ------------------------------------------------------------------ Redis
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CACHE_TTL: int = int(os.environ.get("CACHE_TTL_SECONDS", "300"))
    CACHE_ENABLED: bool = os.environ.get("CACHE_ENABLED", "true").lower() == "true"

    # ----------------------------------------------------------------- Mongo
    MONGO_URI: Optional[str] = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB: str = os.environ.get("MONGO_DB", "scrapling_api")
    PERSIST_ENABLED: bool = os.environ.get("PERSIST_ENABLED", "true").lower() == "true"

    # ---------------------------------------------------------------- Limits
    MAX_COMMANDS: int = int(os.environ.get("MAX_COMMANDS", "20"))
    MAX_OUTPUT_LENGTH: int = int(os.environ.get("MAX_OUTPUT_LENGTH", "50000"))
    DEFAULT_TIMEOUT_SECONDS: int = int(os.environ.get("DEFAULT_TIMEOUT_SECONDS", "30"))
    DEFAULT_BROWSER_TIMEOUT_MS: int = int(
        os.environ.get("DEFAULT_BROWSER_TIMEOUT_MS", "30000")
    )

    # --------------------------------------------------------- Host controls
    # Comma-separated list of allowed hosts; empty means allow all
    ALLOWED_HOSTS: list[str] = [
        h.strip()
        for h in os.environ.get("ALLOWED_HOSTS", "").split(",")
        if h.strip()
    ]
    # Comma-separated list of blocked hosts; always applied
    BLOCKED_HOSTS: list[str] = [
        h.strip()
        for h in os.environ.get("BLOCKED_HOSTS", "").split(",")
        if h.strip()
    ]
