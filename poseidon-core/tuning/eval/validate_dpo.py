"""Evaluation helpers for Direct Preference Optimisation (DPO)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from datasets import Dataset, load_dataset

from .metrics import (
    calculate_chain_precision,
    calculate_task_accuracy,
    log_metrics_to_langfuse,
    log_metrics_to_mlflow,
    summarize_metrics,
)


logger = logging.getLogger(__name__)


def load_preference_dataset(path: Path | str) -> Dataset:
    dataset = load_dataset("json", data_files=str(path), split="train")
    logger.debug("Loaded %d preference pairs from %s", len(dataset), path)
    return dataset


def extract_preference_pairs(dataset: Dataset) -> tuple[list[Sequence[Mapping]], list[Sequence[Mapping]]]:
    """Return chosen/rejected tool chains for comparison."""

    chosen, rejected = [], []
    for record in dataset:
        chosen_chain = record.get("chosen") or []
        rejected_chain = record.get("rejected") or []
        if isinstance(chosen_chain, str):
            chosen_chain = json.loads(chosen_chain)
        if isinstance(rejected_chain, str):
            rejected_chain = json.loads(rejected_chain)
        chosen.append(chosen_chain)
        rejected.append(rejected_chain)
    return chosen, rejected


def evaluate_dpo_preferences(
    predictions: Iterable[Mapping],
    chosen_chains: Sequence[Sequence[Mapping]],
) -> dict[str, float]:
    """Compare predicted chains with the preferred (chosen) references."""

    predicted = [pred.get("response") or [] for pred in predictions]
    metrics = {
        "preference_match_rate": calculate_task_accuracy(chosen_chains, predicted),
        "preference_precision": calculate_chain_precision(chosen_chains, predicted),
    }
    return metrics


def run_validation(
    predictions: Iterable[Mapping],
    validation_path: Path | str,
    mlflow_prefix: str | None = None,
) -> dict[str, float]:
    dataset = load_preference_dataset(validation_path)
    chosen, _ = extract_preference_pairs(dataset)
    metrics = evaluate_dpo_preferences(predictions, chosen)
    payload = summarize_metrics(metrics, prefix=mlflow_prefix)
    log_metrics_to_mlflow(payload)
    log_metrics_to_langfuse(
        payload,
        host=os.getenv("LANGFUSE_HOST"),
        project_id=os.getenv("LANGFUSE_PROJECT_ID"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    )
    logger.info("DPO validation metrics: %s", metrics)
    return metrics


__all__ = [
    "load_preference_dataset",
    "extract_preference_pairs",
    "evaluate_dpo_preferences",
    "run_validation",
]
