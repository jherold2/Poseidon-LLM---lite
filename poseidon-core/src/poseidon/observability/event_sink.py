"""Database-backed telemetry helpers for Poseidon."""

from __future__ import annotations

import logging

import json
import os
from typing import Any, Optional
from uuid import uuid4

from poseidon.utils.db_connect import execute
from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

_MAX_JSON_CHARS = 8000


def _observability_enabled() -> bool:
    return os.getenv("POSEIDON_DISABLE_OBSERVABILITY") != "1" and os.getenv("POSEIDON_DISABLE_DB") != "1"


def _to_json(value: Any | None) -> Optional[str]:
    if value is None:
        return None
    try:
        payload = json.dumps(value, default=str)
    except TypeError:
        payload = json.dumps(str(value))

    if len(payload) > _MAX_JSON_CHARS:
        payload = json.dumps(
            {
                "_truncated": True,
                "length": len(payload),
                "preview": payload[: _MAX_JSON_CHARS],
            }
        )
    return payload


def _safe_execute(query: str, params: tuple[Any, ...]) -> None:
    if not _observability_enabled():
        return
    try:
        execute(query, params)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("Observability sink failed to persist event: %s", exc)


def create_workflow_run(
    workflow_name: str,
    *,
    trigger_user: str | None,
    session_id: str | None,
    is_async: bool,
    request_payload: Any,
) -> str:
    """Insert a workflow run row and return its UUID."""
    run_id = str(uuid4())
    query = """
        INSERT INTO telemetry.workflow_runs
        (id, workflow_name, trigger_user, session_id, is_async, request_payload, status)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
    """
    params = (
        run_id,
        workflow_name,
        trigger_user,
        session_id,
        is_async,
        _to_json(request_payload) or json.dumps({}),
        "queued",
    )
    _safe_execute(query, params)
    return run_id


def update_workflow_run_status(
    workflow_run_id: str,
    status: str,
    *,
    result_summary: Any | None = None,
    error: str | None = None,
    completed: bool = False,
) -> None:
    """Update workflow status, summary, or error fields."""
    set_clauses = ["status = %s", "updated_at = NOW()"]
    params: list[Any] = [status]

    if result_summary is not None:
        set_clauses.append("result_summary = %s::jsonb")
        params.append(_to_json(result_summary))

    if error is not None:
        set_clauses.append("error = %s")
        params.append(error)

    if completed:
        set_clauses.append("completed_at = NOW()")

    query = f"""
        UPDATE telemetry.workflow_runs
        SET {', '.join(set_clauses)}
        WHERE id = %s
    """
    params.append(workflow_run_id)
    _safe_execute(query, tuple(params))


def log_user_action(
    *,
    workflow_run_id: str | None,
    user_id: str | None,
    session_id: str | None,
    action_type: str,
    action_payload: Any | None = None,
) -> None:
    query = """
        INSERT INTO telemetry.user_actions
        (workflow_run_id, user_id, session_id, action_type, action_payload)
        VALUES (%s, %s, %s, %s, %s::jsonb)
    """
    params = (
        workflow_run_id,
        user_id,
        session_id,
        action_type,
        _to_json(action_payload) or json.dumps({}),
    )
    _safe_execute(query, params)


def log_application_event(
    *,
    workflow_run_id: str | None,
    event_type: str,
    event_level: str = "info",
    event_payload: Any | None = None,
) -> None:
    query = """
        INSERT INTO telemetry.application_events
        (workflow_run_id, event_type, event_level, event_payload)
        VALUES (%s, %s, %s, %s::jsonb)
    """
    params = (
        workflow_run_id,
        event_type,
        event_level,
        _to_json(event_payload) or json.dumps({}),
    )
    _safe_execute(query, params)


def log_agent_action(
    *,
    workflow_run_id: str | None,
    module: str,
    action_type: str,
    request_payload: Any | None,
    response_payload: Any | None,
    duration_ms: int | None,
    error: str | None = None,
) -> None:
    query = """
        INSERT INTO telemetry.agent_actions
        (workflow_run_id, module, action_type, request_payload, response_payload, duration_ms, error)
        VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
    """
    params = (
        workflow_run_id,
        module,
        action_type,
        _to_json(request_payload) or json.dumps({}),
        _to_json(response_payload) or json.dumps({}),
        duration_ms,
        error,
    )
    _safe_execute(query, params)
