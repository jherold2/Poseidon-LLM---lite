"""Lightweight shim around langchain agent imports for test environments."""

from __future__ import annotations

import os
from typing import Any, Callable

if os.getenv("POSEIDON_DISABLE_LLM") == "1":  # pragma: no cover - exercised in tests
    class AgentExecutor:
        def __init__(self, *_, execute: Callable[..., Any] | None = None, **__):
            self.execute = execute

        def __call__(self, *args, **kwargs):
            if self.execute:
                return self.execute(*args, **kwargs)
            raise RuntimeError("LangChain agents disabled via POSEIDON_DISABLE_LLM")

    def create_tool_calling_agent(*args, **kwargs):
        class _StubAgent:
            def __call__(self, *_args, **_kwargs):
                raise RuntimeError("LangChain agents disabled via POSEIDON_DISABLE_LLM")

        return _StubAgent()
else:  # pragma: no cover - relies on langchain library
    import logging
    from langchain.agents import AgentExecutor
    from langchain.agents import create_tool_calling_agent as _lc_create_tool_calling_agent
    from langchain.agents import create_react_agent as _lc_create_react_agent

    _logger = logging.getLogger(__name__)

    def create_tool_calling_agent(llm, tools, prompt):
        """Wrapper that falls back to ReAct when the LLM lacks tool binding support."""

        try:
            return _lc_create_tool_calling_agent(llm, tools, prompt)
        except AttributeError as exc:
            if "bind_tools" not in str(exc):
                raise
            _logger.debug("LLM missing bind_tools; falling back to create_react_agent")
            return _lc_create_react_agent(llm, tools, prompt)


__all__ = ["AgentExecutor", "create_tool_calling_agent"]
