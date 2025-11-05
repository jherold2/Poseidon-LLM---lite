"""Tasks for interacting with dbt metadata for MCP exports."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import yaml
from prefect import get_run_logger, task
from sqlalchemy import text

from poseidon.prefect.config import create_sqlalchemy_engine


def _load_yaml_files(paths: Iterable[Path]) -> List[Dict[str, object]]:
    payloads: List[Dict[str, object]] = []
    for path in paths:
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            payloads.append({"path": str(path), "payload": data})
        except Exception as exc:  # pragma: no cover - YAML parsing fallback
            payloads.append({"path": str(path), "error": str(exc), "payload": {}})
    return payloads


def _flatten_semantic_models(doc: Dict[str, object]) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    for semantic_model in doc.get("semantic_models", []) or []:
        entries.append(
            {
                "type": "semantic_model",
                "name": semantic_model.get("name"),
                "description": semantic_model.get("description"),
                "entities": semantic_model.get("entities"),
                "dimensions": semantic_model.get("dimensions"),
                "measures": semantic_model.get("measures"),
            }
        )
    return entries


def _flatten_metrics(doc: Dict[str, object]) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    for metric in doc.get("metrics", []) or []:
        entries.append(
            {
                "type": "metric",
                "name": metric.get("name"),
                "description": metric.get("description"),
                "label": metric.get("label"),
                "calculation_method": metric.get("calculation_method"),
                "expression": metric.get("expression"),
                "filter": metric.get("filter"),
                "type_params": metric.get("type_params"),
            }
        )
    return entries


@task(name="load-dbt-metadata")
def load_dbt_metadata(project_root: Path) -> List[Dict[str, object]]:
    """Read dbt semantic model and metrics definitions from YAML files."""
    logger = get_run_logger()
    semantic_paths = list(project_root.glob("models/semantic_models/**/*.yml")) + list(
        project_root.glob("models/semantic_models/**/*.yaml")
    )
    metric_paths = list(project_root.glob("models/metrics/**/*.yml")) + list(
        project_root.glob("models/metrics/**/*.yaml")
    )

    entries: List[Dict[str, object]] = []
    for record in _load_yaml_files(semantic_paths):
        payload = record.get("payload", {})
        entries.extend(
            {
                **item,
                "source_file": record["path"],
            }
            for item in _flatten_semantic_models(payload)
        )
    for record in _load_yaml_files(metric_paths):
        payload = record.get("payload", {})
        entries.extend(
            {
                **item,
                "source_file": record["path"],
            }
            for item in _flatten_metrics(payload)
        )

    logger.info("Loaded %d dbt metadata entries from %d files", len(entries), len(semantic_paths) + len(metric_paths))
    return entries


@task(name="persist-mcp-metadata")
def persist_mcp_metadata(entries: List[Dict[str, object]], schema: str = "lean_obs", table: str = "mcp_metadata") -> int:
    """Persist metric metadata records to Postgres."""
    if not entries:
        return 0
    logger = get_run_logger()
    engine = create_sqlalchemy_engine()
    insert_sql = text(
        f"""
        INSERT INTO {schema}.{table} (metric_type, name, description, source_file, payload_json, extracted_at)
        VALUES (:metric_type, :name, :description, :source_file, :payload_json, :extracted_at)
        ON CONFLICT (metric_type, name) DO UPDATE SET
            description = EXCLUDED.description,
            source_file = EXCLUDED.source_file,
            payload_json = EXCLUDED.payload_json,
            extracted_at = EXCLUDED.extracted_at
        """
    )
    now = datetime.utcnow()
    with engine.begin() as conn:
        for entry in entries:
            payload = dict(entry)
            metric_type = payload.pop("type", "metric")
            name = payload.get("name")
            description = payload.get("description")
            source_file = payload.pop("source_file", "")
            conn.execute(
                insert_sql,
                {
                    "metric_type": metric_type,
                    "name": name,
                    "description": description,
                    "source_file": source_file,
                    "payload_json": json.dumps(payload, default=str),
                    "extracted_at": now,
                },
            )
    logger.info("Persisted %d metadata entries into %s.%s", len(entries), schema, table)
    return len(entries)
