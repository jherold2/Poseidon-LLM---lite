"""Lean metric orchestration helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from prefect import get_run_logger, task

from poseidon.prefect.tasks.dbt_tasks import run_dbt_command


@task(name="build-lean-metrics", retries=1)
def build_lean_metrics_models(project_dir: Path, selectors: Sequence[str] = ("event_log_unified", "lean_metrics")) -> None:
    """Run dbt commands to refresh the Lean observability mart."""
    logger = get_run_logger()
    futures = []
    for selector in selectors:
        task_runner = run_dbt_command.with_options(name=f"dbt-build-{selector}")  # type: ignore[attr-defined]
        future = task_runner.submit(
            command=("dbt", "run", "--select", selector),
            project_dir=project_dir,
        )
        futures.append(future)
        logger.info("Triggered dbt build for selector '%s'", selector)
    for future in futures:
        future.result()
