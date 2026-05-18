"""
API routes.

Endpoints
---------
GET  /health               – liveness / dependency health
POST /api/v1/runs          – execute a command workflow
GET  /api/v1/runs/<run_id> – retrieve a persisted run
GET  /api/v1/docs          – redirect to OpenAPI spec
"""

from __future__ import annotations

import time
import uuid
import logging
from typing import Any

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from pydantic import ValidationError

from app.schemas import CommandResult, RunRequest, RunResponse
from app.services import cache as cache_svc
from app.services import store as store_svc
from app.services.runner import execute_commands

log = logging.getLogger(__name__)

bp = Blueprint("api", __name__)


# --------------------------------------------------------------------------- #
# /health
# --------------------------------------------------------------------------- #

@bp.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "dependencies": {
                "redis": cache_svc.health_check(),
                "mongodb": store_svc.health_check(),
            },
        }
    )


# --------------------------------------------------------------------------- #
# POST /api/v1/runs
# --------------------------------------------------------------------------- #

@bp.post("/api/v1/runs")
def create_run():
    # ---- Parse & validate request body -----------------------------------
    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    try:
        run_req = RunRequest.model_validate(body)
    except ValidationError as exc:
        return jsonify({"error": "Validation failed", "detail": exc.errors()}), 422

    # ---- Enforce command count limit -------------------------------------
    max_cmds: int = current_app.config["MAX_COMMANDS"]
    if len(run_req.commands) > max_cmds:
        return jsonify(
            {"error": f"Too many commands. Maximum allowed: {max_cmds}"}
        ), 422

    # ---- Cache lookup (skip if cache=false) ------------------------------
    cache_key = cache_svc.make_cache_key(body)
    cache_enabled: bool = current_app.config["CACHE_ENABLED"] and run_req.cache

    if cache_enabled:
        cached = cache_svc.get_cached(cache_key)
        if cached is not None:
            cached["cache_hit"] = True
            return jsonify(cached), 200

    # ---- Execute commands ------------------------------------------------
    t0 = time.perf_counter()
    results: list[CommandResult] = execute_commands(run_req.commands)
    total_ms = round((time.perf_counter() - t0) * 1000, 2)

    # Derive overall status from individual results
    has_error = any(r.status == "error" for r in results)
    overall_status = "error" if has_error else "ok"

    # Final output is the output of the last successful command
    final_output: Any = None
    for r in reversed(results):
        if r.status == "ok":
            final_output = r.output
            break

    run_id = uuid.uuid4().hex

    response_body = RunResponse(
        run_id=run_id,
        status=overall_status,
        cache_hit=False,
        commands_executed=len(results),
        duration_ms=total_ms,
        results=results,
        final_output=final_output,
    ).model_dump()

    # ---- Persist run record (optional) -----------------------------------
    persist_enabled: bool = current_app.config["PERSIST_ENABLED"] and run_req.persist
    if persist_enabled:
        run_doc = {
            **response_body,
            "commands": [c.model_dump() for c in run_req.commands],
        }
        stored_id = store_svc.save_run(run_doc)
        if stored_id:
            response_body["run_id"] = stored_id

    # ---- Write to cache --------------------------------------------------
    if cache_enabled and overall_status == "ok":
        ttl: int = current_app.config["CACHE_TTL"]
        cache_svc.set_cached(cache_key, response_body, ttl)

    status_code = 200 if overall_status == "ok" else 422
    return jsonify(response_body), status_code


# --------------------------------------------------------------------------- #
# GET /api/v1/runs/<run_id>
# --------------------------------------------------------------------------- #

@bp.get("/api/v1/runs/<run_id>")
def get_run(run_id: str):
    if not current_app.config["PERSIST_ENABLED"]:
        return jsonify({"error": "Run persistence is disabled"}), 503

    run = store_svc.get_run(run_id)
    if run is None:
        return jsonify({"error": "Run not found"}), 404

    return jsonify(run), 200


# --------------------------------------------------------------------------- #
# GET /api/v1/docs  →  serve the OpenAPI spec
# --------------------------------------------------------------------------- #

@bp.get("/api/v1/docs")
def api_docs():
    import os
    docs_dir = os.path.join(current_app.root_path, "..", "docs")
    return send_from_directory(os.path.abspath(docs_dir), "openapi.yaml")
