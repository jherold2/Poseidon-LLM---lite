"""Reusable metric helpers for the tuning evaluation harness."""

from __future__ import annotations

import json
import logging
from typing import Mapping, MutableMapping, Sequence


logger = logging.getLogger(__name__)


def calculate_task_accuracy(
    gold_chains: Sequence[Sequence[Mapping]],
    predicted_chains: Sequence[Sequence[Mapping]],
) -> float:
    """Compute exact-match accuracy over tool chains."""

    if not gold_chains:
        return 0.0

    correct = 0
    for gold, pred in zip(gold_chains, predicted_chains):
        if json.dumps(gold, sort_keys=True) == json.dumps(pred, sort_keys=True):
            correct += 1
    return correct / len(gold_chains)


def calculate_chain_precision(
    gold_chains: Sequence[Sequence[Mapping]],
    predicted_chains: Sequence[Sequence[Mapping]],
) -> float:
    """Toy precision metric comparing flattened tool names."""

    predicted_tools = _flatten_tools(predicted_chains)
    gold_tools = set(_flatten_tools(gold_chains))
    if not predicted_tools:
        return 0.0
    matches = sum(1 for tool in predicted_tools if tool in gold_tools)
    return matches / len(predicted_tools)


def _flatten_tools(chains: Sequence[Sequence[Mapping]]) -> list[str]:
    flattened: list[str] = []
    for chain in chains:
        for step in chain:
            tool_name = step.get("tool")
            if isinstance(tool_name, str):
                flattened.append(tool_name)
    return flattened


def summarize_metrics(metrics: Mapping[str, float], prefix: str | None = None) -> Mapping[str, float]:
    """Attach optional prefix for downstream logging systems."""

    if not prefix:
        return dict(metrics)
    namespaced: MutableMapping[str, float] = {}
    for key, value in metrics.items():
        namespaced[f"{prefix}/{key}"] = value
    return namespaced


def log_metrics_to_mlflow(metrics: Mapping[str, float], step: int | None = None) -> None:
    """Best-effort logging of metrics to MLflow if it is installed."""

    if not metrics:
        return

    try:
        import mlflow
    except ImportError:  # pragma: no cover - optional dependency
        logger.debug("MLflow not installed; skipping metric logging")
        return

    clean_metrics = {k: float(v) for k, v in metrics.items()}
    mlflow.log_metrics(clean_metrics, step=step)


def log_metrics_to_langfuse(
    metrics: Mapping[str, float],
    *,
    host: str | None = None,
    project_id: str | None = None,
    public_key: str | None = None,
    secret_key: str | None = None,
    trace_id: str | None = None,
) -> None:
    """Best-effort logging of metrics to Langfuse via the public metrics API."""

    if not metrics:
        return

    host = (host or "").rstrip("/") or None
    project_id = project_id or None
    public_key = public_key or None
    secret_key = secret_key or None
    if not all((host, project_id, public_key, secret_key)):
        logger.debug("Langfuse credentials incomplete; skipping metric logging")
        return

    clean_metrics = {k: float(v) for k, v in metrics.items()}

    import requests

    for name, value in clean_metrics.items():
        payload = {
            "projectId": project_id,
            "name": name,
            "value": value,
        }
        if trace_id:
            payload["traceId"] = trace_id

        response = requests.post(
            f"{host}/api/public/metrics",
            json=payload,
            auth=(public_key, secret_key),
            timeout=10,
        )
        try:
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to log Langfuse metric %s: %s", name, exc)


__all__ = [
    "calculate_task_accuracy",
    "calculate_chain_precision",
    "summarize_metrics",
    "log_metrics_to_mlflow",
    "log_metrics_to_langfuse",
]
