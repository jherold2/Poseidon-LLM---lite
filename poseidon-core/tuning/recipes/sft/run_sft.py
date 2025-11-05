"""Skeleton SFT training entrypoint that logs configuration to MLflow."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Mapping

import yaml

from tuning.eval import runner as eval_runner


logger = logging.getLogger(__name__)


def load_recipe(path: Path | str) -> Mapping:
    recipe_path = Path(path)
    payload = yaml.safe_load(recipe_path.read_text())
    if payload.get("type") not in {"sft", None}:
        raise ValueError(f"Recipe {recipe_path} is not an SFT recipe")
    payload.setdefault("type", "sft")
    return payload


def start_mlflow_run(recipe: Mapping, disable_mlflow: bool = False):
    try:
        import mlflow
    except ImportError:  # pragma: no cover - optional dependency
        mlflow = None

    if disable_mlflow or mlflow is None:
        class _Noop:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Noop()

    mlflow.set_experiment(recipe.get("logging", {}).get("mlflow_experiment", "poseidon-tuning"))
    return mlflow.start_run(run_name=f"sft::{recipe['name']}")


def run_training(recipe: Mapping) -> Mapping[str, float]:
    """Placeholder training loop for SFT.

    Replace this stub with integration to TRL/Transformers. The return value should
    contain evaluation metrics from the training run (e.g., final loss).
    """

    logger.info("Pretending to fine-tune %s", recipe.get("base_model"))
    logger.debug("Training hyperparameters: %s", recipe.get("hyperparameters", {}))

    # TODO: integrate real training pipeline
    return {"train_loss_final": 0.0}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Launch an SFT training run")
    parser.add_argument("recipe", type=Path, help="Path to SFT recipe YAML")
    parser.add_argument(
        "--eval-spec",
        type=Path,
        help="Optional eval spec to execute after training",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        help="Path to model predictions JSONL for post-training evaluation",
    )
    parser.add_argument("--no-mlflow", action="store_true", help="Disable MLflow logging")
    args = parser.parse_args(argv)

    recipe = load_recipe(args.recipe)
    logging.basicConfig(level=logging.INFO)

    with start_mlflow_run(recipe, disable_mlflow=args.no_mlflow):
        try:
            import mlflow
        except ImportError:  # pragma: no cover - optional dependency
            mlflow = None

        if mlflow and not args.no_mlflow:
            mlflow.log_dict(recipe, "recipes/sft_recipe.yaml")
            mlflow.set_tag("stage", "sft")

        metrics = run_training(recipe)
        if mlflow and not args.no_mlflow and metrics:
            mlflow.log_metrics(metrics)

        if args.eval_spec:
            if not args.predictions:
                parser.error("--predictions is required when --eval-spec is provided")
            eval_runner.run_eval(
                spec_path=args.eval_spec,
                predictions_path=args.predictions,
                enable_mlflow=not args.no_mlflow,
            )


if __name__ == "__main__":
    main()
