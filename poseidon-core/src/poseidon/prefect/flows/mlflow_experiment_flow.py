"""Prefect flow orchestrating an MLflow experiment cycle."""

from __future__ import annotations

from typing import Mapping

from prefect import flow, get_run_logger

from poseidon.prefect.tasks.mlflow_tasks import (
    complete_mlflow_run,
    log_mlflow_metrics,
    start_mlflow_run,
)


@flow(name="MLflow Experiment Flow", log_prints=True)
def mlflow_experiment_flow(
    experiment_name: str,
    run_name: str | None = None,
    parameters: Mapping[str, str] | None = None,
    metrics: Mapping[str, float] | None = None,
    improvement_note: str | None = None,
) -> str:
    """
    Execute a lightweight MLflow experiment lifecycle: start run, log metrics, close run.

    Parameters
    ----------
    experiment_name:
        Name of the MLflow experiment to target.
    run_name:
        Optional friendly alias for the run.
    parameters:
        Parameters to log at the start of the run.
    metrics:
        Metrics to log after the run completes.
    improvement_note:
        Optional comment persisted as a Kaizen entry.
    """

    logger = get_run_logger()
    run_id = start_mlflow_run(
        experiment_name=experiment_name,
        run_name=run_name,
        parameters=dict(parameters or {}),
    )
    logger.info("Started MLflow run %s", run_id)

    if metrics:
        log_mlflow_metrics(run_id=run_id, metrics=dict(metrics))

    complete_mlflow_run(run_id=run_id, improvement_note=improvement_note)
    logger.info("MLflow experiment flow completed for run %s", run_id)
    return run_id


__all__ = ["mlflow_experiment_flow"]
