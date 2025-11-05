"""Handlers for logging Kaizen improvements."""

from __future__ import annotations

import logging
from typing import Any

from poseidon.prefect.tasks.kaizen_tasks import record_kaizen_event


LOGGER = logging.getLogger(__name__)


def on_flow_optimized(flow_name: str, duration_before: float, duration_after: float) -> None:
    improvement = duration_before - duration_after
    impact = f"{(improvement / duration_before) * 100:.2f}% runtime reduction" if duration_before else ""
    record_kaizen_event.fn(source=flow_name, description="Flow optimization", impact=impact)


def on_metric_improved(metric_name: str, value_before: float, value_after: float) -> None:
    delta = value_after - value_before
    impact = f"Δ {delta:+.4f}"
    record_kaizen_event.fn(source=metric_name, description="Metric improvement", impact=impact)


def log_kaizen_event(source: str, description: str, impact: str | None = None) -> None:
    record_kaizen_event.fn(source=source, description=description, impact=impact)


def on_event(event: Any) -> None:
    payload = getattr(event, "payload", {})
    record_kaizen_event.fn(
        source=payload.get("source", "unknown"),
        description=payload.get("description", "Kaizen event"),
        impact=payload.get("impact"),
    )
    LOGGER.info("Recorded Kaizen event for source %s", payload.get("source", "unknown"))
