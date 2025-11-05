"""Evaluation harness entrypoints for tuning pipelines."""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

import yaml

from . import metrics as metric_utils
from . import validate_dpo, validate_sft


logger = logging.getLogger(__name__)


@dataclass
class EvalSpec:
    name: str
    task_type: str
    dataset_path: Path
    suite: str | None = None
    scorers: list[str] | None = None
    metadata: Mapping[str, object] | None = None

    @classmethod
    def from_path(cls, path: Path) -> "EvalSpec":
        payload = yaml.safe_load(path.read_text())
        dataset_path = Path(payload["dataset"])
        if not dataset_path.is_absolute():
            dataset_path = (path.parent / dataset_path).resolve()
        return cls(
            name=payload["name"],
            task_type=payload["task_type"],
            dataset_path=dataset_path,
            suite=payload.get("suite"),
            scorers=payload.get("scorers"),
            metadata=payload.get("metadata"),
        )


@dataclass
class EvalResult:
    spec: EvalSpec
    metrics: Mapping[str, float]
    output_dir: Path


def load_predictions(path: Path | str) -> list[Mapping]:
    path = Path(path)
    entries: list[Mapping] = []
    with path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            entries.append(json.loads(line))
    logger.debug("Loaded %d predictions from %s", len(entries), path)
    return entries


def ensure_output_dir(root: Path, spec_name: str) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_dir = root / f"{timestamp}_{spec_name}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def run_eval(
    spec_path: Path | str,
    predictions_path: Path | str | None,
    runs_root: Path | str = Path("tuning/runs"),
    enable_mlflow: bool = True,
    enable_langfuse: bool = True,
) -> EvalResult:
    spec_path = Path(spec_path)
    spec = EvalSpec.from_path(spec_path)
    runs_root = Path(runs_root)
    output_dir = ensure_output_dir(runs_root, spec.name)

    if enable_mlflow:
        _start_mlflow_run_if_needed(spec)

    trace_id = None
    if enable_langfuse:
        trace_id = _start_langfuse_trace(spec)

    task_type = spec.task_type.lower()
    if task_type in {"sft", "dpo"}:
        if predictions_path is None:
            raise ValueError(f"predictions_path is required for task type {task_type}")
        predictions = load_predictions(predictions_path)
    else:
        predictions = []

    if task_type == "sft":
        metrics = validate_sft.run_validation(
            predictions,
            spec.dataset_path,
            mlflow_prefix=spec.name,
        )
    elif task_type == "dpo":
        metrics = validate_dpo.run_validation(
            predictions,
            spec.dataset_path,
            mlflow_prefix=spec.name,
        )
    elif task_type == "perf":
        metrics = _load_perf_metrics(spec.dataset_path)
        payload = metric_utils.summarize_metrics(metrics, prefix=spec.name)
        if enable_mlflow:
            metric_utils.log_metrics_to_mlflow(payload)
        metric_utils.log_metrics_to_langfuse(
            payload,
            host=os.getenv("LANGFUSE_HOST"),
            project_id=os.getenv("LANGFUSE_PROJECT_ID"),
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            trace_id=trace_id,
        )
    else:
        raise ValueError(f"Unsupported task_type '{spec.task_type}' in {spec_path}")

    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True))

    spec_snapshot = output_dir / "eval_spec.yaml"
    spec_snapshot.write_text(spec_path.read_text())

    if enable_mlflow:
        _log_artifacts_to_mlflow(metrics_path, spec_snapshot, spec)

    if enable_langfuse:
        _log_metrics_to_langfuse(
            metrics,
            spec,
            trace_id=trace_id,
        )

    logger.info("Saved evaluation results to %s", output_dir)
    return EvalResult(spec=spec, metrics=metrics, output_dir=output_dir)


def _load_perf_metrics(path: Path) -> Mapping[str, float]:
    raw_text = path.read_text().strip()
    if not raw_text:
        return {}
    try:
        payload = json.loads(raw_text)
        if isinstance(payload, dict):
            return {k: float(v) for k, v in payload.items()}
    except json.JSONDecodeError:
        pass

    # Fallback to JSONL (take first line)
    with path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                return {k: float(v) for k, v in obj.items()}
    raise ValueError(f"Unable to parse performance metrics from {path}")


def _start_mlflow_run_if_needed(spec: EvalSpec) -> None:
    try:
        import mlflow
    except ImportError:  # pragma: no cover - optional dependency
        logger.debug("MLflow not available; skipping run creation")
        return

    if mlflow.active_run() is not None:
        return

    mlflow.start_run(run_name=f"eval::{spec.name}")
    mlflow.set_tag("eval_spec", spec.name)
    if spec.metadata:
        for key, value in spec.metadata.items():
            mlflow.set_tag(f"eval_meta.{key}", value)


def _log_artifacts_to_mlflow(metrics_file: Path, spec_file: Path, spec: EvalSpec) -> None:
    try:
        import mlflow
    except ImportError:  # pragma: no cover - optional dependency
        return

    mlflow.log_artifact(str(metrics_file), artifact_path=f"eval/{spec.name}")
    mlflow.log_artifact(str(spec_file), artifact_path=f"eval/{spec.name}")


def _start_langfuse_trace(spec: EvalSpec) -> str | None:
    host = os.getenv("LANGFUSE_HOST")
    project_id = os.getenv("LANGFUSE_PROJECT_ID")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not all((host, project_id, public_key, secret_key)):
        logger.debug("Langfuse credentials missing; skipping trace creation")
        return None

    import requests

    payload = {
        "projectId": project_id,
        "name": f"eval::{spec.name}",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "metadata": spec.metadata or {},
    }
    response = requests.post(
        f"{host.rstrip('/')}/api/public/traces",
        json=payload,
        auth=(public_key, secret_key),
        timeout=10,
    )
    try:
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to create Langfuse trace for %s: %s", spec.name, exc)
        return None
    data = response.json()
    return data.get("id")


def _log_metrics_to_langfuse(metrics: Mapping[str, float], spec: EvalSpec, trace_id: str | None) -> None:
    metric_utils.log_metrics_to_langfuse(
        metric_utils.summarize_metrics(metrics, prefix=spec.name),
        host=os.getenv("LANGFUSE_HOST"),
        project_id=os.getenv("LANGFUSE_PROJECT_ID"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        trace_id=trace_id,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run an evaluation spec against predictions")
    parser.add_argument("spec", type=Path, help="Path to eval spec YAML")
    parser.add_argument(
        "predictions",
        type=Path,
        nargs="?",
        help="Path to JSONL predictions (omit for perf-only specs)",
    )
    parser.add_argument(
        "--no-mlflow",
        action="store_true",
        help="Disable MLflow logging even if the package is available.",
    )
    parser.add_argument(
        "--no-langfuse",
        action="store_true",
        help="Disable Langfuse logging even if the service is available.",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("tuning/runs"),
        help="Directory where eval run outputs should be written.",
    )
    args = parser.parse_args(argv)

    run_eval(
        spec_path=args.spec,
        predictions_path=args.predictions,
        runs_root=args.runs_root,
        enable_mlflow=not args.no_mlflow,
        enable_langfuse=not args.no_langfuse,
    )


if __name__ == "__main__":
    main()
