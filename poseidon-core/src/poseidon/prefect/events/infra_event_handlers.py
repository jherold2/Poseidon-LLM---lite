"""Infrastructure event handlers for Prefect orchestration."""

from __future__ import annotations

from poseidon.prefect.events.andon_event_handlers import on_container_restart
from poseidon.prefect.flows.andon_alert_flow import andon_alert_flow


def on_agent_disconnected(agent_name: str) -> None:
    andon_alert_flow("prefect_agent_monitor", f"Agent `{agent_name}` disconnected", severity="critical")


def on_disk_space_low(host: str, usage_percent: float) -> None:
    if usage_percent > 90:
        andon_alert_flow("infra_monitor", f"Disk space warning on `{host}`: {usage_percent:.1f}%", severity="warning")


def on_memory_pressure(host: str, usage_percent: float) -> None:
    if usage_percent > 85:
        andon_alert_flow("infra_monitor", f"High memory usage on `{host}`: {usage_percent:.1f}%", severity="warning")


def on_container_restart_event(service_name: str, reason: str) -> None:
    on_container_restart(service_name, reason)
