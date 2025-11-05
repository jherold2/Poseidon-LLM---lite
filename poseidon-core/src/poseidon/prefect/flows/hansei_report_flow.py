"""Prefect flow generating a weekly Hansei report and posting it to Teams."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Sequence

import requests
from prefect import flow, get_run_logger, task
from sqlalchemy import text

from poseidon.prefect.config import create_sqlalchemy_engine

TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")
TEMPLATE_PATH = Path(__file__).resolve().parents[6] / "reports" / "hansei_summary_template.md"


@task(name="fetch-andon-alerts")
def fetch_andon_alerts(days_back: int = 7) -> List[Dict[str, str]]:
    """Return raw Andon alerts from the analytics schema for the requested lookback period."""
    logger = get_run_logger()
    window_start = datetime.utcnow() - timedelta(days=days_back)
    engine = create_sqlalchemy_engine()
    query = text(
        """
        SELECT flow_name, category, severity, message, timestamp
        FROM analytics.andon_alerts
        WHERE timestamp >= :window_start
        ORDER BY timestamp DESC
        """
    )
    try:
        with engine.connect() as conn:
            rows = conn.execute(query, {"window_start": window_start}).mappings().all()
    except Exception as exc:  # pragma: no cover - defensive persistence guard
        logger.warning("Unable to load Andon alerts: %s", exc)
        return []
    logger.info("Fetched %d Andon alerts since %s", len(rows), window_start.isoformat())
    return [dict(row) for row in rows]


def _summarise_counts(values: Sequence[str]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for value in values:
        summary[value] = summary.get(value, 0) + 1
    return summary


@task(name="analyse-alerts")
def analyse_alerts(rows: List[Dict[str, str]]) -> Dict[str, object]:
    """Create a structured summary suitable for reporting."""
    if not rows:
        return {
            "summary": "✅ No Andon alerts recorded in the review window.",
            "category_counts": {},
            "severity_counts": {},
            "top_flows": [],
            "total": 0,
        }

    categories = _summarise_counts(row["category"] for row in rows)
    severities = _summarise_counts(row["severity"] for row in rows)
    flows = _summarise_counts(row["flow_name"] for row in rows)
    top_flows = sorted(flows.items(), key=lambda item: item[1], reverse=True)[:5]

    summary_lines = [
        f"**Total Alerts:** {len(rows)}",
        f"**Categories:** {', '.join(f'{cat} ({count})' for cat, count in categories.items())}",
        f"**Severities:** {', '.join(f'{sev} ({count})' for sev, count in severities.items())}",
        "**Top Flows:**",
        *[f"- {flow} ({count})" for flow, count in top_flows],
    ]
    summary = "\n".join(summary_lines)

    return {
        "summary": summary,
        "category_counts": categories,
        "severity_counts": severities,
        "top_flows": top_flows,
        "total": len(rows),
    }


def _render_template(analysis: Dict[str, object]) -> str:
    if TEMPLATE_PATH.exists():
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    else:  # pragma: no cover - fallback when template missing
        template = "Hansei Summary\nTotal Alerts: {{ total_alerts }}\n"

    category_section = "\n".join(
        f"- {name}: {count}"
        for name, count in analysis.get("category_counts", {}).items()
    ) or "No categories recorded"
    severity_section = "\n".join(
        f"- {name}: {count}"
        for name, count in analysis.get("severity_counts", {}).items()
    ) or "No severity data"
    top_flows_section = "\n".join(
        f"- {flow} ({count})" for flow, count in analysis.get("top_flows", [])
    ) or "No flow-level alerts"

    substitutions = {
        "report_date": datetime.utcnow().date().isoformat(),
        "total_alerts": analysis.get("total", 0),
        "category_section": category_section,
        "severity_section": severity_section,
        "top_flows_section": top_flows_section,
        "generated_at": datetime.utcnow().isoformat(),
    }
    for key, value in substitutions.items():
        template = template.replace(f"{{{{ {key} }}}}", str(value))
    return template


@task(name="build-hansei-card")
def build_teams_card(analysis: Dict[str, object]) -> dict:
    """Render a Teams card summarising the weekly Hansei insights."""
    summary_text = _render_template(analysis)
    facts: List[Dict[str, str]] = []

    if analysis["category_counts"]:
        category_text = ", ".join(
            f"{name} ({count})" for name, count in analysis["category_counts"].items()
        )
        facts.append({"name": "Categories", "value": category_text})
    if analysis["severity_counts"]:
        severity_text = ", ".join(
            f"{name} ({count})" for name, count in analysis["severity_counts"].items()
        )
        facts.append({"name": "Severities", "value": severity_text})

    card = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": "0078D7",
        "summary": "Hansei Weekly Report",
        "sections": [
            {
                "activityTitle": f"📊 Hansei Report ({datetime.utcnow().date().isoformat()})",
                "activitySubtitle": "Continuous improvement summary",
                "facts": facts,
                "text": summary_text,
            }
        ],
    }
    return card


@task(name="post-hansei-teams")
def post_to_teams(card: dict) -> None:
    """Post the Hansei report to the configured Teams channel, if available."""
    logger = get_run_logger()
    if not TEAMS_WEBHOOK_URL:
        logger.warning("TEAMS_WEBHOOK_URL is not configured; skipping Hansei Teams report.")
        return

    response = requests.post(
        TEAMS_WEBHOOK_URL,
        data=json.dumps(card),
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    if not response.ok:
        logger.error("Failed to post Hansei report to Teams: %s", response.text)
        response.raise_for_status()
    logger.info("Posted Hansei weekly report to Microsoft Teams.")


@flow(name="Hansei Weekly Report Flow", log_prints=False)
def hansei_weekly_report_flow(days_back: int = 7) -> None:
    """Generate and publish a Hansei reflection from recent Andon alerts."""
    rows = fetch_andon_alerts(days_back)
    analysis = analyse_alerts(rows)
    card = build_teams_card(analysis)
    post_to_teams(card)


__all__ = ["hansei_weekly_report_flow"]
