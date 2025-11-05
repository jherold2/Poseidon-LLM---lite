"""Specialised evaluation helpers for supervised fine-tuning (SFT)."""

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


def load_reference_dataset(path: Path | str) -> Dataset:
    """Load the canonical SFT validation split."""

    dataset = load_dataset("json", data_files=str(path), split="train")
    logger.debug("Loaded %d validation examples from %s", len(dataset), path)
    return dataset


def extract_gold_chains(dataset: Dataset) -> list[Sequence[Mapping]]:
    """Return the expected tool chains from the validation dataset."""

    gold: list[Sequence[Mapping]] = []
    for example in dataset:
        chain = example.get("gold_chain") or example.get("response") or []
        if isinstance(chain, str):
            chain = json.loads(chain)
        gold.append(chain)
    return gold


def evaluate_sft_predictions(
    predictions: Iterable[Mapping],
    gold_chains: Sequence[Sequence[Mapping]],
) -> dict[str, float]:
    """Compute core SFT validation metrics given predictions and gold chains."""

    predicted = [pred.get("response") or pred.get("chain") or [] for pred in predictions]
    metrics = {
        "chain_accuracy": calculate_task_accuracy(gold_chains, predicted),
        "chain_precision": calculate_chain_precision(gold_chains, predicted),
    }
    return metrics


def run_validation(
    predictions: Iterable[Mapping],
    validation_path: Path | str,
    mlflow_prefix: str | None = None,
) -> dict[str, float]:
    """Validate predictions against the reference set and log to MLflow/Langfuse."""

    dataset = load_reference_dataset(validation_path)
    gold_chains = extract_gold_chains(dataset)
    metrics = evaluate_sft_predictions(predictions, gold_chains)
    payload = summarize_metrics(metrics, prefix=mlflow_prefix)
    log_metrics_to_mlflow(payload)
    log_metrics_to_langfuse(
        payload,
        host=os.getenv("LANGFUSE_HOST"),
        project_id=os.getenv("LANGFUSE_PROJECT_ID"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    )
    logger.info("SFT validation metrics: %s", metrics)
    return metrics


__all__ = [
    "load_reference_dataset",
    "extract_gold_chains",
    "evaluate_sft_predictions",
    "run_validation",
]
