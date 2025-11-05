"""Deployment helpers for Poseidon's Prefect work streams."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Optional

from prefect.client.schemas.schedules import CronSchedule
from prefect.filesystems import LocalFileSystem

from poseidon.prefect.flows import (
    agent_inference_flow,
    andon_alert_flow,
    dbt_build_flow,
    dbt_metric_build_flow,
    hansei_weekly_report_flow,
    langfuse_trace_flow,
    lean_ingestion_flow,
    mlflow_experiment_flow,
    mcp_metadata_refresh_flow,
    observability_monitor_flow,
    orchestration_flow,
)


def _deployment_specs(repo_path: Path) -> list[dict[str, Any]]:
    return [
        {
            "flow": lean_ingestion_flow,
            "name": "lean-ingestion-stream",
            "work_queue_name": "ingestion-queue",
            "schedule": CronSchedule(cron="*/15 * * * *", timezone="UTC"),
            "parameters": {"run_dbt": True, "dbt_selectors": ["event_log_unified", "lean_metrics"]},
            "entrypoint": "poseidon-core/src/poseidon/prefect/flows/ingestion_flow.py:lean_ingestion_flow",
        },
        {
            "flow": dbt_build_flow,
            "name": "dbt-build-stream",
            "work_queue_name": "dbt-queue",
            "schedule": CronSchedule(cron="0 * * * *", timezone="UTC"),
            "parameters": {"selectors": [], "run_tests": True},
            "entrypoint": "poseidon-core/src/poseidon/prefect/flows/dbt_build_flow.py:dbt_build_flow",
        },
        {
            "flow": dbt_metric_build_flow,
            "name": "dbt-metric-build-stream",
            "work_queue_name": "dbt-queue",
            "schedule": None,
            "parameters": {"select": "marts+"},
            "entrypoint": "poseidon-core/src/poseidon/prefect/flows/dbt_metric_build_flow.py:dbt_metric_build_flow",
        },
        {
            "flow": mlflow_experiment_flow,
            "name": "mlflow-experiment-stream",
            "work_queue_name": "mlflow-queue",
            "schedule": None,
            "parameters": {
                "experiment_name": "poseidon-default",
                "run_name": None,
                "parameters": {},
                "metrics": {},
                "improvement_note": None,
            },
            "entrypoint": "poseidon-core/src/poseidon/prefect/flows/mlflow_experiment_flow.py:mlflow_experiment_flow",
        },
        {
            "flow": langfuse_trace_flow,
            "name": "langfuse-trace-stream",
            "work_queue_name": "langfuse-queue",
            "schedule": None,
            "parameters": {
                "host": "https://cdaseafood.ddns.net/langfuse",
                "project_id": "poseidon",
                "public_key": os.getenv("LANGFUSE_PUBLIC_KEY", ""),
                "secret_key": os.getenv("LANGFUSE_SECRET_KEY", ""),
                "trace_name": "poseidon-default",
                "metrics": {},
            },
            "entrypoint": "poseidon-core/src/poseidon/prefect/flows/langfuse_trace_flow.py:langfuse_trace_flow",
        },
        {
            "flow": agent_inference_flow,
            "name": "agent-inference-stream",
            "work_queue_name": "agent-queue",
            "schedule": None,
            "parameters": {"agent_name": "sales", "prompt": "Provide the latest KPI summary."},
            "entrypoint": "poseidon-core/src/poseidon/prefect/flows/agent_inference_flow.py:agent_inference_flow",
        },
        {
            "flow": observability_monitor_flow,
            "name": "observability-monitor-stream",
            "work_queue_name": "observability-queue",
            "schedule": CronSchedule(cron="*/5 * * * *", timezone="UTC"),
            "parameters": {"window_minutes": 15},
            "entrypoint": "poseidon-core/src/poseidon/prefect/flows/observability_monitor_flow.py:observability_monitor_flow",
        },
        {
            "flow": hansei_weekly_report_flow,
            "name": "hansei-weekly-review-stream",
            "work_queue_name": "weekly-review-queue",
            "schedule": CronSchedule(cron="0 8 * * MON", timezone="UTC"),
            "parameters": {"days_back": 7},
            "entrypoint": "poseidon-core/src/poseidon/prefect/flows/hansei_report_flow.py:hansei_weekly_report_flow",
        },
        {
            "flow": mcp_metadata_refresh_flow,
            "name": "mcp-metadata-refresh-stream",
            "work_queue_name": "weekly-review-queue",
            "schedule": CronSchedule(cron="30 8 * * MON", timezone="UTC"),
            "parameters": {},
            "entrypoint": "poseidon-core/src/poseidon/prefect/flows/mcp_metadata_refresh_flow.py:mcp_metadata_refresh_flow",
        },
        {
            "flow": orchestration_flow,
            "name": "lean-orchestration-stream",
            "work_queue_name": "observability-queue",
            "schedule": None,
            "parameters": {"run_agents": False},
            "entrypoint": "poseidon-core/src/poseidon/prefect/flows/orchestration_flow.py:orchestration_flow",
        },
        {
            "flow": andon_alert_flow,
            "name": "andon-alert-stream",
            "work_queue_name": "observability-queue",
            "schedule": None,
            "parameters": {"flow_name": "manual", "message": "Manual test alert", "severity": "info"},
            "entrypoint": "poseidon-core/src/poseidon/prefect/flows/andon_alert_flow.py:andon_alert_flow",
        },
    ]


async def _apply_async(
    work_pool_name: str,
    repo_path: Path,
    storage_block_name: str,
    work_queue_prefix: Optional[str] = None,
) -> None:
    storage_block_id = await LocalFileSystem(basepath=str(repo_path)).save(storage_block_name, overwrite=True)
    specs = _deployment_specs(repo_path)

    for spec in specs:
        queue_name = spec["work_queue_name"]
        if work_queue_prefix:
            queue_name = f"{work_queue_prefix}-{queue_name}"

        deployment = await spec["flow"].deploy(
            name=spec["name"],
            work_pool_name=work_pool_name,
            work_queue_name=queue_name,
            schedule=spec["schedule"],
            parameters=spec["parameters"],
            entrypoint=spec["entrypoint"],
            storage_document_id=storage_block_id,
            tags=["poseidon", queue_name],
        )
        await deployment.apply()


def apply_stream_deployments(
    *,
    work_pool_name: str = "default",
    repo_path: Path | None = None,
    storage_block_name: str = "poseidon-streams-storage",
    work_queue_prefix: str | None = None,
) -> None:
    """Create Prefect deployments aligned to the six Poseidon work streams."""
    if repo_path is None:
        repo_path = Path(__file__).resolve().parents[1]

    asyncio.run(
        _apply_async(
            work_pool_name=work_pool_name,
            repo_path=repo_path,
            storage_block_name=storage_block_name,
            work_queue_prefix=work_queue_prefix,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply Prefect deployments for Poseidon work streams.")
    parser.add_argument("--work-pool", default="default", help="Prefect work pool to target.")
    parser.add_argument("--base-path", default=None, help="Repository root (defaults to autodetect).")
    parser.add_argument("--storage-block-name", default="poseidon-streams-storage", help="LocalFileSystem block name.")
    parser.add_argument("--queue-prefix", default=None, help="Optional prefix applied to created work queues.")
    args = parser.parse_args()

    base_path = Path(args.base_path).resolve() if args.base_path else None
    apply_stream_deployments(
        work_pool_name=args.work_pool,
        repo_path=base_path,
        storage_block_name=args.storage_block_name,
        work_queue_prefix=args.queue_prefix,
    )
