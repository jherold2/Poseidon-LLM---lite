"""Lean ingestion Prefect flow wiring together telemetry sources."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from prefect import flow, get_run_logger

from poseidon.prefect.config import airflow_temp_root
from poseidon.prefect.tasks.dbt_tasks import ingest_dbt_run_results
from poseidon.prefect.tasks.fastapi_tasks import ingest_fastapi_logs
from poseidon.prefect.tasks.lean_metrics_tasks import build_lean_metrics_models
from poseidon.prefect.tasks.langfuse_tasks import ingest_langfuse_events
from poseidon.prefect.tasks.mlflow_tasks import ingest_mlflow_runs
from poseidon.prefect.tasks.observability_tasks import ingest_observability_events
from poseidon.prefect.tasks.prefect_tasks import ingest_prefect_runs


@flow(name="Lean Ingestion Flow", log_prints=True, persist_result=True)
def lean_ingestion_flow(
    run_dbt: bool = True,
    dbt_selectors: Sequence[str] = ("event_log_unified", "lean_metrics"),
    prefect_limit: int = 1000,
) -> dict[str, int | bool]:
    """Ingest heterogeneous telemetry into Postgres and optionally refresh Lean dbt models."""
    logger = get_run_logger()
    summary: dict[str, int | bool] = {}

    prefect_future = ingest_prefect_runs.submit(api_limit=prefect_limit)
    langfuse_future = ingest_langfuse_events.submit(
        host="https://cdaseafood.ddns.net/langfuse",
        project_id="poseidon",
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
    )
    mlflow_future = ingest_mlflow_runs.submit()
    dbt_future = ingest_dbt_run_results.submit()
    fastapi_future = ingest_fastapi_logs.submit()
    obs_future = ingest_observability_events.submit()

    summary["prefect_runs"] = prefect_future.result()
    summary["langfuse_events"] = langfuse_future.result()
    summary["mlflow_runs"] = mlflow_future.result()
    summary["dbt_results"] = dbt_future.result()
    summary["fastapi_logs"] = fastapi_future.result()
    summary["observability_events"] = obs_future.result()

    if run_dbt:
        project_dir = airflow_temp_root().parent / "poseidon-cda" / "dbt" / "analytics" / "cedea_metrics"
        build_future = build_lean_metrics_models.submit(project_dir=project_dir, selectors=dbt_selectors)
        build_future.result()
        summary["lean_models_built"] = True
        logger.info("Lean dbt models refreshed at %s", project_dir)
    else:
        summary["lean_models_built"] = False

    logger.info("Lean ingestion summary: %s", summary)
    return summary


__all__ = ["lean_ingestion_flow"]
