"""Dispatch recipes to the appropriate training entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .dpo import run_dpo
from .sft import run_sft


def detect_recipe_type(path: Path) -> str:
    payload = yaml.safe_load(path.read_text())
    recipe_type = payload.get("type")
    if recipe_type:
        return recipe_type
    if "dpo" in path.parts:
        return "dpo"
    if "sft" in path.parts:
        return "sft"
    raise ValueError(f"Unable to infer recipe type for {path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run a tuning recipe")
    parser.add_argument("recipe", type=Path, help="Path to recipe YAML")
    parser.add_argument("--no-mlflow", action="store_true", help="Disable MLflow logging")
    parser.add_argument("--eval-spec", type=Path, help="Optional eval spec to execute")
    parser.add_argument("--predictions", type=Path, help="Predictions JSONL for eval")
    args = parser.parse_args(argv)

    recipe_type = detect_recipe_type(args.recipe)

    if recipe_type == "sft":
        run_sft.main([
            str(args.recipe),
            *("--no-mlflow",) if args.no_mlflow else (),
            *(() if not args.eval_spec else ("--eval-spec", str(args.eval_spec))),
            *(() if not args.predictions else ("--predictions", str(args.predictions))),
        ])
    elif recipe_type == "dpo":
        run_dpo.main([
            str(args.recipe),
            *("--no-mlflow",) if args.no_mlflow else (),
            *(() if not args.eval_spec else ("--eval-spec", str(args.eval_spec))),
            *(() if not args.predictions else ("--predictions", str(args.predictions))),
        ])
    else:
        raise ValueError(f"Unsupported recipe type: {recipe_type}")


if __name__ == "__main__":
    main()
