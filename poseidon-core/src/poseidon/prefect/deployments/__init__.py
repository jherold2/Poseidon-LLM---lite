"""Deployment entrypoints for Prefect."""

from poseidon.prefect.deployments.reporting import apply_all_deployments
from poseidon.prefect.deployments.streams import apply_stream_deployments

__all__ = ["apply_all_deployments", "apply_stream_deployments"]
