"""Prefect flow for dispatching Andon alerts to Microsoft Teams."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Tuple

import requests
from prefect import flow, get_run_logger, task
from sqlalchemy import text

from poseidon.prefect.config import create_sqlalchemy_engine

TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")

ALERT_CATEGORIES: Dict[str, List[str]] = {
    "Data Quality": ["dbt test", "null value", "schema mismatch", "constraint", "duplicate"],
    "System Failure": ["flow failed", "timeout", "connection error", "retry exceeded", "database down"],
    "Performance": ["slow", "latency", "duration", "load", "throughput"],
    "Model Drift": ["langfuse drift", "mlflow drift", "accuracy drop", "f1 drop", "model degraded"],
    "LLM Inference": ["langchain", "llm", "agent", "embedding", "context length", "token limit"],
    "API Failure": ["fastapi", "http 5", "endpoint error", "invalid response"],
    "Security": ["unauthorized", "access denied", "permission", "token expired"],
    "Observability": ["missing log", "telemetry", "metric not found"],
    "Infra": ["disk full", "memory", "cpu", "pod crash", "container restart"],
    "Other": [],
}


def _classify_alert(message: str) -> str:
    lowered = message.lower()
    for category, keywords in ALERT_CATEGORIES.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "Other"


def _teams_theme(severity: str) -> str:
    severity_lower = severity.lower()
    if severity_lower == "critical":
        return "E81123"
    if severity_lower == "info":
        return "0078D7"
    return "FEE75C"


@task(name="format-andon-card")
def format_teams_message(flow_name: str, message: str, severity: str = "warning") -> Tuple[dict, str]:
    """Create a structured Teams message card and return it along with the detected category."""
    logger = get_run_logger()
    category = _classify_alert(message)
    theme_color = _teams_theme(severity)
    summary = f"⚙️ Prefect Andon Alert: {category}"

    card = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": theme_color,
        "summary": summary,
        "sections": [
            {
                "activityTitle": f"🚨 **{category.upper()} ALERT** in *{flow_name}*",
                "activitySubtitle": f"Severity: **{severity.upper()}**",
                "facts": [
                    {"name": "Timestamp", "value": datetime.utcnow().isoformat()},
                    {"name": "Flow", "value": flow_name},
                    {"name": "Category", "value": category},
                    {"name": "Severity", "value": severity.upper()},
                ],
                "text": message,
            }
        ],
    }
    logger.info("Prepared Teams card for %s alert", category)
    return card, category


@task(name="send-andon-teams")
def send_to_teams(card: dict) -> None:
    """Post the alert message to a Microsoft Teams webhook (if configured)."""
    logger = get_run_logger()
    if not TEAMS_WEBHOOK_URL:
        logger.warning("TEAMS_WEBHOOK_URL is not configured; skipping Teams notification.")
        return

    response = requests.post(
        TEAMS_WEBHOOK_URL,
        data=json.dumps(card),
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    if not response.ok:
        logger.error("Failed to post Andon alert to Teams: %s", response.text)
        response.raise_for_status()
    logger.info("Sent Andon alert to Microsoft Teams.")


@task(name="log-andon-alert")
def persist_alert(flow_name: str, category: str, severity: str, message: str) -> None:
    """Persist the alert in Postgres for future Hansei reporting."""
    logger = get_run_logger()
    engine = create_sqlalchemy_engine()
    insert_sql = text(
        """
        INSERT INTO analytics.andon_alerts (flow_name, category, severity, message, timestamp)
        VALUES (:flow_name, :category, :severity, :message, :timestamp)
        """
    )
    timestamp = datetime.utcnow()
    try:
        with engine.begin() as conn:
            conn.execute(
                insert_sql,
                {
                    "flow_name": flow_name,
                    "category": category,
                    "severity": severity.upper(),
                    "message": message,
                    "timestamp": timestamp,
                },
            )
    except Exception as exc:  # pragma: no cover - defensive persistence guard
        logger.warning("Failed to persist Andon alert: %s", exc)
    else:
        logger.info("Persisted Andon alert for %s at %s", flow_name, timestamp.isoformat())


@flow(name="Andon Alert Flow", log_prints=False)
def andon_alert_flow(flow_name: str, message: str, severity: str = "warning") -> None:
    """
    Dispatch an Andon alert:
    - format card
    - optionally send to Teams
    - persist for Hansei reporting
    """
    severity_normalised = severity.lower()
    card, category = format_teams_message(flow_name, message, severity_normalised)
    send_to_teams(card)
    persist_alert(flow_name, category, severity_normalised, message)


__all__ = ["andon_alert_flow"]
