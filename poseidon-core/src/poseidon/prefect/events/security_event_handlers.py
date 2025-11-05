"""Security-focused event handlers."""

from __future__ import annotations

from poseidon.prefect.flows.andon_alert_flow import andon_alert_flow


def on_unauthorized_access(flow_name: str, user: str, endpoint: str) -> None:
    msg = f"Unauthorized access attempt by `{user}` to `{endpoint}`"
    andon_alert_flow(flow_name, msg, severity="critical")


def on_token_expired(service: str) -> None:
    andon_alert_flow(service, f"Access token expired for `{service}`", severity="warning")


def on_permission_denied(user: str, resource: str) -> None:
    andon_alert_flow("security_monitor", f"Permission denied: `{user}` on `{resource}`", severity="warning")
