"""CI helper to execute evaluation specs and enforce gate compliance."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from tuning.eval import gate_checker, runner
from tuning.eval.gate_checker import _find_latest_metrics, _load_metrics


logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run eval specs and check gates")
    parser.add_argument("--gate", type=Path, default=Path("tuning/gates/standard_v1.yaml"))
    parser.add_argument(
        "--spec",
        action="append",
        default=[],
        help="Run an eval spec prior to gating. Format: path/to/spec.yaml=path/to/predictions.jsonl",
    )
    parser.add_argument("--runs-root", type=Path, default=Path("tuning/runs"))
    parser.add_argument("--no-mlflow", action="store_true", help="Disable MLflow logging")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)

    metrics_map: dict[str, dict[str, float]] = {}
    for entry in args.spec:
        if "=" not in entry:
            parser.error("--spec entries must be spec=predictions")
        spec_path, predictions_path = entry.split("=", 1)
        result = runner.run_eval(
            spec_path=Path(spec_path),
            predictions_path=Path(predictions_path),
            runs_root=args.runs_root,
            enable_mlflow=not args.no_mlflow,
        )
        metrics_map[result.spec.name] = dict(result.metrics)

    gate_spec = gate_checker.GateSpec.from_path(args.gate)

    for check in gate_spec.checks:
        if check.eval_spec in metrics_map:
            continue
        metrics_path = _find_latest_metrics(args.runs_root, check.eval_spec)
        if metrics_path is None:
            logger.warning("No metrics found for spec %s", check.eval_spec)
            continue
        metrics_map[check.eval_spec] = dict(_load_metrics(metrics_path))

    verdict = gate_checker.evaluate_gate(gate_spec, metrics_map)
    if not verdict.passed:
        for failure in verdict.failures:
            logger.error(failure)
        return 1

    logger.info("Gate %s PASSED", gate_spec.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
