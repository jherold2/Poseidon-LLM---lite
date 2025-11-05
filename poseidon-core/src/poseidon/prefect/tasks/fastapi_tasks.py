"""FastAPI log ingestion tasks."""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import requests
from prefect import get_run_logger, task

from poseidon.prefect.config import create_sqlalchemy_engine


@task(name="ingest-fastapi-logs", retries=2, retry_delay_seconds=30)
def ingest_fastapi_logs(
    endpoint: Optional[str] = None,
    table_name: str = "fastapi_logs",
    schema: str = "raw_events",
) -> int:
    """
    Fetch structured FastAPI logs and store them in Postgres.

    Parameters
    ----------
    endpoint:
        Optional override for the log export endpoint. Defaults to the FASTAPI_LOG_EXPORT_URL env var.
    table_name:
        Target table within the destination schema.
    schema:
        Target schema for persisted logs.
    """
    logger = get_run_logger()
    url = endpoint or os.getenv("FASTAPI_LOG_EXPORT_URL", "http://fastapi.internal/logs/export")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    logs = response.json()
    if not logs:
        logger.info("FastAPI log endpoint %s returned no records.", url)
        return 0

    df = pd.DataFrame(logs)
    engine = create_sqlalchemy_engine()
    df.to_sql(table_name, con=engine, schema=schema, if_exists="append", index=False)
    logger.info("Ingested %s FastAPI log rows into %s.%s", len(df), schema, table_name)
    return len(df)
