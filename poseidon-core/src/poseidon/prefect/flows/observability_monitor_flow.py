"""Prefect flow that polls Lean telemetry for anomalies and raises Andon alerts."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict, List

from prefect import flow, get_run_logger, task
from sqlalchemy import text

from poseidon.prefect.config import create_sqlalchemy_engine
from poseidon.prefect.flows.andon_alert_flow import andon_alert_flow


LEAN_SCHEMA = os.getenv("POSEIDON_LEAN_SCHEMA", "cedea_metrics")


@task(name="fetch-recent-events")
def fetch_recent_events(window_minutes: int = 10) -> List[Dict[str, object]]:
    """Fetch recent failure or warning events from the unified Lean telemetry table."""
    logger = get_run_logger()
    since = datetime.utcnow() - timedelta(minutes=window_minutes)
    engine = create_sqlalchemy_engine()
    query = text(
        f"""
        SELECT event_id, source_tool, lean_category, status, event_severity, event_timestamp, payload
        FROM {LEAN_SCHEMA}.event_log_unified
        WHERE event_timestamp >= :since
          AND (
              status ILIKE 'failed%%'
              OR event_severity IN ('warning', 'error', 'critical')
              OR lean_category IN ('Andon', 'Mura')
          )
        ORDER BY event_timestamp DESC
        """
    )
    try:
        with engine.connect() as conn:
            rows = conn.execute(query, {"since": since}).mappings().all()
    except Exception as exc:  # pragma: no cover - defensive persistence guard
        logger.warning("Failed to query Lean event log: %s", exc)
        return []
    logger.info("Observability monitor retrieved %d events", len(rows))
    return [dict(row) for row in rows]


@flow(name="Observability Monitor Flow", log_prints=False)
def observability_monitor_flow(window_minutes: int = 10) -> int:
    """Poll the Lean telemetry mart and raise Andon alerts for fresh anomalies."""
    rows = fetch_recent_events(window_minutes)
    for row in rows:
        message = (
            f"{row['lean_category']} detected in {row['source_tool']} at {row['event_timestamp']}: "
            f"status={row['status']} severity={row['event_severity']}"
        )
        andon_alert_flow(
            flow_name=f"observability:{row['source_tool']}",
            message=message,
            severity=str(row.get("event_severity") or "warning"),
        )
    return len(rows)


__all__ = ["observability_monitor_flow"]
