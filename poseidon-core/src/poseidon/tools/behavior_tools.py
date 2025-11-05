"""Behavioral analytics helpers for customer interaction insights."""

from __future__ import annotations

import logging

import json
from collections import Counter
from statistics import mean
from typing import Dict, List

from langchain_core.tools import Tool

from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def _compute_channel_breakdown(channels: List[str]) -> List[Dict[str, object]]:
    counts = Counter(channels)
    total = sum(counts.values()) or 1
    return [
        {"channel": channel, "count": count, "share": count / total}
        for channel, count in counts.most_common()
    ]


def analyze_customer_behavior(args: Dict[str, object]) -> str:
    interactions = args.get("interactions") or []
    if not isinstance(interactions, list) or not interactions:
        return json.dumps({"error": "interactions must be a non-empty list"})

    try:
        channels = [str(item.get("channel", "unknown")).lower() for item in interactions]
        intents = [str(item.get("intent")).lower() for item in interactions if item.get("intent")]
        recency_days = [
            float(item.get("days_since_interaction"))
            for item in interactions
            if isinstance(item.get("days_since_interaction"), (int, float))
        ]
        spend_values = [
            float(item.get("spend", 0))
            for item in interactions
            if item.get("spend") is not None
        ]
    except (TypeError, ValueError) as exc:
        logger.error("Invalid interaction payload: %s", exc)
        return json.dumps({"error": "invalid interaction payload"})

    channel_breakdown = _compute_channel_breakdown(channels)
    intent_breakdown = Counter(intents).most_common()

    behavior_summary = {
        "primary_channel": channel_breakdown[0]["channel"] if channel_breakdown else None,
        "channel_mix": channel_breakdown,
        "top_intents": intent_breakdown,
        "average_days_since_touch": mean(recency_days) if recency_days else None,
        "average_spend": mean(spend_values) if spend_values else None,
    }

    return json.dumps(behavior_summary)


behavior_tool = Tool(
    name="analyze_customer_behavior",
    func=analyze_customer_behavior,
    description="Summarize interaction patterns. Args: interactions (list of {channel, intent, days_since_interaction, spend}).",
)

__all__ = ["behavior_tool"]
