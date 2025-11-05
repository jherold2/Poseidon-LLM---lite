"""Accounting drill-down tools for ledger visibility."""

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
    return json.dumps([dict(zip(columns, row)) for row in rows], default=str)


def query_ledger_entries(args: Dict[str, str]) -> str:
    """Fetch general ledger entries filtered by account, journal, or date range."""
    time_range = args.get("time_range", "2024")
    start_date, end_date = parse_time_range(time_range)
    account_id = args.get("account_id")
    journal_id = args.get("journal_id")
    move_name = args.get("move_name")

    clauses = ["accounting_date BETWEEN %s AND %s"]
    params: List[str] = [start_date, end_date]

    if account_id:
        clauses.append("account_id = %s")
        params.append(account_id)
    if journal_id:
        clauses.append("journal_id = %s")
        params.append(journal_id)
    if move_name:
        clauses.append("move_name = %s")
        params.append(move_name)

    where_sql = " AND ".join(clauses)
    columns = [
        "accounting_date",
        "journal_id",
        "account_id",
        "move_name",
        "move_type",
        "debit",
        "credit",
        "balance",
        "customer_id",
        "supplier_id",
        "product_id",
    ]

    query = (
        "SELECT accounting_date, journal_id, account_id, move_name, move_type, debit, credit, balance, "
        "customer_id, supplier_id, product_id "
        "FROM cda_it_custom.fact_accounting_journal_mv "
        f"WHERE {where_sql} ORDER BY accounting_date DESC LIMIT 100"
    )

    try:
        rows = db_run(query, tuple(params))
        return _to_json(rows, columns)
    except Exception as exc:  # pragma: no cover
        logger.error("Ledger query failed: %s", exc)
        return json.dumps({"error": str(exc)})


def detect_budget_allocation_anomalies(args: Dict[str, str]) -> str:
    """Identify budget lines whose descriptions do not align with the assigned product."""

    time_range = args.get("time_range", "2024")
    start_date, end_date = parse_time_range(time_range)
    try:
        min_amount = float(args.get("min_amount", 1_000_000))
    except ValueError:
        return json.dumps({"error": "min_amount must be numeric"})

    try:
        limit = int(args.get("limit", 50))
    except ValueError:
        return json.dumps({"error": "limit must be an integer"})

    columns = [
        "budget_line_id",
        "budget_line_name",
        "budget_name",
        "account_id",
        "product_id",
        "product_name",
        "category_level_1",
        "category_level_2",
        "category_level_3",
        "net_amount",
        "product_name_mismatch",
        "category_mismatch"
    ]

    query = (
        "WITH budget AS ("
        "    SELECT "
        "        fab.budget_line_id,"
        "        fab.budget_line_name,"
        "        fab.budget_name,"
        "        fab.account_id,"
        "        fab.product_id,"
        "        dp.product_name,"
        "        dp.category_level_1,"
        "        dp.category_level_2,"
        "        dp.category_level_3,"
        "        SUM(fab.debit - fab.credit) AS net_amount"
        "    FROM cda_it_custom.fact_accounting_budget_mv fab"
        "    LEFT JOIN cda_it_custom.dim_product dp ON fab.product_id = dp.product_id"
        "    WHERE fab.accounting_date BETWEEN %s AND %s"
        "    GROUP BY fab.budget_line_id, fab.budget_line_name, fab.budget_name, fab.account_id,"
        "             fab.product_id, dp.product_name, dp.category_level_1, dp.category_level_2, dp.category_level_3"
        "), flagged AS ("
        "    SELECT "
        "        budget_line_id,"
        "        budget_line_name,"
        "        budget_name,"
        "        account_id,"
        "        product_id,"
        "        product_name,"
        "        category_level_1,"
        "        category_level_2,"
        "        category_level_3,"
        "        net_amount,"
        "        (product_name IS NULL OR position(lower(product_name) in lower(budget_line_name)) = 0) AS product_name_mismatch,"
        "        (CASE WHEN category_level_1 IS NULL THEN FALSE ELSE position(lower(category_level_1) in lower(budget_line_name)) = 0 END) AS category_mismatch"
        "    FROM budget"
        ")"
        "SELECT * FROM flagged"
        " WHERE ABS(net_amount) >= %s"
        "   AND (product_name_mismatch OR category_mismatch)"
        " ORDER BY ABS(net_amount) DESC"
        " LIMIT %s"
    )

    params = (start_date, end_date, min_amount, limit)

    try:
        rows = db_run(query, params)
        return _to_json(rows, columns)
    except Exception as exc:  # pragma: no cover
        logger.error("Budget anomaly query failed: %s", exc)
        return json.dumps({"error": str(exc)})


ledger_entries_tool = Tool(
    name="query_ledger_entries",
    func=query_ledger_entries,
    description=(
        "Retrieve GL entries. Args: time_range ('YYYY' or 'YYYY-MM-DD to YYYY-MM-DD'), "
        "account_id (str, optional), journal_id (str, optional), move_name (str, optional)."
    ),
)

budget_allocation_anomaly_tool = Tool(
    name="detect_budget_allocation_anomalies",
    func=detect_budget_allocation_anomalies,
    description=(
        "Flag budget lines whose descriptions do not align with assigned products. "
        "Args: time_range (str, optional), min_amount (float, optional, default 1e6), limit (int, optional)."
    ),
)

__all__ = ["ledger_entries_tool", "budget_allocation_anomaly_tool"]
