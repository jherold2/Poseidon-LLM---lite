"""Utilities for tracking automated task assignments sent to employees."""

from __future__ import annotations

import logging

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

_ASSIGNMENT_LOG = Path("data/task_assignments.jsonl")
_ASSIGNMENT_LOG.parent.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class AssignmentRecord:
    """Canonical representation for a dispatched employee task."""

    timestamp: str
    employee_id: str
    employee_name: str
    task_id: str
    task_name: str
    channel: str
    session_id: str | None
    metadata: Dict[str, object]

    @classmethod
    def new(
        cls,
        *,
        employee: Dict[str, object],
        task: Dict[str, object],
        channel: str,
        session_id: str | None = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> "AssignmentRecord":
        return cls(
            timestamp=datetime.utcnow().isoformat(),
            employee_id=str(employee.get("id") or employee.get("employee_id") or ""),
            employee_name=str(employee.get("name") or employee.get("employee_name") or ""),
            task_id=str(task.get("id") or task.get("task_id") or ""),
            task_name=str(task.get("name") or task.get("title") or task.get("task_name") or ""),
            channel=channel,
            session_id=session_id,
            metadata=metadata or {},
        )


def _read_assignments() -> List[AssignmentRecord]:
    if not _ASSIGNMENT_LOG.exists():
        return []

    records: List[AssignmentRecord] = []
    with _ASSIGNMENT_LOG.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                records.append(AssignmentRecord(**payload))
            except Exception as exc:  # pragma: no cover - defensive parsing guard
                logger.warning("Skipping malformed assignment record: %s", exc)
    return records


def log_sent_task(
    employee: Dict[str, object],
    task: Dict[str, object],
    email_payload: Dict[str, object],
    *,
    session_id: str | None = None,
) -> AssignmentRecord:
    """
    Append a record noting an outbound task assignment.

    Args:
        employee: Canonical employee profile used for the assignment.
        task: Task definition that was dispatched.
        email_payload: Payload sent to the mailer; persisted for reproducibility.
        session_id: Optional session scope when triggered from a workflow.
    """
    record = AssignmentRecord.new(
        employee=employee,
        task=task,
        channel="email",
        session_id=session_id,
        metadata={
            "email": {
                "to": email_payload.get("to"),
                "cc": email_payload.get("cc"),
                "subject": email_payload.get("subject"),
            }
        },
    )

    with _ASSIGNMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record)) + "\n")

    logger.info(
        "Recorded assignment for employee %s (%s) task %s",
        record.employee_name,
        record.employee_id,
        record.task_id,
    )
    return record


def recent_assignments(
    *,
    employee_id: str | None = None,
    task_id: str | None = None,
    within_hours: int = 24,
) -> List[AssignmentRecord]:
    """
    Return assignment records filtered by employee/task within the requested window.
    """
    cutoff = datetime.utcnow() - timedelta(hours=within_hours)
    matches: List[AssignmentRecord] = []

    for record in _read_assignments():
        try:
            recorded_at = datetime.fromisoformat(record.timestamp)
        except ValueError:
            continue
        if recorded_at < cutoff:
            continue
        if employee_id and record.employee_id != employee_id:
            continue
        if task_id and record.task_id != task_id:
            continue
        matches.append(record)
    return matches


def has_recent_assignment(
    *,
    employee_id: str,
    task_id: str,
    within_hours: int = 12,
) -> bool:
    """
    Determine whether a given employee already received this task recently.
    """
    return bool(
        recent_assignments(employee_id=employee_id, task_id=task_id, within_hours=within_hours)
    )


def assignment_history(limit: int = 50) -> List[Dict[str, object]]:
    """
    Load the N most recent assignment records for diagnostics or reporting.
    """
    records = _read_assignments()
    slice_ = records[-limit:]
    return [asdict(item) for item in slice_]


__all__ = [
    "log_sent_task",
    "recent_assignments",
    "has_recent_assignment",
    "assignment_history",
    "AssignmentRecord",
]
