"""Flow exporting dbt metadata for MCP consumers."""

from __future__ import annotations

from pathlib import Path

from prefect import flow, get_run_logger

from poseidon.prefect.tasks.dbt_mcp_tasks import load_dbt_metadata, persist_mcp_metadata


@flow(name="MCP Metadata Refresh Flow", log_prints=True)
def mcp_metadata_refresh_flow(project_root: Path | None = None) -> int:
    """Export dbt semantic metadata into the lean_obs.mcp_metadata table."""
    logger = get_run_logger()
    root = project_root or Path(__file__).resolve().parents[6] / "poseidon-cda" / "dbt" / "analytics" / "cedea_metrics"
    entries = load_dbt_metadata(root)
    count = persist_mcp_metadata(entries)
    logger.info("MCP metadata refresh complete (%s entries)", count)
    return count


__all__ = ["mcp_metadata_refresh_flow"]
