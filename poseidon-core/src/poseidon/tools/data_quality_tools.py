"""Data quality utilities for freshness and null-rate checks."""

from __future__ import annotations

import logging

import json
from typing import Dict

from poseidon.utils.db_connect import run as db_run
from poseidon.utils.logger_setup import setup_logging
from poseidon.tools.registry import register_tool

setup_logging()
logger = logging.getLogger(__name__)


@register_tool(
    name="check_table_freshness",
    description="Get most recent timestamp for a table. Args: table (str), timestamp_column (str).",
    version="1.0",
    tags=["data_quality"],
)
def check_table_freshness(args: Dict[str, str]) -> str:
    table = args.get("table")
    timestamp_column = args.get("timestamp_column")
    if not table or not timestamp_column:
        return json.dumps({"error": "table and timestamp_column are required"})
    try:
        query = f"SELECT MAX({timestamp_column}) FROM {table}"
        result = db_run(query)
        latest = result[0][0] if result else None
        if hasattr(latest, "isoformat"):
            latest = latest.isoformat()
        return json.dumps({
            "table": table,
            "timestamp_column": timestamp_column,
            "latest_timestamp": latest,
        })
    except Exception as exc:  # pragma: no cover
        logger.error("Freshness check failed for %s: %s", table, exc)
        return json.dumps({"error": str(exc)})


@register_tool(
    name="check_null_rate",
    description="Compute null rate for a column. Args: table (str), column (str), where (str optional).",
    version="1.0",
    tags=["data_quality"],
)
def check_null_rate(args: Dict[str, str]) -> str:
    table = args.get("table")
    column = args.get("column")
    where = args.get("where")
    if not table or not column:
        return json.dumps({"error": "table and column are required"})
    try:
        where_clause = f"WHERE {where}" if where else ""
        total_query = f"SELECT COUNT(1) FROM {table} {where_clause}"
        null_condition = f"{where} AND {column} IS NULL" if where else f"{column} IS NULL"
        null_query = f"SELECT COUNT(1) FROM {table} WHERE {null_condition}"
        total = db_run(total_query)[0][0]
        nulls = db_run(null_query)[0][0]
        rate = nulls / total if total else None
        return json.dumps({
            "table": table,
            "column": column,
            "where": where,
            "total_rows": total,
            "null_rows": nulls,
            "null_rate": rate,
        })
    except Exception as exc:  # pragma: no cover
        logger.error("Null rate check failed for %s.%s: %s", table, column, exc)
        return json.dumps({"error": str(exc)})


freshness_tool = check_table_freshness
null_rate_tool = check_null_rate

__all__ = ["freshness_tool", "null_rate_tool"]
