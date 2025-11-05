"""Prefect flow orchestrating a Langfuse trace lifecycle."""

from __future__ import annotations

from typing import Mapping

from prefect import flow, get_run_logger

from poseidon.prefect.tasks.langfuse_tasks import (
    create_langfuse_trace,
    ingest_langfuse_events,
    log_langfuse_metric,
)


@flow(name="Langfuse Trace Flow", log_prints=True)
def langfuse_trace_flow(
    host: str,
    project_id: str,
    public_key: str,
    secret_key: str,
    trace_name: str,
    metrics: Mapping[str, float] | None = None,
    metadata: Mapping[str, object] | None = None,
) -> str:
    """
    Execute a Langfuse trace lifecycle: create trace, log metrics, optionally ingest events.
    """

    logger = get_run_logger()
    trace_id = create_langfuse_trace(
        host=host,
        project_id=project_id,
        public_key=public_key,
        secret_key=secret_key,
        name=trace_name,
        metadata=dict(metadata or {}),
    )
    logger.info("Started Langfuse trace %s", trace_id)

    for metric_name, metric_value in (metrics or {}).items():
        log_langfuse_metric(
            host=host,
            project_id=project_id,
            public_key=public_key,
            secret_key=secret_key,
            trace_id=trace_id,
            metric_name=metric_name,
            metric_value=metric_value,
        )

    ingest_langfuse_events(
        host=host,
        project_id=project_id,
        public_key=public_key,
        secret_key=secret_key,
    )
    logger.info("Langfuse trace flow completed for %s", trace_id)
    return trace_id


__all__ = ["langfuse_trace_flow"]
