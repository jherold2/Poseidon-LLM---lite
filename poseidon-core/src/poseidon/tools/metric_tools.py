"""LangChain tools that proxy business metric requests to the MetricFlow semantic layer.

Includes caching-aware client usage, metric-intent resolution, and SQL fallbacks when the
semantic layer is unavailable.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Tuple

import requests
from langchain_core.tools import Tool

from poseidon.utils.metric_intents import resolve_metric_intent
from poseidon.utils.metricflowclient import MetricFlowError, get_metricflow_client
from poseidon.utils.db_connect import run as db_run
from poseidon.tools.query_tools.utils import parse_time_range

logger = logging.getLogger(__name__)


def _normalize_time_range(time_range: Any, column: str | None) -> Tuple[List[str], List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    if not column or not time_range:
        return clauses, params

    start = end = None
    if isinstance(time_range, dict):
        start = time_range.get("start")
        end = time_range.get("end")
    elif isinstance(time_range, str):
        try:
            start, end = parse_time_range(time_range)
        except ValueError:
            logger.debug("Unable to parse time_range '%s'", time_range)

    if start and end:
        clauses.append(f"{column} BETWEEN %s AND %s")
        params.extend([start, end])
    elif start:
        clauses.append(f"{column} >= %s")
        params.append(start)
    elif end:
        clauses.append(f"{column} <= %s")
        params.append(end)
    return clauses, params


def _apply_filters(allowed: Dict[str, str], filters: List[Dict[str, Any]]) -> Tuple[List[str], List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    include_active = True
    for flt in filters:
        dimension = (flt.get("dimension") or "").lower()
        operator = (flt.get("operator") or "equals").lower()
        value = flt.get("value")
        column = allowed.get(dimension)
        if not column or value is None:
            if dimension == "include_inactive" and str(value).lower() in ("true", "1", "yes"):
                include_active = False
            continue
        if operator == "equals":
            clauses.append(f"{column} = %s")
            params.append(value)
        elif operator == "in" and isinstance(value, (list, tuple)) and value:
            placeholders = ",".join(["%s"] * len(value))
            clauses.append(f"{column} IN ({placeholders})")
            params.extend(list(value))
    if include_active and "active" in allowed.values():
        active_column = next(col for col in allowed.values() if col.endswith("active"))
        clauses.append(f"({active_column} = %s OR {active_column} IS NULL)")
        params.append(True)
    return clauses, params


def _execute_query(sql: str, params: List[Any]) -> Any:
    result = db_run(sql, tuple(params) if params else None)
    return result[0][0] if result else None


def _fallback_total_sales(column: str, filters, time_range) -> Dict[str, Any]:
    time_clauses, params = _normalize_time_range(time_range, "order_date")
    filter_clauses, filter_params = _apply_filters(
        {
            "customer_id": "customer_ref",
            "sales_channel": "sales_channel",
            "sales_region": "sales_region",
        },
        filters,
    )
    clauses = time_clauses + filter_clauses
    params.extend(filter_params)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT SUM({column}) FROM cda_it_custom.fact_sales_mv {where}"
    return {"fallback": True, "value": _execute_query(sql, params)}


def _fallback_sales_order_count(filters, time_range) -> Dict[str, Any]:
    time_clauses, params = _normalize_time_range(time_range, "order_date")
    filter_clauses, filter_params = _apply_filters(
        {
            "customer_id": "customer_ref",
            "sales_channel": "sales_channel",
            "sales_region": "sales_region",
        },
        filters,
    )
    clauses = time_clauses + filter_clauses
    params.extend(filter_params)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = "SELECT COUNT(DISTINCT so_number) FROM cda_it_custom.fact_sales_mv " + where
    return {"fallback": True, "value": _execute_query(sql, params)}


def _fallback_average_order_value(filters, time_range) -> Dict[str, Any]:
    time_clauses, params = _normalize_time_range(time_range, "order_date")
    filter_clauses, filter_params = _apply_filters(
        {
            "customer_id": "customer_ref",
            "sales_channel": "sales_channel",
            "sales_region": "sales_region",
        },
        filters,
    )
    clauses = time_clauses + filter_clauses
    params.extend(filter_params)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT SUM(total_price) AS total_sales, COUNT(DISTINCT so_number) AS order_count "
        "FROM cda_it_custom.fact_sales_mv "
        + where
    )
    result = db_run(sql, tuple(params) if params else None)
    if result:
        total_sales, order_count = result[0]
        value = (total_sales / order_count) if order_count else None
    else:
        value = None
    return {"fallback": True, "value": value}


def _fallback_purchase_sum(column: str, filters, time_range) -> Dict[str, Any]:
    time_clauses, params = _normalize_time_range(time_range, "date_order")
    filter_clauses, filter_params = _apply_filters(
        {
            "supplier_id": "supplier_id",
            "product_id": "product_id",
            "buyer": "employee_name",
            "purchase_status": "status",
        },
        filters,
    )
    clauses = time_clauses + filter_clauses
    params.extend(filter_params)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT SUM({column}) FROM cda_it_custom.fact_purchases {where}"
    return {"fallback": True, "value": _execute_query(sql, params)}


def _fallback_average_purchase_price(filters, time_range) -> Dict[str, Any]:
    time_clauses, params = _normalize_time_range(time_range, "date_order")
    filter_clauses, filter_params = _apply_filters(
        {
            "supplier_id": "supplier_id",
            "product_id": "product_id",
            "buyer": "employee_name",
            "purchase_status": "status",
        },
        filters,
    )
    clauses = time_clauses + filter_clauses
    params.extend(filter_params)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT SUM(total_amount) AS total_spend, SUM(quantity_ordered) AS qty "
        "FROM cda_it_custom.fact_purchases "
        + where
    )
    result = db_run(sql, tuple(params) if params else None)
    if result:
        total_spend, qty = result[0]
        value = (total_spend / qty) if qty else None
    else:
        value = None
    return {"fallback": True, "value": value}


def _fallback_inventory_sum(column: str, filters, time_range) -> Dict[str, Any]:
    time_clauses, params = _normalize_time_range(time_range, "date")
    filter_clauses, filter_params = _apply_filters(
        {
            "product_id": "product_id",
            "source_warehouse": "source_warehouse",
            "destination_warehouse": "destination_warehouse",
            "base_warehouse": "base_warehouse",
        },
        filters,
    )
    clauses = time_clauses + filter_clauses
    params.extend(filter_params)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT SUM({column}) FROM cda_it_custom.fact_inventory_mv {where}"
    return {"fallback": True, "value": _execute_query(sql, params)}


def _fallback_invoice_sum(column: str, filters, time_range) -> Dict[str, Any]:
    time_clauses, params = _normalize_time_range(time_range, "invoice_date")
    filter_clauses, filter_params = _apply_filters(
        {
            "customer_id": "customer_id",
            "payment_state": "payment_state",
        },
        filters,
    )
    clauses = time_clauses + filter_clauses
    params.extend(filter_params)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT SUM({column}) FROM cda_it_custom.fact_accounting_invoice {where}"
    return {"fallback": True, "value": _execute_query(sql, params)}


def _fallback_journal_entry_count(filters, time_range) -> Dict[str, Any]:
    time_clauses, params = _normalize_time_range(time_range, "accounting_date")
    filter_clauses, filter_params = _apply_filters(
        {
            "journal_id": "journal_id",
            "account_id": "account_id",
        },
        filters,
    )
    clauses = time_clauses + filter_clauses
    params.extend(filter_params)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = "SELECT COUNT(DISTINCT account_move_line_id) FROM cda_it_custom.fact_accounting_journal_mv " + where
    return {"fallback": True, "value": _execute_query(sql, params)}


def _extract_account_groups(filters: List[Dict[str, Any]], default_groups: List[str]) -> List[str]:
    for flt in filters:
        if (flt.get("dimension") or "").lower() == "account_group":
            value = flt.get("value")
            if isinstance(value, (list, tuple)) and value:
                return list(value)
            if isinstance(value, str):
                return [value]
    return default_groups


def _fallback_account_group_balance(filters, time_range, default_groups: List[str]) -> Dict[str, Any]:
    groups = _extract_account_groups(filters, default_groups)
    if not groups:
        return {"fallback": True, "value": None}

    time_clauses, params = _normalize_time_range(time_range, "j.accounting_date")
    clauses = time_clauses + [f"a.account_group IN ({','.join(['%s'] * len(groups))})"]
    params.extend(groups)
    clauses.append("(a.active = %s OR a.active IS NULL)")
    params.append(True)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT SUM(j.balance) FROM cda_it_custom.fact_accounting_journal_mv j "
        "JOIN cda_it_custom.dim_account a ON j.account_id = a.account_id "
        f"{where}"
    )
    return {"fallback": True, "value": _execute_query(sql, params)}


FALLBACK_HANDLERS = {
    "total_sales_amount": lambda f, t: _fallback_total_sales("total_price", f, t),
    "total_net_sales_amount": lambda f, t: _fallback_total_sales("subtotal_taxable", f, t),
    "sales_order_count": _fallback_sales_order_count,
    "average_order_value": _fallback_average_order_value,
    "total_purchase_spend": lambda f, t: _fallback_purchase_sum("total_amount", f, t),
    "average_purchase_price": _fallback_average_purchase_price,
    "inventory_value": lambda f, t: _fallback_inventory_sum("total_value", f, t),
    "on_hand_quantity": lambda f, t: _fallback_inventory_sum("balance_qty", f, t),
    "total_invoiced_amount": lambda f, t: _fallback_invoice_sum("invoice_amount", f, t),
    "total_outstanding_amount": lambda f, t: _fallback_invoice_sum("outstanding", f, t),
    "journal_entry_count": _fallback_journal_entry_count,
    "cash_and_bank_balance": lambda f, t: _fallback_account_group_balance(f, t, ["PETTY CASH", "BANK"]),
    "receivables_balance": lambda f, t: _fallback_account_group_balance(f, t, [
        "PIUTANG USAHA",
        "PIUTANG PIHAK KE TIGA",
        "PIUTANG PIHAK KETIGA LAINNYA",
    ]),
    "inventory_balance": lambda f, t: _fallback_account_group_balance(f, t, ["PERSEDIAAN"]),
    "prepayments_balance": lambda f, t: _fallback_account_group_balance(f, t, [
        "UANG MUKA",
        "SEWA DIBAYAR DI MUKA",
        "BIAYA DI BAYAR DI MUKA",
        "PAJAK DIBAYAR DIMUKA",
    ]),
    "payables_balance": lambda f, t: _fallback_account_group_balance(f, t, [
        "HUTANG USAHA",
        "HUTANG PIHAK KETIGA",
        "HUTANG BIAYA",
        "HUTANG PAJAK",
        "HUTANG BANK JANGKA PENDEK",
        "HUTANG BANK JANGKA PANJANG",
        "HUTANG LEASING",
    ]),
    "fixed_asset_balance": lambda f, t: _fallback_account_group_balance(f, t, ["ASET TETAP"]),
    "accumulated_depreciation_balance": lambda f, t: _fallback_account_group_balance(f, t, [
        "AKUMULASI PENYUSUTAN PENYUSUTAN AKTIVA TETAP",
        "DEPRECIATION FACTORY",
        "BIAYA DEPRESIASI UMUM",
    ]),
    "equity_balance": lambda f, t: _fallback_account_group_balance(f, t, [
        "MODAL",
        "OPENING BALANCE EQUITY",
        "LABA (RUGI) DITAHAN",
        "DEVIDEN",
        "AGIO SAHAM",
        "OPENING BALANCE EQUITY REVISI",
        "CURRENT EARNING OF THE YEAR",
    ]),
    "operating_expense_balance": lambda f, t: _fallback_account_group_balance(f, t, [
        "BIAYA SALES DAN MARKETING",
        "BIAYA UMUM DAN ADMINISTRASI",
        "BIAYA LOGISTIK",
        "BIAYA DEPRESIASI UMUM",
        "BEBAN LAIN-LAIN",
    ]),
}


def _execute_fallback(metric: str, filters, time_range) -> Dict[str, Any]:
    handler = FALLBACK_HANDLERS.get(metric)
    if not handler:
        return {"fallback": True, "error": f"No fallback implemented for metric '{metric}'"}
    try:
        return handler(filters, time_range)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Fallback query failed for metric %s", metric)
        return {"fallback": True, "error": str(exc)}


def query_metric(args: Dict[str, Any]) -> str:
    """Resolve a natural-language metric request and return the MetricFlow response."""
    query = args.get("query")
    if not query:
        return json.dumps({"error": "Missing 'query' argument"})

    intent = resolve_metric_intent(query)
    if not intent:
        return json.dumps({"error": "No matching metric intent"})

    group_by: List[str] = args.get("group_by") or intent.default_group_by
    time_range = args.get("time_range") or intent.default_time_range
    filters = intent.build_filters(args)
    limit = args.get("limit")

    client = get_metricflow_client()
    try:
        response = client.query_metric(
            intent.metric,
            group_by=group_by,
            filters=filters,
            time_range=time_range,
            limit=limit,
        )
        payload = {
            "intent": intent.name,
            "metric": intent.metric,
            "group_by": group_by,
            "filters": filters,
            "time_range": time_range,
            "data": response,
        }
        return json.dumps(payload)
    except (MetricFlowError, requests.RequestException) as exc:
        logger.warning("MetricFlow query failed for metric %s: %s", intent.metric, exc)
        fallback_data = _execute_fallback(intent.metric, filters, time_range)
        return json.dumps(
            {
                "intent": intent.name,
                "metric": intent.metric,
                "group_by": group_by,
                "filters": filters,
                "time_range": time_range,
                "data": fallback_data,
                "warning": str(exc),
            }
        )
    except Exception as exc:  # unexpected failure
        logger.exception("Unexpected error querying metric %s", intent.metric)
        fallback_data = _execute_fallback(intent.metric, filters, time_range)
        return json.dumps(
            {
                "intent": intent.name,
                "metric": intent.metric,
                "group_by": group_by,
                "filters": filters,
                "time_range": time_range,
                "data": fallback_data,
                "error": str(exc),
            }
        )


metric_query_tool = Tool(
    name="query_semantic_metric",
    func=query_metric,
    description=(
        "Resolve business metric requests through the semantic layer. "
        "Args: query (str, required), group_by (list[str], optional), "
        "time_range (dict or str, optional), filters (list[dict], optional), limit (int, optional). "
        "Falls back to direct SQL when the semantic layer is unavailable."
    ),
)

__all__ = ["metric_query_tool"]
