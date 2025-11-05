"""Lazy import helpers for query tool modules."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_MODULES = {
    "category_queries": "poseidon.tools.query_tools.category_queries",
    "accounting_queries": "poseidon.tools.query_tools.accounting_queries",
    "logistics_queries": "poseidon.tools.query_tools.logistics_queries",
    "manufacturing_queries": "poseidon.tools.query_tools.manufacturing_queries",
    "sales_history_queries": "poseidon.tools.query_tools.sales_history_queries",
    "feedback_context": "poseidon.tools.query_tools.feedback_context",
    "utils": "poseidon.tools.query_tools.utils",
}

__all__ = list(_MODULES.keys())


def __getattr__(name: str) -> Any:  # pragma: no cover - simple delegation
    if name in _MODULES:
        module = import_module(_MODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module 'poseidon.tools.query_tools' has no attribute '{name}'")
