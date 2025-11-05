"""Tools to retrieve conversation context from the shared cache."""

from __future__ import annotations

import logging

import json
from typing import Dict

from langchain_core.tools import Tool

from poseidon.utils.cache import ConversationCache
from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)
cache = ConversationCache()


def fetch_recent_context(args: Dict[str, str]) -> str:
    session_id = args.get("session_id", "default")
    hours = args.get("hours")
    try:
        window = int(hours) if hours else 24
    except ValueError:
        window = 24
        logger.warning("Invalid hours '%s' provided to fetch_recent_context", hours)

    history = cache.get_history(session_id, window)
    return json.dumps({"session_id": session_id, "window_hours": window, "history": history})


context_tool = Tool(
    name="fetch_recent_context",
    func=fetch_recent_context,
    description="Retrieve cached conversation history. Args: session_id (str, optional), hours (int, optional)."
)

__all__ = ["context_tool"]
