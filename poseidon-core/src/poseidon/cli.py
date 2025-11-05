"""Command-line interface for running Poseidon workflows."""

from __future__ import annotations

import argparse
import logging
import os
import time
from collections import deque
from pathlib import Path
from typing import Optional, Sequence

import yaml

from poseidon.utils.logger_setup import LoggingContext, setup_logging
from poseidon.utils.local_llm import get_llm
from poseidon.utils.path_utils import core_root, resolve_config_path
from poseidon.utils.sshfs_connect import mount_remote_server
from poseidon.workflows.hierarchical_graph import SupervisorWorkflow
from poseidon.workflows.master_pipeline import master_workflow

setup_logging()
LOGGER = logging.getLogger(__name__)

CONFIG_PATH = resolve_config_path("connect_llm.yaml")
LOG_ROOT = core_root() / "logs"
_COMPONENT_DEFAULTS = {
    "app": LOG_ROOT / "app" / "app.log",
    "workflow": LOG_ROOT / "workflow" / "workflow.log",
    "inference": LOG_ROOT / "inference" / "inference.log",
    "audit": LOG_ROOT / "audit" / "audit.log",
}


def _load_llm_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _ensure_local_model_path(model_config: dict) -> Path:
    """Return the local model path, triggering SSHFS mount if necessary."""
    raw_path = model_config.get("path")
    if not raw_path:
        raise ValueError(f"{CONFIG_PATH} is missing 'model.path' for local providers")

    model_path = Path(raw_path).expanduser()
    if model_path.exists():
        return model_path

    LOGGER.info("Model path %s not found; attempting SSHFS mount", model_path)
    try:
        mount_point = mount_remote_server()
    except Exception as exc:  # pragma: no cover - depends on local environment
        raise FileNotFoundError(
            f"Unable to mount LLM directory for path {model_path}"
        ) from exc

    if not model_path.exists():
        raise FileNotFoundError(
            f"Mounted SSHFS at {mount_point}, but model path {model_path} still missing"
        )
    return model_path


def _resolve_log_path(component: str) -> Path:
    component_key = component.lower()
    if component_key in _COMPONENT_DEFAULTS:
        return _COMPONENT_DEFAULTS[component_key]
    agent_path = LOG_ROOT / "agents" / f"{component_key}.log"
    return agent_path


def _tail_file(path: Path, *, lines: int = 20) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()

    with path.open("r", encoding="utf-8") as stream:
        if lines > 0:
            history = deque(stream.readlines(), maxlen=lines)
            for entry in history:
                print(entry.rstrip(), flush=True)
        while True:
            line = stream.readline()
            if not line:
                time.sleep(0.5)
                continue
            print(line.rstrip(), flush=True)


def _command_run(args: argparse.Namespace) -> None:
    """Boot the supervisor workflow after ensuring the configured LLM is accessible."""
    with LoggingContext(session_id="cli", trace_id="cli-run"):
        config = _load_llm_config()
        model_config = config.get("model") or {}
        provider = str(model_config.get("provider", "local")).lower()

        if provider in {"remote", "remote_ollama", "ollama_remote"}:
            remote_section = model_config.get("remote") or config.get("remote") or {}
            target = remote_section.get("host") or remote_section.get("ip") or "unknown host"
            LOGGER.info("Using remote LLM provider '%s' targeting %s", provider, target)
        else:
            model_path = _ensure_local_model_path(model_config)
            LOGGER.info("Using local LLM weights at %s", model_path)

        # Warm up the cached LangChain instance so downstream agents can share it.
        get_llm()

        supervisor = SupervisorWorkflow()
        results = supervisor.execute_workflow(master_workflow, trace_id="cli-run")

        for step_result in results:
            print(step_result)


def _command_logs(args: argparse.Namespace) -> None:
    component = args.tail
    lines = args.lines
    path = _resolve_log_path(component)
    with LoggingContext(session_id=f"logs:{component}", trace_id=f"tail-{component}"):
        LOGGER.info("Tailing log file %s", path)
        try:
            _tail_file(path, lines=lines)
        except KeyboardInterrupt:  # pragma: no cover - interactive behaviour
            LOGGER.info("Stopping tail for %s", component)


