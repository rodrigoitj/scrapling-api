"""Tests for MongoDB persistence helpers (pymongo is mocked)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from pymongo.errors import PyMongoError

_VALID_OID = "507f1f77bcf86cd799439011"


# --------------------------------------------------------------------------- #
# save_run
# --------------------------------------------------------------------------- #

def test_save_run_returns_none_when_collection_unavailable():
    with patch("app.services.store._get_collection", return_value=None):
        from app.services.store import save_run

        result = save_run({"status": "ok"})
    assert result is None


def test_save_run_returns_run_id_on_success():
    oid = ObjectId(_VALID_OID)
    mock_insert_result = MagicMock()
    mock_insert_result.inserted_id = oid

    mock_col = MagicMock()
    mock_col.insert_one.return_value = mock_insert_result

    with patch("app.services.store._get_collection", return_value=mock_col):
        from app.services.store import save_run

        run_id = save_run({"status": "ok", "results": []})

    assert run_id == _VALID_OID
    mock_col.insert_one.assert_called_once()
    mock_col.update_one.assert_called_once()


def test_save_run_adds_created_at_timestamp():
    oid = ObjectId(_VALID_OID)
    mock_insert_result = MagicMock()
    mock_insert_result.inserted_id = oid
    mock_col = MagicMock()
    mock_col.insert_one.return_value = mock_insert_result

    doc: dict = {"status": "ok"}
    with patch("app.services.store._get_collection", return_value=mock_col):
        from app.services.store import save_run

        save_run(doc)

    assert "created_at" in doc
    assert isinstance(doc["created_at"], datetime)


def test_save_run_returns_none_on_pymongo_error():
    mock_col = MagicMock()
    mock_col.insert_one.side_effect = PyMongoError("write failed")

    with patch("app.services.store._get_collection", return_value=mock_col):
        from app.services.store import save_run

        result = save_run({"status": "ok"})

    assert result is None


# --------------------------------------------------------------------------- #
# get_run
# --------------------------------------------------------------------------- #

def test_get_run_returns_none_when_collection_unavailable():
    with patch("app.services.store._get_collection", return_value=None):
        from app.services.store import get_run

        result = get_run(_VALID_OID)
    assert result is None


def test_get_run_returns_none_for_invalid_object_id():
    mock_col = MagicMock()
    with patch("app.services.store._get_collection", return_value=mock_col):
        from app.services.store import get_run

        result = get_run("not-a-valid-oid")

    assert result is None
    mock_col.find_one.assert_not_called()


def test_get_run_returns_none_when_document_not_found():
    mock_col = MagicMock()
    mock_col.find_one.return_value = None

    with patch("app.services.store._get_collection", return_value=mock_col):
        from app.services.store import get_run

        result = get_run(_VALID_OID)

    assert result is None


def test_get_run_returns_document_with_string_run_id():
    oid = ObjectId(_VALID_OID)
    doc = {
        "_id": oid,
        "status": "ok",
        "cache_hit": False,
        "commands_executed": 1,
        "results": [],
    }
    mock_col = MagicMock()
    mock_col.find_one.return_value = doc

    with patch("app.services.store._get_collection", return_value=mock_col):
        from app.services.store import get_run

        result = get_run(_VALID_OID)

    assert result is not None
    assert result["run_id"] == _VALID_OID
    assert "_id" not in result


def test_get_run_serializes_datetime_to_isoformat():
    oid = ObjectId(_VALID_OID)
    created = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
    doc = {"_id": oid, "status": "ok", "created_at": created, "results": []}
    mock_col = MagicMock()
    mock_col.find_one.return_value = doc

    with patch("app.services.store._get_collection", return_value=mock_col):
        from app.services.store import get_run

        result = get_run(_VALID_OID)

    assert isinstance(result["created_at"], str)
    assert "2026-05-18" in result["created_at"]


def test_get_run_returns_none_on_pymongo_error():
    mock_col = MagicMock()
    mock_col.find_one.side_effect = PyMongoError("read failed")

    with patch("app.services.store._get_collection", return_value=mock_col):
        from app.services.store import get_run

        result = get_run(_VALID_OID)

    assert result is None


# --------------------------------------------------------------------------- #
# health_check
# --------------------------------------------------------------------------- #

def test_store_health_check_unavailable():
    with patch("app.services.store._get_collection", return_value=None):
        from app.services.store import health_check

        result = health_check()

    assert result["status"] == "unavailable"


def test_store_health_check_ok():
    mock_col = MagicMock()
    mock_col.database.command.return_value = {"ok": 1}

    with patch("app.services.store._get_collection", return_value=mock_col):
        from app.services.store import health_check

        result = health_check()

    assert result["status"] == "ok"
    mock_col.database.command.assert_called_once_with("ping")


def test_store_health_check_error_on_command_failure():
    mock_col = MagicMock()
    mock_col.database.command.side_effect = Exception("connection refused")

    with patch("app.services.store._get_collection", return_value=mock_col):
        from app.services.store import health_check

        result = health_check()

    assert result["status"] == "error"
    assert "connection refused" in result["detail"]
