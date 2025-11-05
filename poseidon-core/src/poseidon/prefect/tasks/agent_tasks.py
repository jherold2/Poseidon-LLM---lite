"""Prefect tasks for executing Poseidon agent workflows."""

from __future__ import annotations

from typing import Callable, Dict

from prefect import get_run_logger, task

from poseidon.agents.accounting_agent import create_accounting_agent
from poseidon.agents.inference_agent import create_inference_agent
from poseidon.agents.logistics_agent import create_logistics_agent
from poseidon.agents.manufacturing_agent import create_manufacturing_agent
from poseidon.agents.purchasing_agent import create_purchasing_agent
from poseidon.agents.sales_agent import create_sales_agent

AgentFactory = Callable[[], object]

AGENT_FACTORIES: Dict[str, AgentFactory] = {
    "sales": create_sales_agent,
    "accounting": create_accounting_agent,
    "purchasing": create_purchasing_agent,
    "manufacturing": create_manufacturing_agent,
    "logistics": create_logistics_agent,
    "inference": create_inference_agent,
}


@task(name="run-agent-prompt")
def run_agent_prompt(agent_name: str, prompt: str, session_id: str | None = None) -> dict:
    """Execute a Poseidon agent with a given prompt and return the structured output."""
    logger = get_run_logger()
    factory = AGENT_FACTORIES.get(agent_name)
    if factory is None:
        available = ", ".join(sorted(AGENT_FACTORIES))
        raise ValueError(f"Unknown agent '{agent_name}'. Available agents: {available}")

    executor = factory()
    payload = {
        "input": prompt,
        "session_id": session_id or "prefect-agent-session",
        "trace_id": f"prefect-{agent_name}",
    }
    logger.info("Executing %s agent via Prefect orchestration.", agent_name)
    result = executor.execute(payload)
    logger.info("Agent %s completed execution.", agent_name)
    return result


__all__ = ["run_agent_prompt", "AGENT_FACTORIES"]
