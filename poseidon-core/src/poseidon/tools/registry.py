"""Decorator-driven registry for Poseidon tool plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from langchain_core.tools import Tool


ToolFactory = Callable[..., Any]


@dataclass
class ToolMetadata:
    tool: Tool
    python_callable: ToolFactory | None = None
    version: str = "1.0"
    tags: List[str] | None = None


class ToolRegistry:
    """Simple in-memory registry for tool discovery and metadata."""

    _registry: Dict[str, ToolMetadata] = {}

    @classmethod
    def register(
        cls,
        tool: Tool,
        *,
        version: str = "1.0",
        tags: Optional[List[str]] = None,
        python_callable: ToolFactory | None = None,
    ) -> Tool:
        cls._registry[tool.name] = ToolMetadata(
            tool=tool,
            python_callable=python_callable,
            version=version,
            tags=tags or [],
        )
        return tool

    @classmethod
    def get(cls, name: str) -> Tool:
        return cls._registry[name].tool

    @classmethod
    def list(cls) -> Dict[str, ToolMetadata]:
        return dict(cls._registry)


def register_tool(
    *,
    name: str,
    description: str,
    version: str = "1.0",
    tags: Optional[List[str]] = None,
) -> Callable[[ToolFactory], Tool]:
    """
    Decorator that converts a plain callable into a LangChain Tool and registers it.

    The decorated symbol becomes the Tool instance, preserving the original callable
    in the registry metadata for direct invocation when needed.
    """

    def decorator(func: ToolFactory) -> Tool:
        tool = Tool(name=name, func=func, description=description)
        ToolRegistry.register(tool, version=version, tags=tags, python_callable=func)
        return tool

    return decorator


__all__ = ["ToolRegistry", "register_tool", "ToolMetadata"]
