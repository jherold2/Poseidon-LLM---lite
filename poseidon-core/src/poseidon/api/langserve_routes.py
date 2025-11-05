"""LangServe playground routes for Poseidon agents."""

from __future__ import annotations

import logging
from typing import Any, Dict
from uuid import uuid4

from fastapi import FastAPI
from langchain_core.runnables import RunnableLambda
from langserve import add_routes
from pydantic import BaseModel, Field

from poseidon.agents.registry import AgentRegistry
from poseidon.utils.logger_setup import LoggingContext
from poseidon.workflows.hierarchical_graph import SupervisorWorkflow

logger = logging.getLogger(__name__)


class SupervisorInput(BaseModel):
    module: str = Field(..., description="Registered module name (e.g., 'sales').")
    input: str | None = Field(
        None,
        description="Prompt or question for the agent. Either 'input' or 'prompt' must be provided.",
    )
    prompt: str | None = Field(
        None,
        description="Alternative field for prompt text maintained for LangChain UI ergonomics.",
    )
    session_id: str | None = Field(
        None,
        description="Optional conversation/session identifier for context continuity.",
    )


class SupervisorOutput(BaseModel):
    module: str
    session_id: str
    result: Dict[str, Any]


def _supervisor_callable(payload: SupervisorInput) -> SupervisorOutput:
    module = payload.module
    prompt_text = payload.input or payload.prompt
    if not prompt_text:
        raise ValueError("Supervisor route requires either 'input' or 'prompt'.")

    session_id = payload.session_id or "default"
    trace_id = uuid4().hex
    supervisor = SupervisorWorkflow()
    with LoggingContext(session_id=session_id, trace_id=trace_id):
        logger.info(
            "LangServe supervisor invocation",
            extra={"module": module or "auto", "session_id": session_id, "trace_id": trace_id},
        )
        logger.debug(
            "LangServe prompt snippet: %s",
            prompt_text[:150],
            extra={"module": module or "auto", "session_id": session_id, "trace_id": trace_id},
        )
        result = supervisor.route_query(
            module,
            {"input": prompt_text, "session_id": session_id, "trace_id": trace_id},
        )
    return SupervisorOutput(module=module, session_id=session_id, result=result)


def _agent_callable(module: str):
    def _invoke(payload: SupervisorInput) -> SupervisorOutput:
        prompt_text = payload.input or payload.prompt
        if not prompt_text:
            raise ValueError("Agent route requires either 'input' or 'prompt'.")
        session_id = payload.session_id or "default"
        trace_id = uuid4().hex
        agent = AgentRegistry.get_agent(module)
        with LoggingContext(session_id=session_id, trace_id=trace_id, agent_name=module):
            logger.info(
                "LangServe agent invocation",
                extra={"module": module, "session_id": session_id, "trace_id": trace_id},
            )
            logger.debug(
                "Agent prompt snippet: %s",
                prompt_text[:150],
                extra={"module": module, "session_id": session_id, "trace_id": trace_id},
            )
            response = agent.invoke({"input": prompt_text, "session_id": session_id, "trace_id": trace_id})
            if isinstance(response, dict):
                result = response
            else:
                result = {"output": response}
        result.setdefault("_module", module)
        result.setdefault("_session_id", session_id)
        return SupervisorOutput(module=module, session_id=session_id, result=result)

    return _invoke


def register_langserve_routes(app: FastAPI) -> None:
    """Attach LangServe playground routes to the given FastAPI app."""
    # Supervisor orchestrator route
    add_routes(
        app,
        runnable=RunnableLambda(_supervisor_callable),
        path="/playground/supervisor",
        input_type=SupervisorInput,
        output_type=SupervisorOutput,
    )

    # Direct agent access routes for convenience
    for module in sorted(AgentRegistry.get_available_modules()):
        add_routes(
            app,
            runnable=RunnableLambda(_agent_callable(module)),
            path=f"/playground/agents/{module}",
            input_type=SupervisorInput,
            output_type=SupervisorOutput,
        )


__all__ = ["register_langserve_routes"]
