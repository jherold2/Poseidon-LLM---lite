"""Gate evaluation utilities to enforce release criteria."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import yaml


logger = logging.getLogger(__name__)


@dataclass
class MetricThreshold:
    metric: str
    minimum: float | None = None
    maximum: float | None = None

    def passes(self, value: float) -> bool:
        if self.minimum is not None and value < self.minimum:
            return False
        if self.maximum is not None and value > self.maximum:
            return False
        return True


@dataclass
class GateCheck:
    name: str
    eval_spec: str
    thresholds: list[MetricThreshold]


@dataclass
class GateSpec:
    name: str
    description: str | None
    checks: list[GateCheck]

    @classmethod
    def from_path(cls, path: Path) -> "GateSpec":
        payload = yaml.safe_load(path.read_text())
        gate_data = payload.get("gate") or payload
        checks: list[GateCheck] = []
        for check_payload in gate_data["checks"]:
            thresholds = []
            for metric_name, bounds in check_payload["metrics"].items():
                thresholds.append(
                    MetricThreshold(
                        metric=metric_name,
                        minimum=bounds.get("min"),
                        maximum=bounds.get("max"),
                    )
                )
            checks.append(
                GateCheck(
                    name=check_payload["name"],
                    eval_spec=check_payload["eval_spec"],
                    thresholds=thresholds,
                )
            )
        return cls(
            name=gate_data["name"],
            description=gate_data.get("description"),
            checks=checks,
        )


@dataclass
class GateVerdict:
    passed: bool
    failures: list[str]


def evaluate_gate(spec: GateSpec, metrics_by_spec: Mapping[str, Mapping[str, float]]) -> GateVerdict:
    failures: list[str] = []
    for check in spec.checks:
        metrics = metrics_by_spec.get(check.eval_spec)
        if metrics is None:
            failures.append(f"Missing metrics for spec '{check.eval_spec}'")
            continue
        for threshold in check.thresholds:
            if threshold.metric not in metrics:
                failures.append(
                    f"Spec '{check.eval_spec}' missing metric '{threshold.metric}' for gate '{check.name}'"
                )
                continue
            value = metrics[threshold.metric]
            if not threshold.passes(value):
                bound_desc = []
                if threshold.minimum is not None:
                    bound_desc.append(f"min {threshold.minimum}")
                if threshold.maximum is not None:
                    bound_desc.append(f"max {threshold.maximum}")
                failures.append(
                    f"Gate '{check.name}' failed: metric '{threshold.metric}'={value} (expected {'/'.join(bound_desc)})"
                )
    return GateVerdict(passed=not failures, failures=failures)


def _load_metrics(path: Path) -> Mapping[str, float]:
    with path.open() as handle:
        return json.load(handle)


def _find_latest_metrics(runs_root: Path, spec_name: str) -> Path | None:
    pattern = f"*_{spec_name}"
    candidates = sorted(runs_root.glob(pattern))
    candidates = [cand for cand in candidates if (cand / "metrics.json").exists()]
    return candidates[-1] / "metrics.json" if candidates else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check eval gate compliance")
    parser.add_argument("gate", type=Path, help="Path to gate spec YAML")
    parser.add_argument(
        "--metric",
        action="append",
        default=[],
        help="Explicit metrics mapping in the form spec_name=path/to/metrics.json",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("tuning/runs"),
        help="Directory to search for latest metrics when --metric is not supplied.",
    )
    args = parser.parse_args(argv)

    gate_spec = GateSpec.from_path(args.gate)

    metrics_by_spec: dict[str, Mapping[str, float]] = {}
    manual_mappings = {}
    for entry in args.metric:
        if "=" not in entry:
            parser.error("--metric entries must be spec=path")
        spec_name, metric_path = entry.split("=", 1)
        manual_mappings[spec_name] = Path(metric_path)

    for check in gate_spec.checks:
        if check.eval_spec in manual_mappings:
            metrics_path = manual_mappings[check.eval_spec]
        else:
            metrics_path = _find_latest_metrics(args.runs_root, check.eval_spec)
        if metrics_path is None:
            logger.warning("No metrics found for spec %s", check.eval_spec)
            continue
        metrics_by_spec[check.eval_spec] = _load_metrics(metrics_path)

    verdict = evaluate_gate(gate_spec, metrics_by_spec)

    if verdict.passed:
        logger.info("Gate %s PASSED", gate_spec.name)
        return 0

    logger.error("Gate %s FAILED", gate_spec.name)
    for failure in verdict.failures:
        logger.error(failure)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
