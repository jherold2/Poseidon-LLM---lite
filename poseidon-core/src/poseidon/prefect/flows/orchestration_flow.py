"""Master orchestration flow coordinating Lean pipelines."""

from __future__ import annotations

from prefect import flow

from poseidon.prefect.flows.agent_inference_flow import agent_inference_flow
from poseidon.prefect.flows.andon_alert_flow import andon_alert_flow
from poseidon.prefect.flows.dbt_metric_build_flow import dbt_metric_build_flow
from poseidon.prefect.flows.hansei_report_flow import hansei_weekly_report_flow
from poseidon.prefect.flows.ingestion_flow import lean_ingestion_flow
from poseidon.prefect.flows.mcp_metadata_refresh_flow import mcp_metadata_refresh_flow
from poseidon.prefect.flows.observability_monitor_flow import observability_monitor_flow


@flow(name="Lean Orchestration Flow", log_prints=False)
def orchestration_flow(run_agents: bool = False) -> None:
    """Run the ingestion, transformation, observability, alignment, and reflection flows in sequence."""
    ingestion = lean_ingestion_flow.with_options(name="lean-ingestion-subflow")
    ingestion()

    dbt_metric_build_flow.with_options(name="dbt-metric-build-subflow")()

    observability_monitor_flow.with_options(name="observability-alert-subflow")()

    mcp_metadata_refresh_flow.with_options(name="mcp-refresh-subflow")()

    hansei_weekly_report_flow.with_options(name="hansei-review-subflow")()

    if run_agents:
        agent_inference_flow.with_options(name="agent-batch-subflow")(agent_name="sales", prompt="Provide weekly KPI summary")

    # Optional: fire a completion alert
    andon_alert_flow.with_options(name="orchestration-complete-alert")(
        flow_name="orchestration_flow",
        message="Lean orchestration cycle completed successfully",
        severity="info",
    )


__all__ = ["orchestration_flow"]
