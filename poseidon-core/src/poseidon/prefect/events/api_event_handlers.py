"""API and service layer event handlers."""

from __future__ import annotations

from poseidon.prefect.flows.andon_alert_flow import andon_alert_flow


def on_api_error(flow_name: str, endpoint: str, status_code: int, message: str) -> None:
    severity = "critical" if status_code >= 500 else "warning"
    payload = f"API `{endpoint}` returned {status_code}: {message}"
    andon_alert_flow(flow_name, payload, severity)


def on_latency_warning(flow_name: str, endpoint: str, duration_ms: int, threshold_ms: int) -> None:
    if duration_ms > threshold_ms:
        msg = f"High latency on `{endpoint}` ({duration_ms}ms > {threshold_ms}ms)"
        andon_alert_flow(flow_name, msg, severity="warning")