def _command_prefect_run(args: argparse.Namespace) -> None:
    from poseidon.prefect import (
        agent_inference_flow,
        andon_alert_flow,
        dbt_build_flow,
    dbt_metric_build_flow,
    hansei_weekly_report_flow,
    lean_ingestion_flow,
    langfuse_trace_flow,
    mlflow_experiment_flow,
        mcp_metadata_refresh_flow,
        observability_monitor_flow,
        orchestration_flow,
        refresh_accounting_reporting_flow,
        refresh_production_reporting_flow,
        refresh_sales_reporting_flow,
    )

    flow_name: str = args.flow
    if flow_name == "refresh-sales-reporting":
        refresh_sales_reporting_flow(view_names=_normalise_list(args.view))
    elif flow_name == "refresh-accounting-reporting":
        refresh_accounting_reporting_flow(view_names=_normalise_list(args.view))
    elif flow_name == "refresh-production-reporting":
        refresh_production_reporting_flow(view_names=_normalise_list(args.view), upload_sharepoint=not args.skip_sharepoint)
    elif flow_name == "lean-ingestion":
        selectors = tuple(args.dbt_select) if args.dbt_select else ("event_log_unified", "lean_metrics")
        lean_ingestion_flow(
            run_dbt=not args.no_dbt,
            dbt_selectors=selectors,
            prefect_limit=args.prefect_limit,
        )
    elif flow_name == "dbt-build":
        selectors = args.selector or []
        dbt_build_flow(selectors=selectors, run_tests=not args.skip_tests)
    elif flow_name == "dbt-metric-build":
        dbt_metric_build_flow(select=args.dbt_metric_select)
    elif flow_name == "mlflow-experiment":
        params = dict(value.split("=", 1) for value in args.param or [])
        metrics = {k: float(v) for k, v in (value.split("=", 1) for value in args.metric or [])}
        mlflow_experiment_flow(
            experiment_name=args.experiment,
            run_name=args.run_name,
            parameters=params,
            metrics=metrics,
            improvement_note=args.improvement_note,
        )
    elif flow_name == "langfuse-trace":
        metadata = dict(value.split("=", 1) for value in args.param or [])
        metrics = {k: float(v) for k, v in (value.split("=", 1) for value in args.metric or [])}
        langfuse_trace_flow(
            host=args.langfuse_host,
            project_id=args.langfuse_project,
            public_key=args.langfuse_public_key or os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            secret_key=args.langfuse_secret_key or os.getenv("LANGFUSE_SECRET_KEY", ""),
            trace_name=args.trace_name,
            metadata=metadata,
            metrics=metrics,
        )
    elif flow_name == "agent-inference":
        agent_inference_flow(agent_name=args.agent_name, prompt=args.prompt, session_id=args.session_id)
    elif flow_name == "observability-monitor":
        observability_monitor_flow(window_minutes=args.window_minutes)
    elif flow_name == "hansei-weekly":
        hansei_weekly_report_flow(days_back=args.days_back)
    elif flow_name == "mcp-metadata-refresh":
        mcp_metadata_refresh_flow()
    elif flow_name == "orchestration":
        orchestration_flow(run_agents=args.run_agents)
    elif flow_name == "andon-alert":
        andon_alert_flow(flow_name=args.andon_flow_name, message=args.message, severity=args.severity)
    else:  # pragma: no cover - defensive
        raise SystemExit(f"Unknown flow '{flow_name}'")


