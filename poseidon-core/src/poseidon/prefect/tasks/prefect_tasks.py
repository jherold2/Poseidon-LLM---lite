"""Prefect API integration tasks for telemetry ingestion."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
from prefect import get_run_logger, task
from prefect.tasks import task_input_hash

from poseidon.prefect.config import create_sqlalchemy_engine


@task(
    name="ingest-prefect-runs",
    retries=2,
    retry_delay_seconds=30,
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(hours=1),
)
async def ingest_prefect_runs(api_limit: int = 1000, table_name: str = "prefect_runs", schema: str = "raw_events") -> int:
    """Pull recent Prefect flow runs and upsert them into Postgres."""
    logger = get_run_logger()
    from prefect.client.orchestration import get_client  # local import for optional dependency

    async with get_client() as client:
        runs = await client.read_flow_runs(limit=api_limit)
    if not runs:
        logger.info("No Prefect runs returned; nothing to ingest.")
        return 0

    records = []
    for run in runs:
        data = run.dict()
        metadata = data.get("parameters") or {}
        run_time = data.get("total_run_time")
        if hasattr(run_time, "total_seconds"):
            duration_ms = int(run_time.total_seconds() * 1000)
        elif isinstance(run_time, (int, float)):
            duration_ms = int(run_time * 1000)
        else:
            duration_ms = None
        agent_name = (
            data.get("worker_name")
            or data.get("work_pool_name")
            or data.get("work_queue_name")
        )
        records.append(
            {
                "id": data.get("id"),
                "flow_id": data.get("flow_id"),
                "name": data.get("name"),
                "started_at": data.get("start_time"),
                "ended_at": data.get("end_time"),
                "state": data.get("state_type"),
                "duration_ms": duration_ms,
                "metadata": metadata,
                "agent": agent_name,
            }
        )

    df = pd.DataFrame(records)
    if df.empty:
        logger.info("Prefect API returned %s runs but no parsable records.", len(runs))
        return 0

    engine = create_sqlalchemy_engine()
    df.to_sql(table_name, con=engine, schema=schema, if_exists="append", index=False)
    logger.info("Ingested %s Prefect runs into %s.%s", len(df), schema, table_name)
    return len(df)
