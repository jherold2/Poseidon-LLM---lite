"""Tools for assembling executive-ready briefs from metric snapshots."""

from __future__ import annotations

import logging

import json
from typing import Dict, List

from langchain_core.tools import Tool

from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def generate_executive_brief(args: Dict[str, object]) -> str:
    metrics = args.get("metrics") or []
    highlights = []
    risks = []
    opportunities = []

    if not isinstance(metrics, list) or not metrics:
        return json.dumps({"error": "metrics must be a non-empty list of {name, value}"})

    for entry in metrics:
        name = entry.get("name")
        value = entry.get("value")
        change = entry.get("change")
        summary = f"{name}: {value}"
        if change is not None:
            summary += f" ({'+' if change >= 0 else ''}{change})"
        if entry.get("status") == "risk":
            risks.append(summary)
        elif entry.get("status") == "opportunity":
            opportunities.append(summary)
        else:
            highlights.append(summary)

    narrative_parts: List[str] = []
    if highlights:
        narrative_parts.append("Key Highlights: " + "; ".join(highlights))
    if opportunities:
        narrative_parts.append("Opportunities: " + "; ".join(opportunities))
    if risks:
        narrative_parts.append("Risks: " + "; ".join(risks))

    narrative = args.get("summary") or " ".join(narrative_parts)
    charts = args.get("charts") or []

    brief = {
        "narrative": narrative.strip(),
        "highlights": highlights,
        "opportunities": opportunities,
        "risks": risks,
        "charts": charts,
    }
    return json.dumps(brief)


executive_brief_tool = Tool(
    name="generate_executive_brief",
    func=generate_executive_brief,
    description="Create an executive summary from metric snapshots. Args: metrics (list), summary (str optional), charts (list optional).",
)

__all__ = ["executive_brief_tool"]
