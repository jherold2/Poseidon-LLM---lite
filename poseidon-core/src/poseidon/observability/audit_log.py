"""Unified JSONL audit logging for Poseidon."""

from __future__ import annotations

import logging

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

_DEFAULT_AUDIT_PATH = Path(
    os.getenv("POSEIDON_AUDIT_LOG_PATH", "data/audit/poseidon_audit_log.jsonl")
)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _normalise_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(json.dumps(payload, default=str))
    except TypeError:
        # Fallback: coerce entire payload to string to avoid log loss.
        return {"raw": str(payload)}


def append_event(event_type: str, payload: Dict[str, Any]) -> Path:
    """
    Append an audit event to the shared JSONL log and return the file path.

    Args:
        event_type: Logical category for the event (e.g., ``decision_recorded``).
        payload: Event metadata to persist. Non-serialisable values are coerced to strings.
    """

    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary")

    _ensure_parent(_DEFAULT_AUDIT_PATH)
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "payload": _normalise_payload(payload),
    }

    try:
        with _DEFAULT_AUDIT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        logger.info("Audit event recorded for %s", event_type)
    except OSError as exc:
        logger.error("Failed to append audit event %s: %s", event_type, exc)
        raise

    return _DEFAULT_AUDIT_PATH


def get_audit_log_path() -> Path:
    """Expose the resolved audit log path for downstream tooling and docs."""

    _ensure_parent(_DEFAULT_AUDIT_PATH)
    return _DEFAULT_AUDIT_PATH


__all__ = ["append_event", "get_audit_log_path"]
