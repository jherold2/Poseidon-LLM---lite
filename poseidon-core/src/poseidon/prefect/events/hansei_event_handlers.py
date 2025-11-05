"""Handlers supporting Hansei (reflection) logging."""

from __future__ import annotations

from datetime import datetime

import logging

from sqlalchemy import text

from poseidon.prefect.config import create_sqlalchemy_engine

LOGGER = logging.getLogger(__name__)


def _insert(flow_name: str, category: str, cause: str, resolution: str) -> None:
    engine = create_sqlalchemy_engine()
    insert_sql = text(
        """
        INSERT INTO analytics.hansei_log (flow_name, category, cause, resolution, created_at)
        VALUES (:flow_name, :category, :cause, :resolution, :created_at)
        """
    )
    with engine.begin() as conn:
        conn.execute(
            insert_sql,
            {
                "flow_name": flow_name,
                "category": category,
                "cause": cause,
                "resolution": resolution,
                "created_at": datetime.utcnow(),
            },
        )


def on_post_mortem(flow_name: str, cause: str, resolution: str) -> None:
    try:
        _insert(flow_name, "System Failure", cause, resolution)
    except Exception as exc:  # pragma: no cover - persistence guard
        LOGGER.warning("Failed to record Hansei post-mortem: %s", exc)
    else:
        LOGGER.info("Recorded Hansei post-mortem for %s", flow_name)


def on_process_reflection(flow_name: str, improvement: str) -> None:
    try:
        _insert(flow_name, "Kaizen Reflection", "Periodic review", improvement)
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("Failed to record Hansei reflection: %s", exc)
    else:
        LOGGER.info("Recorded Hansei reflection for %s", flow_name)
