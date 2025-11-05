"""Prefect flows for refreshing reporting marts."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Mapping, Sequence

from prefect import flow

from poseidon.prefect.config import (
    PostgresConfig,
    airflow_temp_root,
    load_accounting_materialized_views,
    load_production_materialized_views,
    load_sales_materialized_views,
)
from poseidon.prefect.tasks.observability_tasks import flow_run_guard
from poseidon.prefect.tasks.reporting_tasks import (
    execute_sql_file,
    export_sharepoint_report,
    record_refresh_artifact,
    refresh_materialized_view,
    run_dbt_command,
)


SALES_DEPENDENCIES: Mapping[str, Sequence[str]] = {
    "sale_order_line_uninvoiced_amounts_mv": ["sale_order_uninvoiced_mv"],
    "account_move_invoice_mv": ["res_partner_location_mv"],
    "account_move_line_basetable_staging_mv": [
        "account_move_invoice_mv",
        "account_move_line_amounts_mv",
        "product_pricelist_item_last_price_mv",
    ],
    "sale_order_line_basetable_staging_mv": [
        "res_partner_location_mv",
        "sale_order_invoiced_mv",
        "sale_order_uninvoiced_mv",
        "sale_order_line_invoiced_amounts_mv",
        "sale_order_line_uninvoiced_amounts_mv",
        "account_move_line_unordered_invoice_mv",
        "product_pricelist_item_last_price_mv",
    ],
    "fact_sales_mv": [
        "account_move_line_unordered_invoice_mv",
        "sale_order_line_basetable_staging_mv",
    ],
}

ACCOUNTING_DEPENDENCIES: Mapping[str, Sequence[str]] = {
    "fact_accounting_budget_mv": ["account_analytic_line_plan_long_mv", "fact_accounting_journal_mv"],
    "fact_accounting_journal_mv": ["account_analytic_line_plan_long_mv"],
}

PRODUCTION_DEPENDENCIES: Mapping[str, Sequence[str]] = {
    "fact_production_mv": [
        "production_target_mv",
        "fact_production_component_mv",
        "fact_scrap_mv",
        "rework_consumption_mv",
        "fact_workorder_mv",
    ],
    "agg_production_order_daily_mv": ["fact_production_mv"],
    "agg_production_order_component_daily_mv": ["agg_production_order_daily_mv"],
    "agg_production_item_daily_mv": ["agg_production_order_daily_mv"],
}


def _refresh_manifest(
    manifest: Sequence[Dict[str, str]],
    dependencies: Mapping[str, Sequence[str]],
    selected_views: Sequence[str] | None,
    postgres_config: PostgresConfig,
) -> List[str]:
    manifest_map = {entry["name"]: entry for entry in manifest}
    requested = list(selected_views or manifest_map.keys())
    visited: List[str] = []

    def _process(name: str) -> None:
        if name in visited:
            return
        entry = manifest_map.get(name)
        if entry is None:
            return
        for dep in dependencies.get(name, []):
            if dep in requested:
                _process(dep)
        execute_sql_file(sql_path=entry["create_sql"], postgres_config=postgres_config)
        refresh_materialized_view(target=entry["refresh_sql"], postgres_config=postgres_config)
        visited.append(name)

    for name in requested:
        _process(name)
    return visited


@flow(
    name="refresh-sales-reporting",
    flow_run_name="refresh-sales-{parameters[view_names]}",
    log_prints=True,
    persist_result=True,
    timeout_seconds=None,
    retries=0,
)
def refresh_sales_reporting_flow(view_names: Sequence[str] | None = None) -> List[str]:
    manifest = load_sales_materialized_views()
    pg_config = PostgresConfig.from_env()
    payload = {"views": list(view_names) if view_names else [entry["name"] for entry in manifest]}

    with flow_run_guard("refresh-sales-reporting", payload=payload) as guard:
        refreshed = _refresh_manifest(manifest, SALES_DEPENDENCIES, view_names, pg_config)
        summary = {"refreshed": refreshed, "completed_at": datetime.utcnow().isoformat()}
        guard.mark_completed(summary)
        record_refresh_artifact(name="sales-reporting", refreshed=refreshed)
        return refreshed


@flow(
    name="refresh-accounting-reporting",
    flow_run_name="refresh-accounting-{parameters[view_names]}",
    log_prints=True,
    persist_result=True,
)
def refresh_accounting_reporting_flow(view_names: Sequence[str] | None = None) -> List[str]:
    manifest = load_accounting_materialized_views()
    pg_config = PostgresConfig.from_env()
    payload = {"views": list(view_names) if view_names else [entry["name"] for entry in manifest]}

    with flow_run_guard("refresh-accounting-reporting", payload=payload) as guard:
        refreshed = _refresh_manifest(manifest, ACCOUNTING_DEPENDENCIES, view_names, pg_config)
        summary = {"refreshed": refreshed, "completed_at": datetime.utcnow().isoformat()}
        guard.mark_completed(summary)
        record_refresh_artifact(name="accounting-reporting", refreshed=refreshed)
        return refreshed


@flow(
    name="refresh-production-reporting",
    flow_run_name="refresh-production-{parameters[view_names]}",
    log_prints=True,
    persist_result=True,
)
def refresh_production_reporting_flow(
    view_names: Sequence[str] | None = None,
    upload_sharepoint: bool = True,
    run_dbt: bool = False,
) -> List[str]:
    manifest = load_production_materialized_views()
    pg_config = PostgresConfig.from_env()
    payload = {
        "views": list(view_names) if view_names else [entry["name"] for entry in manifest],
        "upload_sharepoint": upload_sharepoint,
        "run_dbt": run_dbt,
    }

    refreshed: List[str] = []
    with flow_run_guard("refresh-production-reporting", payload=payload) as guard:
        refreshed = _refresh_manifest(manifest, PRODUCTION_DEPENDENCIES, view_names, pg_config)
        if upload_sharepoint:
            export_sharepoint_report()
            refreshed.append("sharepoint_upload")
        if run_dbt:
            project_dir = airflow_temp_root().parent / "poseidon-cda" / "dbt"
            run_dbt_command(["dbt", "deps"], project_dir)
            run_dbt_command(["dbt", "build"], project_dir)
            refreshed.append("dbt_build")
        summary = {
            "refreshed": refreshed,
            "upload_sharepoint": upload_sharepoint,
            "run_dbt": run_dbt,
            "completed_at": datetime.utcnow().isoformat(),
        }
        guard.mark_completed(summary)
        record_refresh_artifact(name="production-reporting", refreshed=refreshed)
    return refreshed
