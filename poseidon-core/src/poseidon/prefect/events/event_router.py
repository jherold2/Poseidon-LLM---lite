"""Central router for Prefect event stream dispatch."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict
from prefect.client.orchestration import get_client
from prefect.events import Event

from poseidon.prefect.events.andon_event_handlers import (
    on_container_crash,
    on_flow_failed,
    on_flow_retry,
    on_latency_exceeded,
    on_task_failed,
)
from poseidon.prefect.events.api_event_handlers import on_api_error, on_latency_warning
from poseidon.prefect.events.dbt_event_handlers import on_dbt_test_failure
from poseidon.prefect.events.infra_event_handlers import (
    on_agent_disconnected,
    on_container_restart_event,
    on_disk_space_low,
    on_memory_pressure,
)
from poseidon.prefect.events.kaizen_event_handlers import on_flow_optimized, on_metric_improved
from poseidon.prefect.events.model_event_handlers import (
    on_model_drift,
    on_model_registry_update,
    on_model_retrained,
)
from poseidon.prefect.events.security_event_handlers import on_permission_denied, on_token_expired, on_unauthorized_access


EVENT_CATEGORY_MAP: Dict[str, Callable[[Any], None]] = {
    "prefect.flow-run.failed": on_flow_failed,
    "prefect.task-run.failed": on_task_failed,
    "prefect.flow-run.retrying": on_flow_retry,
    "prefect.flow-run.slow": on_latency_exceeded,
    "prefect.agent.disconnected": lambda event: on_agent_disconnected(event.payload.get("agent", "unknown")),
    "infra.disk.low": lambda event: on_disk_space_low(event.payload.get("host", "unknown"), event.payload.get("usage", 0)),
    "infra.memory.high": lambda event: on_memory_pressure(event.payload.get("host", "unknown"), event.payload.get("usage", 0)),
    "infra.container.restart": lambda event: on_container_restart_event(event.payload.get("service", "unknown"), event.payload.get("reason", "unknown")),
    "infra.container.crashed": on_container_crash,
    "api.error": lambda event: on_api_error(
        event.payload.get("flow", "api"),
        event.payload.get("endpoint", "unknown"),
        int(event.payload.get("status", 500)),
        event.payload.get("message", "error"),
    ),
    "api.latency": lambda event: on_latency_warning(
        event.payload.get("flow", "api"),
        event.payload.get("endpoint", "unknown"),
        int(event.payload.get("duration_ms", 0)),
        int(event.payload.get("threshold_ms", 0)),
    ),
    "security.unauthorized": lambda event: on_unauthorized_access(
        event.payload.get("flow", "security"),
        event.payload.get("user", "unknown"),
        event.payload.get("endpoint", "unknown"),
    ),
    "security.permission.denied": lambda event: on_permission_denied(
        event.payload.get("user", "unknown"), event.payload.get("resource", "unknown")
    ),
    "security.token.expired": lambda event: on_token_expired(event.payload.get("service", "unknown")),
    "dbt.test.failed": lambda event: on_dbt_test_failure(
        event.payload.get("model", "unknown"),
        event.payload.get("test", "unknown"),
        event.payload.get("message", "dbt test failed"),
    ),
    "langfuse.trace.drift": lambda event: on_model_drift(
        event.payload.get("model", "unknown"),
        event.payload.get("metric", "metric"),
        float(event.payload.get("drop_percent", 0.0)),
    ),
    "langfuse.trace.retrained": lambda event: on_model_retrained(
        event.payload.get("model", "unknown"), event.payload.get("improvement")
    ),
    "langfuse.registry.updated": lambda event: on_model_registry_update(
        event.payload.get("model", "unknown"), event.payload.get("version", "unknown")
    ),
    "mlflow.model.drift": lambda event: on_model_drift(
        event.payload.get("model", "unknown"),
        event.payload.get("metric", "metric"),
        float(event.payload.get("drop_percent", 0.0)),
    ),
    "mlflow.model.retrained": lambda event: on_model_retrained(
        event.payload.get("model", "unknown"), event.payload.get("improvement")
    ),
    "mlflow.registry.updated": lambda event: on_model_registry_update(
        event.payload.get("model", "unknown"), event.payload.get("version", "unknown")
    ),
    "kaizen.flow.optimized": lambda event: on_flow_optimized(
        event.payload.get("flow", "unknown"),
        float(event.payload.get("before", 0)),
        float(event.payload.get("after", 0)),
    ),
    "kaizen.metric.improved": lambda event: on_metric_improved(
        event.payload.get("metric", "unknown"),
        float(event.payload.get("before", 0)),
        float(event.payload.get("after", 0)),
    ),
}
LOGGER = logging.getLogger(__name__)


def route_event(event: Event) -> None:
    """Dispatch an incoming Prefect event to the registered handler if any."""
    handler = EVENT_CATEGORY_MAP.get(event.event)
    if not handler:
        LOGGER.debug("No handler registered for event %s", event.event)
        return

    try:
        handler(event)
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.error("Failed to handle event %s: %s", event.event, exc)


def listen_to_prefect_events() -> None:
    """Stream Prefect events and route them continuously until cancelled."""

    async def _listen() -> None:
        async with get_client() as client:
            async with client.events.stream("*") as stream:
                LOGGER.info("Listening for Prefect events...")
                async for event in stream:  # pragma: no cover - long-running listener
                    route_event(event)

    asyncio.run(_listen())
