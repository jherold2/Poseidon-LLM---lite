"""Deployment helpers for Poseidon's Prefect flows."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from prefect.client.schemas.schedules import CronSchedule
from prefect.filesystems import LocalFileSystem

from poseidon.prefect.flows.reporting_flows import (
    refresh_accounting_reporting_flow,
    refresh_production_reporting_flow,
    refresh_sales_reporting_flow,
)


async def _apply_async(work_pool_name: str, repo_path: Path, storage_block_name: str) -> None:
    """
    Build (or overwrite) a LocalFileSystem storage block pointing at the given repo path,
    then deploy all three reporting flows against the requested work pool.
    """
    storage_block_id = await LocalFileSystem(basepath=str(repo_path)).save(storage_block_name, overwrite=True)

    sales = await refresh_sales_reporting_flow.deploy(
        name="sales-refresh-hourly",
        work_pool_name=work_pool_name,
        parameters={"view_names": None},
        schedule=CronSchedule(cron="0 * * * *", timezone="UTC"),
        tags=["reporting", "sales"],
        entrypoint="poseidon-core/src/poseidon/prefect/flows/reporting_flows.py:refresh_sales_reporting_flow",
        storage_document_id=storage_block_id,
    )
    await sales.apply()

    accounting = await refresh_accounting_reporting_flow.deploy(
        name="accounting-refresh-daily",
        work_pool_name=work_pool_name,
        parameters={"view_names": None},
        schedule=CronSchedule(cron="30 2 * * *", timezone="UTC"),
        tags=["reporting", "accounting"],
        entrypoint="poseidon-core/src/poseidon/prefect/flows/reporting_flows.py:refresh_accounting_reporting_flow",
        storage_document_id=storage_block_id,
    )
    await accounting.apply()

    production = await refresh_production_reporting_flow.deploy(
        name="production-refresh-quarter-hourly",
        work_pool_name=work_pool_name,
        parameters={"view_names": None, "upload_sharepoint": True, "run_dbt": False},
        schedule=CronSchedule(cron="*/15 * * * *", timezone="UTC"),
        tags=["reporting", "production"],
        entrypoint="poseidon-core/src/poseidon/prefect/flows/reporting_flows.py:refresh_production_reporting_flow",
        storage_document_id=storage_block_id,
    )
    await production.apply()


def apply_all_deployments(
    *,
    work_pool_name: str = "default",
    repo_path: Path | None = None,
    storage_block_name: str = "poseidon-local-storage",
) -> None:
    """
    Create/update Prefect deployments for the reporting flows.

    Parameters
    ----------
    work_pool_name:
        Prefect work-pool to target (must already exist in your Prefect API).
    repo_path:
        Filesystem path to the Poseidon checkout. Defaults to the repo root.
    storage_block_name:
        Name used when saving the LocalFileSystem storage block.
    """
    if repo_path is None:
        repo_path = Path(__file__).resolve().parents[1]

    asyncio.run(_apply_async(work_pool_name=work_pool_name, repo_path=repo_path, storage_block_name=storage_block_name))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply Prefect deployments for reporting flows.")
    parser.add_argument(
        "--work-pool",
        default="default",
        help="Name of the Prefect work pool to target (must already exist). Default: %(default)s",
    )
    parser.add_argument(
        "--base-path",
        default=None,
        help="Path to the Poseidon repo to use for LocalFileSystem storage. Defaults to the repository root.",
    )
    parser.add_argument(
        "--storage-block-name",
        default="poseidon-local-storage",
        help="Name for the LocalFileSystem storage block (will be created/overwritten).",
    )
    args = parser.parse_args()

    base_path = Path(args.base_path).resolve() if args.base_path else None
    apply_all_deployments(
        work_pool_name=args.work_pool,
        repo_path=base_path,
        storage_block_name=args.storage_block_name,
    )
