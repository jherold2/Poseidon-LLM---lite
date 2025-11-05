"""Fraud and compliance anomaly detection tools."""

from __future__ import annotations

import logging

import json
from datetime import datetime
from typing import Dict, List

from langchain_core.tools import Tool

from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


SUSPICIOUS_JOURNAL_TYPES = {"misc",
                             "entry"}


def detect_journal_anomalies(args: Dict[str, object]) -> str:
    entries = args.get("entries") or []
    if not isinstance(entries, list) or not entries:
        return json.dumps({"error": "entries must be a non-empty list"})

    threshold = float(args.get("amount_threshold", 1_000_000))
    anomalies: List[Dict[str, object]] = []
    for entry in entries:
        try:
            amount = abs(float(entry.get("amount", 0)))
            move_type = str(entry.get("move_type", "")).lower()
            created_at = entry.get("timestamp")
            is_weekend = False
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at)
                    is_weekend = dt.weekday() >= 5
                except ValueError:
                    pass
            suspicious = amount >= threshold or move_type in SUSPICIOUS_JOURNAL_TYPES or is_weekend
            if suspicious:
                anomalies.append({
                    "move_name": entry.get("move_name"),
                    "amount": amount,
                    "move_type": move_type,
                    "timestamp": created_at,
                    "flags": {
                        "amount_threshold": amount >= threshold,
                        "suspicious_type": move_type in SUSPICIOUS_JOURNAL_TYPES,
                        "weekend_posting": is_weekend,
                    }
                })
        except Exception as exc:
            logger.warning("Skipping malformed journal entry: %s", exc)

    return json.dumps({"anomalies": anomalies, "total_entries": len(entries)})


fraud_detection_tool = Tool(
    name="detect_journal_anomalies",
    func=detect_journal_anomalies,
    description="Identify suspicious journal entries. Args: entries (list of dict), amount_threshold (float optional).",
)

__all__ = ["fraud_detection_tool"]
