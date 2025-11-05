"""MCP orchestration utilities and deployment scaffolding.

Keep package imports light to avoid side effects when importing submodules
like ``poseidon.mcp.api`` with Uvicorn. Do not import FastAPI apps or heavy
dependencies at package import time.
"""

from __future__ import annotations

# Export the orchestrator app name for convenience, but guard the import so
# that importing the package (poseidon.mcp) doesn't fail if optional deps are
# missing. Uvicorn will import ``poseidon.mcp.api:app`` directly.
try:  # pragma: no cover - defensive import guard for runtime
    from .api import app as orchestrator_app  # type: ignore
except Exception:  # pragma: no cover - keep package import resilient
    orchestrator_app = None  # type: ignore

__all__ = ["orchestrator_app"]
