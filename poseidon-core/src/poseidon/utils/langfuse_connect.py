"""Helpers for interacting with Langfuse-managed prompt artifacts."""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


def _request(
    host: str,
    path: str,
    public_key: str,
    secret_key: str,
    *,
    timeout: int = 10,
) -> Optional[dict[str, Any]]:
    if not host or not public_key or not secret_key:
        logger.debug("Missing Langfuse credentials; skipping request to %s", path)
        return None

    url = f"{host.rstrip('/')}/{path.lstrip('/')}"
    response = requests.get(url, auth=(public_key, secret_key), timeout=timeout)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return payload
    logger.warning("Unexpected payload type from Langfuse: %s", type(payload))
    return None


def load_prompt_from_langfuse(
    host: str,
    project_id: str,
    prompt_name: str,
    public_key: str,
    secret_key: str,
) -> Optional[str]:
    """
    Retrieve a prompt document stored in Langfuse prompt collections.

    The scaffold expects a Langfuse prompt with an identifier matching ``agent_name``.
    """

    payload = _request(
        host,
        f"api/public/prompts/{project_id}/{prompt_name}",
        public_key,
        secret_key,
    )
    if not payload:
        return None

    for field in ("prompt", "template", "content", "body", "text"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()

    messages = payload.get("messages")
    if isinstance(messages, list):
        parts = []
        for message in messages:
            if isinstance(message, dict):
                content = message.get("content") or message.get("text")
                if isinstance(content, str) and content.strip():
                    parts.append(content.strip())
        if parts:
            return "\n".join(parts)

    return None