def _normalise_list(values: Sequence[str] | None) -> list[str] | None:
    if not values:
        return None
    return [value.strip() for value in values if value.strip()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="poseidon")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Execute the master workflow")
    run_parser.set_defaults(func=_command_run)

    logs_parser = subparsers.add_parser("logs", help="Inspect Poseidon log files")
    logs_parser.add_argument("--tail", metavar="COMPONENT", required=True, help="Follow log output for a component (e.g., app, workflow, sales)")
    logs_parser.add_argument("--lines", type=int, default=20, help="Number of existing lines to print before following")
    logs_parser.set_defaults(func=_command_logs)

    prefect_parser = subparsers.add_parser("prefect", help="Execute Prefect flows")
    prefect_sub = prefect_parser.add_subparsers(dest="prefect_command")

    prefect_run = prefect_sub.add_parser("run", help="Run a named Prefect flow")
    prefect_run.add_argument("flow", choices=[
        "refresh-sales-reporting",
        "refresh-accounting-reporting",
        "refresh-production-reporting",
        "lean-ingestion",
        "dbt-build",
        "dbt-metric-build",
        "mlflow-experiment",
        "langfuse-trace",
        "agent-inference",
        "observability-monitor",
        "hansei-weekly",
        "mcp-metadata-refresh",
        "orchestration",
        "andon-alert",
    ])
    prefect_run.add_argument("--view", nargs="*", help="Materialized view names for refresh-sales-reporting flow")
    prefect_run.add_argument("--skip-sharepoint", action="store_true", help="Skip SharePoint upload during production refresh")
    prefect_run.add_argument("--no-dbt", action="store_true", help="Skip rebuilding Lean dbt models after ingestion")
    prefect_run.add_argument("--dbt-select", nargs="*", help="Override the dbt selectors passed to the Lean ingestion flow")
    prefect_run.add_argument("--prefect-limit", type=int, default=1000, help="Maximum number of Prefect runs to ingest")
    prefect_run.add_argument("--selector", dest="selector", action="append", help="dbt selector for dbt-build flow (repeatable)")
    prefect_run.add_argument("--skip-tests", action="store_true", help="Skip dbt tests during dbt-build flow")
    prefect_run.add_argument("--dbt-metric-select", default="marts+", help="Selector for dbt metric build flow")
    prefect_run.add_argument("--experiment", default="poseidon-default", help="MLflow experiment name")
    prefect_run.add_argument("--run-name", default=None, help="Optional MLflow run name")
    prefect_run.add_argument("--improvement-note", default=None, help="Optional Kaizen note for MLflow experiment")
    prefect_run.add_argument("--langfuse-host", default="https://cdaseafood.ddns.net/langfuse", help="Langfuse host URL")
    prefect_run.add_argument("--langfuse-project", default="poseidon", help="Langfuse project identifier")
    prefect_run.add_argument("--langfuse-public-key", default=None, help="Langfuse public API key (falls back to LANGFUSE_PUBLIC_KEY env var)")
    prefect_run.add_argument("--langfuse-secret-key", default=None, help="Langfuse secret API key (falls back to LANGFUSE_SECRET_KEY env var)")
    prefect_run.add_argument("--trace-name", default="poseidon-default", help="Langfuse trace name")
    prefect_run.add_argument(
        "--param",
        action="append",
        help="Key=value pairs used as MLflow parameters or Langfuse metadata",
        default=[],
    )
    prefect_run.add_argument(
        "--metric",
        action="append",
        help="Key=value pairs used as MLflow or Langfuse metrics",
        default=[],
    )
    prefect_run.add_argument("--agent-name", default="sales", help="Agent name for agent-inference flow")
    prefect_run.add_argument("--prompt", default="Provide a KPI summary.", help="Prompt for agent-inference flow")
    prefect_run.add_argument("--session-id", default=None, help="Session identifier for agent-inference flow")
    prefect_run.add_argument("--window-minutes", type=int, default=15, help="Lookback window for observability-monitor flow")
    prefect_run.add_argument("--days-back", type=int, default=7, help="Days of history for Hansei weekly flow")
    prefect_run.add_argument("--run-agents", action="store_true", help="Execute agent batch during orchestration flow")
    prefect_run.add_argument("--andon-flow-name", default="manual", help="Flow name for manual Andon alert")
    prefect_run.add_argument("--message", default="Manual Andon test.", help="Message for Andon alert flow")
    prefect_run.add_argument("--severity", default="warning", choices=["info", "warning", "critical"], help="Severity for Andon alert flow")
    prefect_run.set_defaults(func=_command_prefect_run)

    parser.set_defaults(func=_command_run)
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
