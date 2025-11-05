"""Logistics-focused LangChain tools for shipment visibility."""

from __future__ import annotations

import logging

import json
from typing import Dict, List

from langchain_core.tools import Tool

from poseidon.utils.db_connect import run as db_run
from poseidon.tools.query_tools.utils import parse_time_range
from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def _to_json(rows: List[tuple], columns: List[str]) -> str:
    mapped = [dict(zip(columns, row)) for row in rows]
    return json.dumps(mapped, default=str)


def query_recent_shipments(args: Dict[str, str]) -> str:
    """Fetch recent stock moves (shipments) filtered by optional parameters."""
    time_range = args.get("time_range", "2024")
    start_date, end_date = parse_time_range(time_range)
    so_number = args.get("so_number")
    product_id = args.get("product_id")
    warehouse = args.get("warehouse")

    columns = [
        "move_reference",
        "picking_type",
        "move_status",
        "date_completed",
        "source_warehouse",
        "destination_warehouse",
        "product_id",
        "qty",
    ]

    where_clauses = ["date_completed BETWEEN %s AND %s"]
    params: List[str] = [start_date, end_date]

    if so_number:
        where_clauses.append("move_reference = %s")
        params.append(so_number)
    if product_id:
        where_clauses.append("product_id = %s")
        params.append(product_id)
    if warehouse:
        where_clauses.append("(source_warehouse = %s OR destination_warehouse = %s)")
        params.extend([warehouse, warehouse])

    where_sql = " AND ".join(where_clauses)
    query = (
        "SELECT move_reference, picking_type, move_status, date_completed, "
        "source_warehouse, destination_warehouse, product_id, qty "
        "FROM cda_it_custom.fact_stock_move "
        f"WHERE {where_sql} ORDER BY date_completed DESC LIMIT 50"
    )

    try:
        rows = db_run(query, tuple(params))
        return _to_json(rows, columns)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Shipment query failed: %s", exc)
        return json.dumps({"error": str(exc)})


logistics_shipments_tool = Tool(
    name="query_recent_shipments",
    func=query_recent_shipments,
    description=(
        "Retrieve recent stock moves (shipments). Args: time_range ('YYYY' or 'YYYY-MM-DD to YYYY-MM-DD'), "
        "so_number (str, optional), product_id (str, optional), warehouse (str, optional)."
    ),
)


def query_inventory_flow_positions(args: Dict[str, str]) -> str:
    """Summarise transit/pre/post production inventory balances over time."""

    time_range = args.get("time_range", "2024")
    start_date, end_date = parse_time_range(time_range)
    warehouse = args.get("warehouse")
    product_id = args.get("product_id")

    columns = [
        "movement_date",
        "warehouse",
        "transit_balance_qty",
        "pre_production_balance_qty",
        "post_production_balance_qty",
        "negative_balance_qty",
    ]

    where_clauses = ["date BETWEEN %s AND %s"]
    params: List[str] = [start_date, end_date]

    if warehouse:
        where_clauses.append(
            "(base_warehouse = %s OR destination_warehouse = %s OR source_warehouse = %s)"
        )
        params.extend([warehouse, warehouse, warehouse])
    if product_id:
        where_clauses.append("product_id = %s")
        params.append(product_id)

    where_sql = " AND ".join(where_clauses)
    query = f"""
        SELECT
            date::date AS movement_date,
            coalesce(base_warehouse, destination_warehouse, source_warehouse) AS warehouse,
            SUM(CASE
                    WHEN coalesce(destination_location, '') ILIKE '%%Transit%%'
                      OR coalesce(source_location, '') ILIKE '%%Transit%%'
                      OR coalesce(base_location, '') ILIKE '%%Transit%%'
                    THEN balance_qty ELSE 0 END) AS transit_balance_qty,
            SUM(CASE
                    WHEN coalesce(destination_location, '') ILIKE '%%Pre-Production%%'
                      OR coalesce(source_location, '') ILIKE '%%Pre-Production%%'
                      OR coalesce(base_location, '') ILIKE '%%Pre-Production%%'
                    THEN balance_qty ELSE 0 END) AS pre_production_balance_qty,
            SUM(CASE
                    WHEN coalesce(destination_location, '') ILIKE '%%Post-Production%%'
                      OR coalesce(source_location, '') ILIKE '%%Post-Production%%'
                      OR coalesce(base_location, '') ILIKE '%%Post-Production%%'
                    THEN balance_qty ELSE 0 END) AS post_production_balance_qty,
            SUM(CASE WHEN balance_qty < 0 THEN balance_qty ELSE 0 END) AS negative_balance_qty
        FROM cda_it_custom.fact_inventory_mv
        WHERE {where_sql}
        GROUP BY 1, 2
        ORDER BY movement_date DESC
        LIMIT 100
    """

    try:
        rows = db_run(query, tuple(params))
        return _to_json(rows, columns)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Inventory flow query failed: %s", exc)
        return json.dumps({"error": str(exc)})


inventory_flow_tool = Tool(
    name="query_inventory_flow_positions",
    func=query_inventory_flow_positions,
    description=(
        "Summarise transit, pre-production, and post-production inventory balances. "
        "Args: time_range ('YYYY' or 'YYYY-MM-DD to YYYY-MM-DD', default '2024'), warehouse (str, optional), product_id (str, optional)."
    ),
)


def query_stock_move_status_summary(args: Dict[str, str]) -> str:
    """Aggregate stock move counts and quantities by status and sequence."""

    time_range = args.get("time_range", "2024")
    start_date, end_date = parse_time_range(time_range)
    sequence_code = args.get("sequence_code")
    move_type = args.get("move_type")
    warehouse = args.get("warehouse")

    columns = [
        "move_date",
        "move_status",
        "sequence_code",
        "move_type",
        "move_count",
        "total_quantity",
    ]

    where_clauses = ["date_completed BETWEEN %s AND %s"]
    params: List[str] = [start_date, end_date]

    if sequence_code:
        where_clauses.append("sequence_code = %s")
        params.append(sequence_code)
    if move_type:
        where_clauses.append("move_type = %s")
        params.append(move_type)
    if warehouse:
        where_clauses.append(
            "(source_warehouse_code = %s OR dest_warehouse_code = %s)"
        )
        params.extend([warehouse, warehouse])

    where_sql = " AND ".join(where_clauses)
    query = f"""
        SELECT
            date_completed::date AS move_date,
            move_status,
            sequence_code,
            move_type,
            COUNT(*) AS move_count,
            SUM(product_uom_qty) AS total_quantity
        FROM cda_it_custom.fact_stock_move
        WHERE {where_sql}
        GROUP BY 1, 2, 3, 4
        ORDER BY move_date DESC
        LIMIT 100
    """

    try:
        rows = db_run(query, tuple(params))
        return _to_json(rows, columns)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Stock move summary query failed: %s", exc)
        return json.dumps({"error": str(exc)})


stock_move_status_tool = Tool(
    name="query_stock_move_status_summary",
    func=query_stock_move_status_summary,
    description=(
        "Aggregate stock moves by status and sequence. Args: time_range ('YYYY' or 'YYYY-MM-DD to YYYY-MM-DD', default '2024'), "
        "sequence_code (str, optional), move_type (str, optional), warehouse (str, optional)."
    ),
)

__all__ = [
    "logistics_shipments_tool",
    "inventory_flow_tool",
    "stock_move_status_tool",
]
