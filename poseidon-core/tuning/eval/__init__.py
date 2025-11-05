"""Evaluation package for the tuning pipeline."""

from .metrics import (
    calculate_chain_precision,
    calculate_task_accuracy,
    log_metrics_to_langfuse,
    log_metrics_to_mlflow,
    summarize_metrics,
)
from .runner import EvalResult, EvalSpec, run_eval
from .validate_dpo import (
    evaluate_dpo_preferences,
    extract_preference_pairs,
    load_preference_dataset,
    run_validation as run_dpo_validation,
)
from .validate_sft import (
    evaluate_sft_predictions,
    extract_gold_chains,
    load_reference_dataset,
    run_validation as run_sft_validation,
)

__all__ = [
    "calculate_chain_precision",
    "calculate_task_accuracy",
    "log_metrics_to_langfuse",
    "log_metrics_to_mlflow",
    "summarize_metrics",
    "EvalResult",
    "EvalSpec",
    "run_eval",
    "evaluate_dpo_preferences",
    "extract_preference_pairs",
    "load_preference_dataset",
    "run_dpo_validation",
    "evaluate_sft_predictions",
    "extract_gold_chains",
    "load_reference_dataset",
    "run_sft_validation",
]
