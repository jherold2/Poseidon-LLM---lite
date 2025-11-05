"""Tools for recording structured action items or decisions."""

from __future__ import annotations

import logging

import json
from typing import Dict

from langchain_core.tools import Tool

from poseidon.observability.audit_log import append_event
from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def record_decision(args: Dict[str, str]) -> str:
    payload = {
        "actor": args.get("actor"),
        "topic": args.get("topic"),
        "decision": args.get("decision"),
        "rationale": args.get("rationale"),
        "next_steps": args.get("next_steps"),
    }
    try:
        path = append_event(
            "decision_recorded",
            {
                "topic": payload["topic"],
                "actor": payload["actor"],
                "decision": payload["decision"],
                "rationale": payload["rationale"],
                "next_steps": payload["next_steps"],
            },
        )
        logger.info("Decision recorded for topic %s", payload.get("topic"))
        return json.dumps({"status": "recorded", "path": str(path)})
    except Exception as exc:  # pragma: no cover - file IO guard
        logger.error("Failed to record decision: %s", exc)
        return json.dumps({"error": str(exc)})


decision_tool = Tool(
    name="record_decision",
    func=record_decision,
    description=(
        "Store a structured decision. Args: actor (str, optional), topic (str), decision (str), "
        "rationale (str, optional), next_steps (str, optional)."
    ),
)

__all__ = ["decision_tool"]
