"""Utility tasks for recording Kaizen events."""

from __future__ import annotations

from datetime import datetime

from prefect import get_run_logger, task
from sqlalchemy import text

from poseidon.prefect.config import create_sqlalchemy_engine


@task(name="record-kaizen-event")
def record_kaizen_event(source: str, description: str, impact: str | None = None) -> None:
    """Persist a Kaizen event in the analytics schema."""
    logger = get_run_logger()
    engine = create_sqlalchemy_engine()
    insert_sql = text(
        """
        INSERT INTO analytics.kaizen_events (source, description, impact, created_at)
        VALUES (:source, :description, :impact, :created_at)
        """
    )
    payload = {
        "source": source,
        "description": description,
        "impact": impact,
        "created_at": datetime.utcnow(),
    }
    try:
        with engine.begin() as conn:
            conn.execute(insert_sql, payload)
    except Exception as exc:  # pragma: no cover - persistence guard
        logger.warning("Failed to record Kaizen event for %s: %s", source, exc)
    else:
        logger.info("Recorded Kaizen event from %s", source)


__all__ = ["record_kaizen_event"]
