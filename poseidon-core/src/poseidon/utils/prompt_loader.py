"""Utilities for retrieving agent prompts from Langfuse, prompt service, or local overrides."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import requests

from poseidon.utils.config_loader import get_prompt_config
from poseidon.utils.langfuse_connect import load_prompt_from_langfuse
from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

PROMPT_SERVICE_URL = os.getenv("PROMPT_SERVICE_URL", "").strip()


def _candidate_endpoints(agent_name: str) -> list[str]:
    if not PROMPT_SERVICE_URL:
        return []
    base = PROMPT_SERVICE_URL.rstrip("/")
    return [
        f"{base}/prompts/{agent_name}",
        f"{base}/prompts/{agent_name}.json",
        f"{base}/api/prompts/{agent_name}",
    ]


@lru_cache(maxsize=16)
def load_prompt_template(agent_name: str, default_template: str) -> str:
    """Fetch prompt text for the given agent name, honoring feature flags."""
    prompt_cfg = get_prompt_config()
    mode = (prompt_cfg.get("mode") or "langfuse").lower()

    if mode == "langfuse":
        prompt = _load_prompt_via_langfuse(agent_name, prompt_cfg)
        if prompt:
            return prompt

    if mode == "local":
        directory = prompt_cfg.get("directory")
        if directory:
            path = Path(directory) / f"{agent_name}.txt"
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8").strip()
                    if content:
                        logger.info("Loaded prompt for %s from %s", agent_name, path)
                        return content
                except OSError as exc:
                    logger.warning("Failed to read prompt file %s: %s", path, exc)

    for url in _candidate_endpoints(agent_name):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            prompt = _extract_prompt_text(response)
            if prompt:
                logger.info("Loaded prompt for %s from %s", agent_name, url)
                return prompt
        except Exception as exc:  # pragma: no cover - best effort retrieval
            logger.warning("Prompt fetch attempt failed for %s via %s: %s", agent_name, url, exc)

    logger.info("Using default prompt for %s", agent_name)
    return default_template


def _extract_prompt_text(response: requests.Response) -> Optional[str]:
    content_type = response.headers.get("Content-Type", "")
    try:
        if "application/json" in content_type:
            data = response.json()
            for key in ("prompt", "content", "template", "body", "text"):
                if isinstance(data, dict) and data.get(key):
                    return str(data[key])
        text = response.text.strip()
        return text or None
    except (ValueError, TypeError):
        return None


def _load_prompt_via_langfuse(agent_name: str, prompt_cfg: dict) -> Optional[str]:
    langfuse_cfg = prompt_cfg.get("langfuse") or {}

    agent_overrides: dict[str, object] = {}
    agents_cfg = langfuse_cfg.get("agents")
    if isinstance(agents_cfg, dict):
        agent_value = agents_cfg.get(agent_name)
        if isinstance(agent_value, dict):
            agent_overrides = agent_value
        elif isinstance(agent_value, str):
            agent_overrides = {"prompt_name": agent_value}

    host = (
        agent_overrides.get("host")
        or langfuse_cfg.get("host")
        or os.getenv("LANGFUSE_HOST")
        or ""
    )
    project_id = (
        agent_overrides.get("project_id")
        or langfuse_cfg.get("project_id")
        or os.getenv("LANGFUSE_PROJECT_ID")
        or "poseidon"
    )
    public_key = (
        agent_overrides.get("public_key")
        or langfuse_cfg.get("public_key")
        or os.getenv("LANGFUSE_PUBLIC_KEY")
        or ""
    )
    secret_key = (
        agent_overrides.get("secret_key")
        or langfuse_cfg.get("secret_key")
        or os.getenv("LANGFUSE_SECRET_KEY")
        or ""
    )
    prompt_name = agent_overrides.get("prompt_name") or langfuse_cfg.get("prompt_name") or agent_name

    if not host or not public_key or not secret_key:
        logger.debug(
            "Langfuse configuration incomplete for agent %s (host=%s, project=%s)",
            agent_name,
            host,
            project_id,
        )
        return None

    prompt = load_prompt_from_langfuse(
        str(host),
        str(project_id),
        str(prompt_name),
        str(public_key),
        str(secret_key),
    )
    if prompt:
        logger.info("Loaded prompt for %s from Langfuse (%s)", agent_name, prompt_name)
        return prompt

    logger.warning("Langfuse prompt %s unavailable for agent %s", prompt_name, agent_name)
    return None
