"""Simple form-based authentication endpoints for local development."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_USERNAME = os.getenv("POSEIDON_LOGIN_USERNAME", "poseidon")
_PASSWORD = os.getenv("POSEIDON_LOGIN_PASSWORD", "poseidon")
_TOKEN = os.getenv("POSEIDON_AUTH_TOKEN", "poseidon-dev-token")

router = APIRouter(prefix="", tags=["auth"])


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Return the shared bearer token when credentials match."""
    trace_id = getattr(request.state, "trace_id", "N/A")
    session_id = getattr(request.state, "session_id", "N/A")
    if username != _USERNAME or password != _PASSWORD:
        logger.warning(
            "Authentication failure for user '%s'",
            username,
            extra={"trace_id": trace_id, "session_id": session_id},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    logger.info(
        "Authentication success for user '%s'",
        username,
        extra={"trace_id": trace_id, "session_id": session_id},
    )
    return JSONResponse(
        {
            "access_token": _TOKEN,
            "token_type": "bearer",
        }
    )


@router.post("/logout")
def logout(request: Request):
    """Stateless logout endpoint for API symmetry."""
    trace_id = getattr(request.state, "trace_id", "N/A")
    session_id = getattr(request.state, "session_id", "N/A")
    logger.info(
        "Logout invoked",
        extra={"trace_id": trace_id, "session_id": session_id},
    )
    return {"status": "logged_out"}


__all__ = ["router"]
