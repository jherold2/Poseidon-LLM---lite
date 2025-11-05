"""Prefect flow orchestrating Poseidon agent executions."""

from __future__ import annotations

from prefect import flow, get_run_logger

from poseidon.prefect.tasks.agent_tasks import run_agent_prompt
from poseidon.prefect.tasks.observability_tasks import flow_run_guard


@flow(name="Agent Inference Flow", log_prints=False)
def agent_inference_flow(agent_name: str, prompt: str, session_id: str | None = None) -> dict:
    """
    Execute a Poseidon agent through Prefect orchestration.

    Parameters
    ----------
    agent_name:
        Registered agent slug (e.g. ``sales``, ``accounting``).
    prompt:
        Natural-language prompt to dispatch to the agent.
    session_id:
        Optional session identifier propagated to the agent execution context.
    """
    logger = get_run_logger()
    with flow_run_guard("agent-inference", payload={"agent": agent_name, "session_id": session_id, "prompt": prompt}):
        result = run_agent_prompt(agent_name=agent_name, prompt=prompt, session_id=session_id)
        logger.info("Agent inference completed for %s", agent_name)
        return result


__all__ = ["agent_inference_flow"]
