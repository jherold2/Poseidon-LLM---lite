"""Event handlers for ML model monitoring."""

from __future__ import annotations

from poseidon.prefect.flows.andon_alert_flow import andon_alert_flow
from poseidon.prefect.tasks.kaizen_tasks import record_kaizen_event


def on_model_drift(model_name: str, metric: str, drop_percent: float) -> None:
    message = f"Model `{model_name}` drift detected: {metric} dropped {drop_percent:.2f}%"
    andon_alert_flow(model_name, message, severity="warning")


def on_model_retrained(model_name: str, improvement: str | None = None) -> None:
    record_kaizen_event.fn(source=model_name, description="Model retrained", impact=improvement)


def on_model_registry_update(model_name: str, new_version: str) -> None:
    record_kaizen_event.fn(
        source=model_name,
        description="Model registry update",
        impact=f"Version {new_version}",
    )
