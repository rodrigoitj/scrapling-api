"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from app import create_app
from app.config import Config


class TestConfig(Config):
    TESTING = True
    CACHE_ENABLED = False
    PERSIST_ENABLED = False
    REDIS_URL = "redis://localhost:6379/0"
    MONGO_URI = "mongodb://localhost:27017"
    ALLOWED_HOSTS: list[str] = []
    BLOCKED_HOSTS: list[str] = []


@pytest.fixture
def app():
    application = create_app(TestConfig)
    yield application


@pytest.fixture
def client(app):
    return app.test_client()
