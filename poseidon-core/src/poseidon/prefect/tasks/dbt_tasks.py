"""dbt-oriented Prefect tasks shared across flows."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Mapping, Sequence

import pandas as pd
from prefect import get_run_logger, task

from prefect_dbt.cli.commands import DbtCoreOperation

from poseidon.prefect.config import create_sqlalchemy_engine


@task(name="run-dbt-command", tags={"reporting", "dbt"})
def run_dbt_command(command: Sequence[str], project_dir: Path, env: Mapping[str, str] | None = None) -> None:
    """Execute a dbt CLI command with optional environment overrides."""
    logger = get_run_logger()
    logger.info("Running dbt command: %s", " ".join(command))
    full_env: Dict[str, str] = dict(os.environ)
    if env:
        full_env.update(env)
    completed = subprocess.run(
        list(command),
        cwd=project_dir,
        env=full_env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.stdout:
        logger.info("dbt stdout:\n%s", completed.stdout)
    if completed.stderr:
        logger.warning("dbt stderr:\n%s", completed.stderr)
    if completed.returncode != 0:
        raise RuntimeError(f"dbt command {' '.join(command)} failed with exit code {completed.returncode}")


@task(name="ingest-dbt-run-results", retries=1)
def ingest_dbt_run_results(
    result_path: Path | str = "./target/run_results.json",
    table_name: str = "dbt_run_results",
    schema: str = "raw_events",
) -> int:
    """Persist dbt run results JSON into Postgres."""
    logger = get_run_logger()
    path = Path(result_path)
    if not path.exists():
        logger.warning("dbt run results file %s not found; skipping ingestion.", path)
        return 0

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    results = payload.get("results", [])
    if not results:
        logger.info("dbt run results file %s contained no result entries.", path)
        return 0

    df = pd.json_normalize(results)
    engine = create_sqlalchemy_engine()
    df.to_sql(table_name, con=engine, schema=schema, if_exists="append", index=False)
    logger.info("Ingested %s dbt result rows into %s.%s", len(df), schema, table_name)
    return len(df)


@task(name="run-dbt-models", retries=2, retry_delay_seconds=30)
def run_dbt_models(select: str = "marts+") -> dict:
    """Execute dbt run using prefect-dbt for the requested selector."""
    logger = get_run_logger()
    project_dir = Path(__file__).resolve().parents[6] / "poseidon-cda" / "dbt" / "analytics" / "cedea_metrics"
    logger.info("Running dbt models with selector '%s' in %s", select, project_dir)
    operation = DbtCoreOperation(
        commands=[f"run --select {select}"],
        project_dir=str(project_dir),
    )
    result = operation.run()
    logger.info("dbt run completed with result: %s", result)
    return result
