"""Prefect flow orchestrating dbt builds and tests."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from prefect import flow, get_run_logger

from poseidon.prefect.config import airflow_temp_root
from poseidon.prefect.tasks.dbt_tasks import run_dbt_command


def _project_root() -> Path:
    return airflow_temp_root().parent / "poseidon-cda" / "dbt"


@flow(name="dbt Build Flow", log_prints=True)
def dbt_build_flow(
    selectors: Sequence[str] | None = None,
    run_tests: bool = True,
) -> dict:
    """
    Execute dbt commands across the semantic layer project.

    Parameters
    ----------
    selectors:
        Optional iterable of selectors to pass to dbt run/test. Defaults to all models.
    run_tests:
        Whether to invoke ``dbt test`` after ``dbt run``.
    """
    logger = get_run_logger()
    project_dir = _project_root()
    selectors = list(selectors or [])

    logger.info("Running dbt deps in %s", project_dir)
    run_dbt_command(command=("dbt", "deps"), project_dir=project_dir)

    run_args = ["dbt", "run"]
    if selectors:
        run_args.extend(["--select", " ".join(selectors)])
    logger.info("Executing %s", " ".join(run_args))
    run_dbt_command(command=tuple(run_args), project_dir=project_dir)

    if run_tests:
        test_args = ["dbt", "test"]
        if selectors:
            test_args.extend(["--select", " ".join(selectors)])
        logger.info("Executing %s", " ".join(test_args))
        run_dbt_command(command=tuple(test_args), project_dir=project_dir)

    summary = {
        "project_dir": str(project_dir),
        "selectors": selectors,
        "tests_ran": run_tests,
    }
    logger.info("dbt build flow complete: %s", summary)
    return summary


__all__ = ["dbt_build_flow"]
