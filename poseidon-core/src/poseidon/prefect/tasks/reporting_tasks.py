"""Reusable Prefect tasks for reporting flows."""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Sequence

from prefect import get_run_logger, task
from prefect.artifacts import create_table_artifact

from poseidon.utils.path_utils import repo_root

from poseidon.prefect.config import PostgresConfig, airflow_sql_path
from poseidon.prefect.tasks.dbt_tasks import run_dbt_command


@task(name="execute-sql-file", tags={"reporting", "sql"})
def execute_sql_file(sql_path: str, postgres_config: PostgresConfig) -> None:
    logger = get_run_logger()
    resolved = _resolve_sql_path(sql_path)
    logger.info("Executing SQL script %s", resolved)
    import psycopg2  # local import to keep dependency minimal

    conn = psycopg2.connect(
        host=postgres_config.host,
        port=postgres_config.port,
        database=postgres_config.database,
        user=postgres_config.user,
        password=postgres_config.password,
    )
    try:
        with resolved.open("r", encoding="utf-8") as handle:
            sql = handle.read()
        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()
    finally:
        conn.close()


@task(name="refresh-materialized-view", tags={"reporting", "sql"})
def refresh_materialized_view(target: str, postgres_config: PostgresConfig) -> None:
    safe_refresh_sql = f"""
    DO $$
    BEGIN
        BEGIN
            EXECUTE 'REFRESH MATERIALIZED VIEW CONCURRENTLY {target};';
        EXCEPTION
            WHEN feature_not_supported THEN
                EXECUTE 'REFRESH MATERIALIZED VIEW {target};';
        END;
    END $$;
    """
    logger = get_run_logger()
    logger.info("Refreshing materialized view %s", target)
    import psycopg2  # local import

    conn = psycopg2.connect(
        host=postgres_config.host,
        port=postgres_config.port,
        database=postgres_config.database,
        user=postgres_config.user,
        password=postgres_config.password,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(safe_refresh_sql)
        conn.commit()
    finally:
        conn.close()


@task(name="export-sharepoint-report", tags={"reporting", "sharepoint"})
def export_sharepoint_report() -> None:
    """Reuse the existing SharePoint upload utility."""
    logger = get_run_logger()
    module_path = repo_root() / "airflow-temp" / "upload_sharepoint_excel.py"
    namespace = runpy.run_path(str(module_path))
    func = namespace.get("export_and_upload_to_sharepoint")
    if not func:
        raise RuntimeError("export_and_upload_to_sharepoint not found in upload_sharepoint_excel.py")
    logger.info("Uploading production workbook to SharePoint")
    func()


@task(name="record-refresh-artifact", tags={"reporting", "artifact"})
def record_refresh_artifact(name: str, refreshed: Sequence[str]) -> None:
    """Publish a table artifact summarising refreshed objects."""
    if not refreshed:
        return
    table = [{"order": idx + 1, "resource": value} for idx, value in enumerate(refreshed)]
    create_table_artifact(
        key=f"{name}-refresh-summary",
        table=table,
        description=f"Summary of refreshed resources for {name}",
    )


def _resolve_sql_path(relative_sql: str) -> Path:
    return airflow_sql_path(relative_sql)
