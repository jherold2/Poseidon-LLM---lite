"""Backward-compatible shim for legacy imports.

All evaluation utilities now live under `tuning.eval`. Re-export the common
entrypoints so existing imports keep working while we migrate the codebase.
"""

from tuning.eval.metrics import (
    calculate_chain_precision,
    calculate_task_accuracy,
    log_metrics_to_langfuse,
    summarize_metrics,
)
from tuning.eval.runner import run_eval
from tuning.eval.validate_dpo import (
    evaluate_dpo_preferences,
    run_validation as run_dpo_validation,
)
from tuning.eval.validate_sft import (
    evaluate_sft_predictions,
    run_validation as run_sft_validation,
)

__all__ = [
    "calculate_chain_precision",
    "calculate_task_accuracy",
    "log_metrics_to_langfuse",
    "summarize_metrics",
    "run_eval",
    "evaluate_dpo_preferences",
    "run_dpo_validation",
    "evaluate_sft_predictions",
    "run_sft_validation",
]
