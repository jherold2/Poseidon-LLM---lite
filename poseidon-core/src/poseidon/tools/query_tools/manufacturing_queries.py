"""Manufacturing helper tools for BOM and work-order drill downs."""

from __future__ import annotations

import logging

import json
from typing import Dict, List

from langchain_core.tools import Tool

from poseidon.utils.db_connect import run as db_run
from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def _to_json(rows: List[tuple], columns: List[str]) -> str:
    return json.dumps([dict(zip(columns, row)) for row in rows], default=str)


def query_bom_components(args: Dict[str, str]) -> str:
    """Return component breakdown for a given BOM or produced product."""
    bom_id = args.get("bom_id")
    product_id = args.get("product_id")

    if not bom_id and not product_id:
        return json.dumps({"error": "Provide bom_id or product_id"})

    clauses: List[str] = []
    params: List[str] = []
    if bom_id:
        clauses.append("bom_id = %s")
        params.append(bom_id)
    if product_id:
        clauses.append("produced_product_id = %s")
        params.append(product_id)

    where_sql = " AND ".join(clauses)
    query = (
        "SELECT bom_component_id, bom_id, product_id, product_code, product_name, category_code, "
        "quantity, uom_name, base_uom_quantity, base_uom_name, is_produced "
        "FROM cda_it_custom.dim_bom_component "
        f"WHERE {where_sql} ORDER BY product_name"
    )

    try:
        rows = db_run(query, tuple(params))
        columns = [
            "bom_component_id",
            "bom_id",
            "product_id",
            "product_code",
            "product_name",
            "category_code",
            "quantity",
            "uom_name",
            "base_uom_quantity",
            "base_uom_name",
            "is_produced",
        ]
        return _to_json(rows, columns)
    except Exception as exc:  # pragma: no cover
        logger.error("BOM component query failed: %s", exc)
        return json.dumps({"error": str(exc)})


manufacturing_bom_tool = Tool(
    name="query_bom_components",
    func=query_bom_components,
    description=(
        "List components for a BOM. Args: bom_id (str, optional), product_id (str, optional). "
        "At least one parameter is required."
    ),
)

__all__ = ["manufacturing_bom_tool"]
