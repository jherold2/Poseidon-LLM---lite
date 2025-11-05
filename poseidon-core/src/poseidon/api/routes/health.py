"""Health and readiness endpoints."""

from __future__ import annotations

import logging
import socket
from datetime import datetime, timezone

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live(request: Request) -> dict[str, str]:
    """Basic liveness probe for load balancers."""
    trace_id = getattr(request.state, "trace_id", "N/A")
    session_id = getattr(request.state, "session_id", "N/A")
    payload = {
        "status": "ok",
        "hostname": socket.gethostname(),
        "checked_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    logger.debug(
        "Liveness probe answered",
        extra={"trace_id": trace_id, "session_id": session_id},
    )
    return payload


@router.get("/ready")
async def ready(request: Request) -> dict[str, str]:
    """Readiness probe that can be extended with deeper checks."""
    trace_id = getattr(request.state, "trace_id", "N/A")
    session_id = getattr(request.state, "session_id", "N/A")
    payload = {
        "status": "ready",
        "hostname": socket.gethostname(),
        "checked_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    logger.debug(
        "Readiness probe answered",
        extra={"trace_id": trace_id, "session_id": session_id},
    )
    return payload
