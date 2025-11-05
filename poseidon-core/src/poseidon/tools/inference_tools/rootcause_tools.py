"""Root cause analysis utilities for decomposing metric deltas."""

from __future__ import annotations

import logging

import json
from typing import Dict, List

from langchain_core.tools import Tool

from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def analyze_metric_delta(args: Dict[str, object]) -> str:
    previous = args.get("previous") or {}
    current = args.get("current") or {}
    metric = args.get("metric")
    top_n = int(args.get("top_n", 5))

    if not isinstance(previous, dict) or not isinstance(current, dict):
        return json.dumps({"error": "previous and current must be dictionaries"})

    contributions: List[Dict[str, object]] = []
    delta_total = 0.0
    for dimension, current_value in current.items():
        prev_value = float(previous.get(dimension, 0.0))
        curr_value = float(current_value)
        delta = curr_value - prev_value
        delta_total += delta
        contributions.append({
            "dimension": dimension,
            "previous": prev_value,
            "current": curr_value,
            "delta": delta,
        })

    contributions.sort(key=lambda x: abs(x["delta"]), reverse=True)
    payload = {
        "metric": metric,
        "delta_total": delta_total,
        "top_contributors": contributions[:top_n],
        "all_contributors": contributions,
    }
    return json.dumps(payload)


root_cause_tool = Tool(
    name="analyze_metric_delta",
    func=analyze_metric_delta,
    description="Break down metric changes by dimension. Args: previous (dict), current (dict), metric (str optional), top_n (int optional).",
)

__all__ = ["root_cause_tool"]
