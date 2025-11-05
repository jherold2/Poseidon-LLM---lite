"""Category-level sales query helpers."""

from __future__ import annotations

import logging

import json
from typing import Dict, List, Tuple

from langchain_core.tools import Tool

from poseidon.tools.query_tools.utils import parse_time_range, validate_payload
from poseidon.utils.db_connect import run as db_run
from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def _to_dicts(rows: List[Tuple], columns: List[str]) -> List[Dict[str, object]]:
    return [dict(zip(columns, row)) for row in rows]


def query_sales_by_category(args: Dict[str, object]) -> str:
    """Aggregate sales by category within a time window.

    Expected args:
        time_range: optional ISO range or natural language window
        sales_channel: optional string filter
        limit: optional integer cap (defaults to 10)
    """

    error = validate_payload(
        args,
        optional={"time_range": (str,), "sales_channel": (str,), "limit": (int,)},
        allow_extra=False,
    )
    if error:
        return json.dumps({"error": error})

    time_range = args.get("time_range", "last 90 days")
    sales_channel = args.get("sales_channel")
    limit = args.get("limit", 10)
    if isinstance(limit, int) and limit <= 0:
        limit = 10

    try:
        start_date, end_date = parse_time_range(time_range)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    sql = [
        "SELECT category_level_2,",
        "       SUM(subtotal_taxable) AS net_sales,",
        "       SUM(gross_sales) AS gross_sales,",
        "       SUM(qty) AS total_units",
        "FROM cda_it_custom.fact_sales_mv",
        "WHERE order_date BETWEEN %s AND %s",
    ]
    params: List[object] = [start_date, end_date]

    if sales_channel:
        sql.append("  AND sales_channel = %s")
        params.append(sales_channel)

    sql.extend([
        "GROUP BY category_level_2",
        "ORDER BY net_sales DESC NULLS LAST",
    ])
    if limit:
        sql.append("LIMIT %s")
        params.append(limit)

    try:
        rows = db_run("\n".join(sql), tuple(params))
        data = _to_dicts(rows, ["category", "net_sales", "gross_sales", "total_units"]) if rows else []
        return json.dumps({
            "time_range": {"start": str(start_date), "end": str(end_date)},
            "sales_channel": sales_channel,
            "categories": data,
        })
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Category sales query failed: %s", exc)
        return json.dumps({"error": str(exc)})


category_sales_tool = Tool(
    name="query_sales_by_category",
    func=query_sales_by_category,
    description="Aggregate net sales by category. Args: time_range (str), sales_channel (str), limit (int).",
)

__all__ = ["category_sales_tool", "query_sales_by_category"]
