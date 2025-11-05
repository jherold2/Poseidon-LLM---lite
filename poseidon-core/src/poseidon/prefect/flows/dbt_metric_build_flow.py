"""Prefect flow that triggers dbt metric builds via prefect-dbt."""

from __future__ import annotations

from prefect import flow, get_run_logger

from poseidon.prefect.tasks.dbt_tasks import run_dbt_models


@flow(name="dbt Metric Build Flow", log_prints=True)
def dbt_metric_build_flow(select: str = "marts+") -> dict:
    """Run dbt models for the requested selector using prefect-dbt integration."""
    logger = get_run_logger()
    result = run_dbt_models(select=select)
    logger.info("dbt metric build finished")
    return result


__all__ = ["dbt_metric_build_flow"]
