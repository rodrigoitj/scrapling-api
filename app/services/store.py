"""
MongoDB persistence helpers.

Each run is stored in the ``runs`` collection of the configured database.
Documents follow this shape::

    {
        "_id":            ObjectId,
        "run_id":         str  (hex string of _id),
        "status":         "ok" | "error",
        "cache_hit":      bool,
        "commands":       list[dict],   # serialised command payloads
        "results":        list[dict],   # CommandResult dicts
        "final_output":   Any,
        "commands_executed": int,
        "duration_ms":    float,
        "created_at":     datetime,
    }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from flask import current_app
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

log = logging.getLogger(__name__)

_mongo: Optional[MongoClient] = None


def _get_collection() -> Optional[Collection]:
    global _mongo
    try:
        if _mongo is None:
            uri: str = current_app.config["MONGO_URI"]
            _mongo = MongoClient(
                uri,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000,
            )
        db_name: str = current_app.config["MONGO_DB"]
        return _mongo[db_name]["runs"]
    except Exception as exc:
        log.warning("MongoDB unavailable: %s", exc)
        return None


def save_run(run_doc: dict[str, Any]) -> Optional[str]:
    """Persist a run document and return its string run_id, or None on failure."""
    col = _get_collection()
    if col is None:
        return None
    try:
        run_doc["created_at"] = datetime.now(tz=timezone.utc)
        result = col.insert_one(run_doc)
        run_id = str(result.inserted_id)
        col.update_one({"_id": result.inserted_id}, {"$set": {"run_id": run_id}})
        return run_id
    except PyMongoError as exc:
        log.warning("MongoDB save_run failed: %s", exc)
        return None


def get_run(run_id: str) -> Optional[dict[str, Any]]:
    """Retrieve a run document by its string run_id."""
    col = _get_collection()
    if col is None:
        return None
    try:
        oid = ObjectId(run_id)
    except Exception:
        return None
    try:
        doc = col.find_one({"_id": oid})
        if doc is None:
            return None
        doc["run_id"] = str(doc["_id"])
        doc.pop("_id", None)
        if isinstance(doc.get("created_at"), datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        return doc
    except PyMongoError as exc:
        log.warning("MongoDB get_run failed: %s", exc)
        return None


def health_check() -> dict[str, Any]:
    col = _get_collection()
    if col is None:
        return {"status": "unavailable"}
    try:
        col.database.command("ping")
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
