"""Alerting utilities for Lean Andon signalling."""

from __future__ import annotations

from typing import Sequence

from prefect import get_run_logger, task

try:
    from prefect.events import emit_event
except Exception:  # pragma: no cover
    def emit_event(**_: str) -> None:
        return


@task(name="emit-andon-alert")
def emit_andon_alert(event_ids: Sequence[str], message: str) -> None:
    """
    Emit a Prefect event to flag a Lean Andon alert.

    Parameters
    ----------
    event_ids:
        Identifiers of the events triggering the alert.
    message:
        Human-readable description of the issue.
    """
    logger = get_run_logger()
    payload = {"event_ids": list(event_ids), "message": message}
    emit_event(event="poseidon.andon.alert", payload=payload)
    logger.warning("Emitted Andon alert for %s events: %s", len(event_ids), message)
