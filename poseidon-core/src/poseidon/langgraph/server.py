"""LangGraph integration for Poseidon agents."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
from functools import lru_cache
from time import perf_counter
from typing import Any, Dict, Iterable, Optional, Tuple
from uuid import uuid4

from fastapi import FastAPI
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph
from poseidon.agents.registry import AgentRegistry
from poseidon.langgraph.auth import auth as poseidon_auth
from poseidon.utils.logger_setup import LoggingContext, setup_logging
from poseidon.workflows.hierarchical_graph import SupervisorWorkflow

# Ensure required defaults are in place before importing LangGraph packages.
os.environ.setdefault("DATABASE_URI", ":memory:")
os.environ.setdefault("ALLOW_PRIVATE_NETWORK", "true")
os.environ.setdefault("REDIS_URI", "redis://localhost:6379/0")
os.environ.setdefault("LANGGRAPH_RUNTIME_EDITION", "inmem")

try:
    # LangGraph runtime helpers live in the venv-installed packages.
    from langgraph_api.graph import register_graph
    from langgraph_api.server import app as _langgraph_app
    from langgraph_runtime_inmem.checkpoint import Checkpointer
    from langgraph_sdk.client import configure_loopback_transports
except ModuleNotFoundError as exc:  # pragma: no cover - runtime guard
    register_graph = None  # type: ignore[assignment]
    _langgraph_app = None  # type: ignore[assignment]
    Checkpointer = None  # type: ignore[assignment]
    configure_loopback_transports = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

setup_logging()
logger = logging.getLogger(__name__)

_ALLOWED_MODULES = set(AgentRegistry.get_available_modules())
_DEFAULT_MODULE = "inference" if "inference" in _ALLOWED_MODULES else next(
    iter(_ALLOWED_MODULES), "inference"
)


def _normalise_text(content: Any) -> str:
    if isinstance(content, list):
        texts: Iterable[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts = (*texts, str(part.get("text", "")))
            else:
                texts = (*texts, str(part))
        return "\n".join(str(t) for t in texts if t)
    if isinstance(content, (dict, tuple, set)):
        return json.dumps(content)
    return str(content)


def _extract_payload(message: HumanMessage) -> Tuple[Optional[str], str]:
    module: Optional[str] = None
    prompt = ""
    content = message.content

    if isinstance(content, dict):
        module = str(content.get("module", module)).lower()
        prompt = content.get("input") or content.get("prompt") or ""
    else:
        prompt = _normalise_text(content)
        if ":" in prompt:
            possible, remainder = prompt.split(":", 1)
            candidate = possible.strip().lower()
            if candidate in _ALLOWED_MODULES:
                module = candidate
                prompt = remainder.strip()

    if module not in _ALLOWED_MODULES:
        module = None
    return module, prompt.strip()

def _build_poseidon_graph():
    if Checkpointer is None or register_graph is None:
        msg = "LangGraph optional dependencies are not installed."
        raise RuntimeError(msg)

    supervisor = SupervisorWorkflow()
    checkpointer = Checkpointer()

    graph = StateGraph(MessagesState, context_schema=dict)

    def _handle_request(state: MessagesState, runtime: Any):
        messages: list[BaseMessage] = state["messages"]
        if not messages:
            return {"messages": []}
        last_message = messages[-1]
        if not isinstance(last_message, HumanMessage):
            return {"messages": []}

        runtime_config = getattr(runtime, "config", {}) or {}
        metadata = runtime_config.get("metadata") or {}
        trace_id = metadata.get("trace_id") or metadata.get("x-trace-id")
        if not trace_id and isinstance(getattr(last_message, "additional_kwargs", {}), dict):
            trace_id = last_message.additional_kwargs.get("trace_id")
        trace_id = trace_id or uuid4().hex

        module, prompt_text = _extract_payload(last_message)
        if not prompt_text:
            return {
                "messages": [
                    AIMessage(
                        content="No query supplied. Provide a question or instruction for the agents."
                    )
                ]
            }

        thread_id = runtime_config.get("configurable", {}).get("thread_id") or "default"
        with LoggingContext(trace_id=trace_id, session_id=thread_id):
            logger.info(
                "LangGraph node received message",
                extra={
                    "trace_id": trace_id,
                    "session_id": thread_id,
                    "module": module or "auto",
                    "message_count": len(messages),
                },
            )
            logger.debug(
                "LangGraph prompt snippet: %s",
                prompt_text[:200],
                extra={"trace_id": trace_id, "session_id": thread_id, "module": module or "auto"},
            )
            payload = {"input": prompt_text, "session_id": thread_id, "trace_id": trace_id}
            start_time = perf_counter()
            response = supervisor.route_query(module or "", payload)
            elapsed_ms = (perf_counter() - start_time) * 1000
            logger.debug(
                "[LangGraph] Node 'poseidon' executed in %.2fms",
                elapsed_ms,
                extra={
                    "trace_id": trace_id,
                    "session_id": thread_id,
                    "module": response.get("_module", module or _DEFAULT_MODULE),
                },
            )
        resolved_module = str(response.get("_module", module or _DEFAULT_MODULE))

        return {
            "messages": [
                AIMessage(
                    content=json.dumps(response, ensure_ascii=False, indent=2),
                    additional_kwargs={
                        "module": resolved_module,
                        "session_id": thread_id,
                        "trace_id": trace_id,
                    },
                )
            ]
        }

    graph.add_node("poseidon", _handle_request)
    graph.add_edge("__start__", "poseidon")
    graph.add_edge("poseidon", "__end__")

    return graph.compile(checkpointer=checkpointer, name="poseidon-supervisor")


async def _register_graph_once():
    if register_graph is None:
        msg = "LangGraph optional dependencies are not installed."
        raise RuntimeError(msg)

    graph = _build_poseidon_graph()
    kwargs: Dict[str, Any] = {
        "graph_id": "poseidon-supervisor",
        "graph": lambda: graph,
        "description": "Poseidon's supervisory agent graph.",
    }

    signature = inspect.signature(register_graph)
    if "config" in signature.parameters:
        kwargs.setdefault("config", None)
    if "auth" in signature.parameters:
        kwargs["auth"] = poseidon_auth

    await register_graph(**kwargs)


@lru_cache(maxsize=1)
def get_langgraph_app():
    """Return a configured LangGraph ASGI app registered with Poseidon graph."""
    if _IMPORT_ERROR:
        return _build_placeholder_app(_IMPORT_ERROR)

    # Ensure local-dev defaults mirroring `langgraph dev`.
    os.environ.setdefault("LANGSMITH_LANGGRAPH_API_VARIANT", "local_dev")

    if not getattr(_langgraph_app.state, "poseidon_startup_registered", False):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_register_graph_once())
        else:
            loop.create_task(_register_graph_once())
        configure_loopback_transports(_langgraph_app)
        _langgraph_app.state.poseidon_startup_registered = True

    return _langgraph_app


def _build_placeholder_app(error: ModuleNotFoundError) -> FastAPI:
    """Fallback ASGI app when LangGraph optional deps are unavailable."""
    app = FastAPI(
        title="Poseidon LangGraph (disabled)",
        description=(
            "LangGraph routes are unavailable because optional dependencies "
            "are missing. Install 'langgraph-api', 'langgraph-runtime-inmem', "
            "and 'langgraph-sdk' to enable this endpoint."
        ),
        version="0.0.0",
    )

    missing = str(error)

    @app.get("/")
    async def _root():
        return {
            "status": "unavailable",
            "detail": "LangGraph integration disabled. Install optional dependencies.",
            "missing_module": missing,
        }

    return app


__all__ = ["get_langgraph_app"]
