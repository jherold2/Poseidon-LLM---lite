"""Minimal authentication middleware for the Poseidon LangGraph deployment."""

from __future__ import annotations

import hmac
import os
from typing import Final

from langgraph_sdk import Auth
from langgraph_sdk.auth import exceptions as auth_exceptions

_TOKEN_ENV: Final[str] = "POSEIDON_AUTH_TOKEN"
_DEFAULT_TOKEN: Final[str] = "poseidon-dev-token"

auth = Auth()


def _expected_token() -> str:
    token = os.getenv(_TOKEN_ENV)
    if token:
        return token.strip()
    # Fall back to a development token to keep local setup simple.
    return _DEFAULT_TOKEN


@auth.authenticate
async def authenticate(authorization: str | None = None):
    """Validate a Bearer token from the Authorization header."""
    if not authorization:
        raise auth_exceptions.HTTPException(status_code=401, detail="Missing Authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise auth_exceptions.HTTPException(status_code=401, detail="Invalid authorization scheme")

    expected = _expected_token()
    if not expected:
        raise auth_exceptions.HTTPException(status_code=500, detail="Server auth token not configured")

    if not hmac.compare_digest(token.strip(), expected):
        raise auth_exceptions.HTTPException(status_code=401, detail="Invalid or expired token")

    # LangGraph stores this user context in run metadata for downstream nodes.
    return {
        "identity": "poseidon-local",
        "permissions": ["graph:write"],
    }


@auth.on
async def authorize_all(ctx, value):
    """Allow authenticated callers to access graph resources."""
    return None


__all__ = ["auth"]
