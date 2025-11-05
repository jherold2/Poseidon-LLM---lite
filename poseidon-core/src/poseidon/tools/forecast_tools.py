"""Simple forecasting utilities that operate on time-series histories."""

from __future__ import annotations

import logging

import json
from typing import Dict, List

from langchain_core.tools import Tool

from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def _linear_forecast(history: List[float], horizon: int) -> List[float]:
    n = len(history)
    if n == 0:
        return [0.0] * horizon
    if n == 1:
        return [history[0]] * horizon

    indices = list(range(n))
    mean_x = sum(indices) / n
    mean_y = sum(history) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(indices, history))
    denominator = sum((x - mean_x) ** 2 for x in indices) or 1
    slope = numerator / denominator
    intercept = mean_y - slope * mean_x

    forecasts = []
    for step in range(1, horizon + 1):
        x = n - 1 + step
        forecasts.append(intercept + slope * x)
    return forecasts


def forecast_metric(args: Dict[str, object]) -> str:
    history = args.get("history")
    horizon = int(args.get("horizon", 3))
    metric_name = args.get("metric")
    if not isinstance(history, list) or not history:
        return json.dumps({"error": "history must be a non-empty list of {period, value}"})

    try:
        values = [float(entry["value"]) for entry in history]
        periods = [entry.get("period") for entry in history]
    except (TypeError, KeyError, ValueError) as exc:
        logger.error("Invalid history payload: %s", exc)
        return json.dumps({"error": "invalid history entries"})

    forecast_values = _linear_forecast(values, horizon)
    payload = {
        "metric": metric_name,
        "history": history,
        "forecast": [
            {"step": idx + 1, "value": value}
            for idx, value in enumerate(forecast_values)
        ],
    }
    return json.dumps(payload)


forecast_tool = Tool(
    name="forecast_metric",
    func=forecast_metric,
    description="Forecast a metric using a simple linear trend. Args: history (list[{period,value}]), horizon (int), metric (str optional).",
)

__all__ = ["forecast_tool"]
