"""Handlers for Andon-triggered Prefect events."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from poseidon.prefect.flows.andon_alert_flow import andon_alert_flow


def _get(mapping: Mapping[str, Any], key: str, default: Any = None) -> Any:
    return mapping.get(key, default) if isinstance(mapping, Mapping) else default


def _resource_name(event: Any) -> str:
    resource = getattr(event, "resource", {})
    return _get(resource, "name", "unknown")


LOGGER = logging.getLogger(__name__)


def on_flow_failed(event: Any) -> None:
    flow_name = _resource_name(event)
    message = _get(getattr(event, "payload", {}), "error", "Unknown failure")
    LOGGER.error("Flow failed: %s - %s", flow_name, message)
    andon_alert_flow(flow_name=flow_name, message=message, severity="critical")


def on_task_failed(event: Any) -> None:
    task_resource = getattr(event, "resource", {})
    flow_info = getattr(event, "related", {}).get("flow_run", {})
    task_name = _get(task_resource, "name", "task")
    flow_name = _get(flow_info, "name", "unknown-flow")
    message = _get(getattr(event, "payload", {}), "error", "Task failure")
    andon_alert_flow(flow_name=f"{flow_name}:{task_name}", message=message, severity="critical")


def on_flow_retry(event: Any) -> None:
    flow_name = _resource_name(event)
    retries = _get(getattr(event, "payload", {}), "run_count")
    if retries and retries > 2:
        andon_alert_flow(flow_name, f"Flow retried {retries} times", severity="warning")


def on_latency_exceeded(event: Any) -> None:
    flow_name = _resource_name(event)
    payload = getattr(event, "payload", {})
    duration = _get(payload, "duration_ms")
    threshold = _get(payload, "threshold_ms", 0)
    if duration:
        message = f"Performance alert: flow exceeded SLA ({duration}ms > {threshold}ms)"
        andon_alert_flow(flow_name, message, severity="warning")


def on_container_crash(event: Any) -> None:
    payload = getattr(event, "payload", {})
    service = _get(payload, "service", "unknown-service")
    reason = _get(payload, "reason", "unknown")
    andon_alert_flow(flow_name="infra_monitor", message=f"Container {service} crashed ({reason})", severity="critical")


def on_dbt_test_failed(flow_name: str, model: str, test_name: str, failure_message: str) -> None:
    message = f"dbt test `{test_name}` failed on `{model}`: {failure_message}"
    andon_alert_flow(flow_name=flow_name, message=message, severity="critical")


def on_llm_failure(flow_name: str, endpoint: str, message: str) -> None:
    andon_alert_flow(flow_name=flow_name, message=f"LangChain failure at {endpoint}: {message}", severity="critical")


def on_latency_warning(flow_name: str, duration_ms: int, threshold_ms: int) -> None:
    if duration_ms > threshold_ms:
        andon_alert_flow(flow_name, f"Latency {duration_ms}ms exceeded {threshold_ms}ms", severity="warning")


def on_container_restart(service_name: str, reason: str) -> None:
    andon_alert_flow("infra_monitor", f"Container `{service_name}` restarted ({reason})", severity="info")
