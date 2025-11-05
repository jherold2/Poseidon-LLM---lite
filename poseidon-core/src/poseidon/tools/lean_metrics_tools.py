"""LangChain tools for Lean observability summaries."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from poseidon.tools.registry import register_tool
from poseidon.utils.db_connect import run as db_run

_LEAN_SCHEMA = os.getenv("POSEIDON_LEAN_SCHEMA", "cedea_metrics")
_EVENT_TABLE = f"{_LEAN_SCHEMA}.event_log_unified"


def _ensure_dict(args: Any) -> Dict[str, Any]:
    if args is None:
        return {}
    if isinstance(args, dict):
        return args
    if isinstance(args, str) and args.strip():
        text = args.strip()
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        parsed: Dict[str, Any] = {}
        for part in text.split(","):
            if "=" in part:
                key, value = part.split("=", 1)
                parsed[key.strip()] = value.strip()
        if parsed:
            return parsed
        return {"query": text}
    return {}


def _serialize_rows(rows: List[tuple]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for source_tool, lean_category, total_events, improvement_events, avg_duration_ms in rows:
        payload.append(
            {
                "source_tool": source_tool,
                "lean_category": lean_category,
                "total_events": int(total_events or 0),
                "improvement_events": int(improvement_events or 0),
                "avg_duration_ms": float(avg_duration_ms or 0),
            }
        )
    return payload


@register_tool(
    name="lean_metric_summary",
    description=(
        "Summarise Lean telemetry across tools. Accepts JSON with optional keys: "
        "source_tool (str), lean_category (str), lookback_hours (int, default 24), limit (int, default 20)."
    ),
    tags=["lean", "observability"],
)
def lean_metric_summary_tool(args: Any | None = None) -> str:
    params = _ensure_dict(args)
    lookback_hours = max(int(params.get("lookback_hours", 24)), 0)
    limit = max(int(params.get("limit", 20)), 1)
    conditions = []
    sql_params: List[Any] = []

    if lookback_hours > 0:
        conditions.append("event_timestamp >= now() - (%s * INTERVAL '1 hour')")
        sql_params.append(lookback_hours)
    source_tool = params.get("source_tool")
    if source_tool:
        conditions.append("source_tool = %s")
        sql_params.append(source_tool)
    lean_category = params.get("lean_category")
    if lean_category:
        conditions.append("lean_category = %s")
        sql_params.append(lean_category)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""
        SELECT
            source_tool,
            lean_category,
            COUNT(*) AS total_events,
            SUM(CASE WHEN improvement_flag THEN 1 ELSE 0 END) AS improvement_events,
            AVG(duration_ms) AS avg_duration_ms
        FROM {_EVENT_TABLE}
        {where_clause}
        GROUP BY 1, 2
        ORDER BY total_events DESC
        LIMIT %s
    """
    sql_params.append(limit)
    rows = db_run(query, tuple(sql_params))
    payload = _serialize_rows(rows)
    response = {
        "filters": {
            "source_tool": source_tool,
            "lean_category": lean_category,
            "lookback_hours": lookback_hours,
        },
        "results": payload,
    }
    return json.dumps(response)


__all__ = ["lean_metric_summary_tool"]
