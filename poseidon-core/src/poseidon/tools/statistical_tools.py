"""Tools for basic anomaly detection on numeric series."""

from __future__ import annotations

import logging

import json
from typing import Dict, List

from langchain_core.tools import Tool

from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def detect_zscore_anomalies(args: Dict[str, object]) -> str:
    values = args.get("values")
    if not isinstance(values, list) or not values:
        return json.dumps({"error": "values must be a non-empty list of numbers"})

    try:
        series = [float(v) for v in values]
    except (TypeError, ValueError):
        return json.dumps({"error": "values must be numeric"})

    threshold = float(args.get("threshold", 2.5))
    mean = sum(series) / len(series)
    variance = sum((x - mean) ** 2 for x in series) / len(series)
    std = variance ** 0.5
    if std == 0:
        return json.dumps({"anomalies": []})

    anomalies = []
    for idx, value in enumerate(series):
        z = abs((value - mean) / std)
        if z >= threshold:
            anomalies.append({"index": idx, "value": value, "zscore": z})

    return json.dumps({
        "mean": mean,
        "std": std,
        "threshold": threshold,
        "anomalies": anomalies,
    })


anomaly_detection_tool = Tool(
    name="detect_zscore_anomalies",
    func=detect_zscore_anomalies,
    description="Detect anomalies using z-score. Args: values (list[float]), threshold (float, optional).",
)

__all__ = ["anomaly_detection_tool"]
