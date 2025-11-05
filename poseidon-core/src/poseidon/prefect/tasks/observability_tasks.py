"""Observability helpers bridging Prefect flows with Poseidon's telemetry sink."""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pandas as pd
import requests
from prefect import get_run_logger, runtime, task

from poseidon.prefect.config import create_sqlalchemy_engine

try:  # Prefect event emission is optional for local runs
    from prefect.events import emit_event
except Exception:  # pragma: no cover - Prefect events unavailable
    def emit_event(**_: Any) -> None:
        return

from poseidon.observability.event_sink import (
    create_workflow_run,
    log_application_event,
    update_workflow_run_status,
)


@dataclass
class ObservedRun:
    name: str
    run_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    completed: bool = False

    def log(self, event_type: str, *, level: str = "info", payload: Optional[Dict[str, Any]] = None) -> None:
        log_application_event(
            workflow_run_id=self.run_id,
            event_type=event_type,
            event_level=level,
            event_payload=payload or {},
        )

    def mark_running(self) -> None:
        update_workflow_run_status(self.run_id, "running")

    def mark_completed(self, summary: Optional[Dict[str, Any]] = None) -> None:
        update_workflow_run_status(self.run_id, "completed", result_summary=summary or {}, completed=True)
        self.completed = True

    def mark_failed(self, error: str) -> None:
        update_workflow_run_status(self.run_id, "failed", error=error, completed=True)
        self.completed = True


@task(name="ingest-observability-events", retries=2, retry_delay_seconds=30)
def ingest_observability_events(
    endpoint: Optional[str] = None,
    table_name: str = "observability_events",
    schema: str = "raw_events",
) -> int:
    """Persist observability alerts and anomalies into Postgres."""
    logger = get_run_logger()
    url = endpoint or os.getenv("OBSERVABILITY_EVENT_URL", "http://observability-api.internal/logs")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    events = response.json()
    if not events:
        logger.info("Observability endpoint %s returned no events.", url)
        return 0

    df = pd.DataFrame(events)
    engine = create_sqlalchemy_engine()
    df.to_sql(table_name, con=engine, schema=schema, if_exists="append", index=False)
    logger.info("Ingested %s observability events into %s.%s", len(df), schema, table_name)
    return len(df)


@contextlib.contextmanager
def flow_run_guard(flow_name: str, *, payload: Optional[Dict[str, Any]] = None):
    logger = get_run_logger()
    payload = payload or {}
    run_id = create_workflow_run(
        workflow_name=flow_name,
        trigger_user=payload.get("trigger_user"),
        session_id=payload.get("session_id"),
        is_async=False,
        request_payload=payload,
    )
    guard = ObservedRun(name=flow_name, run_id=run_id, payload=payload)
    guard.log("flow_scheduled", payload=payload)
    emit_event(
        event=f"poseidon.prefect.{flow_name}.scheduled",
        resource={"prefect.resource.id": run_id},
        payload=payload,
    )
    logger.info("Scheduled Prefect flow %s (run_id=%s)", flow_name, run_id)
    try:
        guard.mark_running()
        guard.log("flow_started")
        emit_event(
            event=f"poseidon.prefect.{flow_name}.started",
            resource={"prefect.resource.id": runtime.flow_run.id if runtime.flow_run else run_id},
            payload=payload,
        )
        yield guard
    except Exception as exc:  # pragma: no cover - defensive
        guard.log("flow_failed", level="error", payload={"error": str(exc)})
        guard.mark_failed(str(exc))
        emit_event(
            event=f"poseidon.prefect.{flow_name}.failed",
            resource={"prefect.resource.id": runtime.flow_run.id if runtime.flow_run else run_id},
            payload={"error": str(exc), **payload},
        )
        logger.exception("Prefect flow %s failed", flow_name)
        raise
    else:
        if not guard.completed:
            guard.mark_completed()
        guard.log("flow_completed")
        emit_event(
            event=f"poseidon.prefect.{flow_name}.completed",
            resource={"prefect.resource.id": runtime.flow_run.id if runtime.flow_run else run_id},
            payload=payload,
        )
        logger.info("Prefect flow %s completed", flow_name)
