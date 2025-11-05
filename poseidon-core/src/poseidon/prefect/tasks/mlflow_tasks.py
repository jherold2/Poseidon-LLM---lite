"""MLflow integration tasks used across Prefect flows."""

from __future__ import annotations

from datetime import datetime

import mlflow
import pandas as pd
from prefect import get_run_logger, task

from poseidon.prefect.config import create_sqlalchemy_engine
from poseidon.prefect.tasks.kaizen_tasks import record_kaizen_event


@task(name="ingest-mlflow-runs", retries=2, retry_delay_seconds=45)
def ingest_mlflow_runs(table_name: str = "mlflow_runs", schema: str = "raw_events") -> int:
    """Persist MLflow run metadata into Postgres for Lean analytics."""
    logger = get_run_logger()
    runs = mlflow.search_runs()
    if runs.empty:
        logger.info("No MLflow runs found to ingest.")
        return 0

    df = runs[
        [
            "run_id",
            "experiment_id",
            "start_time",
            "end_time",
            "status",
            "params",
            "metrics",
            "tags",
            "artifact_uri",
            "user_id",
        ]
    ].rename(columns={"run_id": "run_uuid"})

    engine = create_sqlalchemy_engine()
    df.to_sql(table_name, con=engine, schema=schema, if_exists="append", index=False)
    logger.info("Ingested %s MLflow runs into %s.%s", len(df), schema, table_name)
    return len(df)


@task(name="mlflow-start-run")
def start_mlflow_run(
    experiment_name: str,
    run_name: str | None = None,
    parameters: dict[str, str] | None = None,
) -> str:
    """Start an MLflow run and log high-level parameters."""
    logger = get_run_logger()
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=run_name):
        params = parameters or {}
        for key, value in params.items():
            mlflow.log_param(key, value)
        mlflow.log_metric("run_timestamp", datetime.utcnow().timestamp())
        run_id = mlflow.active_run().info.run_id  # type: ignore[union-attr]
        logger.info("Started MLflow run %s in experiment %s", run_id, experiment_name)
    return run_id


@task(name="mlflow-log-metrics")
def log_mlflow_metrics(run_id: str, metrics: dict[str, float]) -> None:
    """Log a batch of metrics to an existing MLflow run."""
    logger = get_run_logger()
    if not metrics:
        logger.info("No metrics provided for MLflow run %s; skipping.", run_id)
        return

    with mlflow.start_run(run_id=run_id):
        for key, value in metrics.items():
            mlflow.log_metric(key, value)
    logger.info("Logged %d metrics to MLflow run %s", len(metrics), run_id)


@task(name="mlflow-complete-run")
def complete_mlflow_run(run_id: str, improvement_note: str | None = None) -> None:
    """Mark a run as successful and optionally record a Kaizen event."""
    logger = get_run_logger()
    with mlflow.start_run(run_id=run_id):
        mlflow.set_tag("status", "completed")
    logger.info("Completed MLflow run %s", run_id)
    if improvement_note:
        record_kaizen_event.fn(
            source="mlflow",
            description="Model retraining completed",
            impact=improvement_note,
        )
