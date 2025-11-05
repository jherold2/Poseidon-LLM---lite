"""Langfuse integration tasks used across Prefect flows."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pandas as pd
import requests
from prefect import get_run_logger, task

from poseidon.prefect.config import create_sqlalchemy_engine


def _langfuse_headers(public_key: str, secret_key: str) -> dict[str, str]:
    return {
        "X-Langfuse-Public-Key": public_key,
        "X-Langfuse-Secret-Key": secret_key,
        "Content-Type": "application/json",
    }


@task(name="ingest-langfuse-events", retries=2, retry_delay_seconds=45)
def ingest_langfuse_events(
    host: str,
    project_id: str,
    public_key: str,
    secret_key: str,
    table_name: str = "langfuse_events",
    schema: str = "raw_events",
) -> int:
    """Persist Langfuse trace metadata into Postgres for Lean analytics."""
    logger = get_run_logger()
    url = f"{host.rstrip('/')}/api/public/traces?projectId={project_id}"
    response = requests.get(url, headers=_langfuse_headers(public_key, secret_key), timeout=10)
    response.raise_for_status()
    traces = response.json().get("data", [])
    if not traces:
        logger.info("No Langfuse traces found to ingest.")
        return 0

    df = pd.DataFrame(
        [
            {
                "trace_id": trace.get("id"),
                "name": trace.get("name"),
                "status": trace.get("status"),
                "timestamp": trace.get("timestamp"),
                "metadata": trace.get("metadata"),
            }
            for trace in traces
        ]
    )
    engine = create_sqlalchemy_engine()
    df.to_sql(table_name, con=engine, schema=schema, if_exists="append", index=False)
    logger.info("Ingested %s Langfuse traces into %s.%s", len(df), schema, table_name)
    return len(df)


@task(name="langfuse-create-trace")
def create_langfuse_trace(
    host: str,
    project_id: str,
    public_key: str,
    secret_key: str,
    name: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Create a Langfuse trace for downstream logging."""
    logger = get_run_logger()
    body = {
        "projectId": project_id,
        "name": name,
        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        "metadata": metadata or {},
    }
    response = requests.post(
        f"{host.rstrip('/')}/api/public/traces",
        headers=_langfuse_headers(public_key, secret_key),
        json=body,
        timeout=10,
    )
    response.raise_for_status()
    trace_id = response.json()["id"]
    logger.info("Created Langfuse trace %s (%s)", trace_id, name)
    return trace_id


@task(name="langfuse-log-metric")
def log_langfuse_metric(
    host: str,
    project_id: str,
    public_key: str,
    secret_key: str,
    trace_id: str,
    metric_name: str,
    metric_value: float,
) -> None:
    """Attach a numeric metric to an existing Langfuse trace."""
    logger = get_run_logger()
    body = {
        "projectId": project_id,
        "traceId": trace_id,
        "name": metric_name,
        "value": metric_value,
        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
    }
    response = requests.post(
        f"{host.rstrip('/')}/api/public/metrics",
        headers=_langfuse_headers(public_key, secret_key),
        json=body,
        timeout=10,
    )
    response.raise_for_status()
    logger.info("Logged metric %s=%s to Langfuse trace %s", metric_name, metric_value, trace_id)
