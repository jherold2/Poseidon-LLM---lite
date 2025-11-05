# /src/tools/query_tools/sales_history_queries.py
import logging
import json
import ast
from datetime import datetime
from typing import List, Dict, Any

from langchain_core.tools import Tool

from functools import lru_cache

from poseidon.utils.db_connect import get_db
from poseidon.utils.logger_setup import setup_logging
from poseidon.tools.query_tools.utils import parse_time_range, validate_payload
from poseidon.utils.dimension_lookup import resolve_dimension_value
from poseidon.utils.cache import ConversationCache

# Initialize utilities
cache = ConversationCache()
setup_logging()
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _db():
    """Lazily obtain the shared SQLDatabase handle."""
    return get_db()


# ---------- Helper: Query Database ----------
def query_database(query: str, params: list = None) -> List[Dict[str, Any]]:
    """Execute a SQL query and return results as a list of dicts."""
    try:
        result = _db().run(query, params or [])
        if isinstance(result, str):
            try:
                result = ast.literal_eval(result)
            except (ValueError, SyntaxError):
                logger.error(f"Failed to parse DB result: {result}")
                return []

        if not result:
            return []

        # Infer column names
        columns = [f"column_{i}" for i in range(len(result[0]))] if result else []
        return [dict(zip(columns, row)) for row in result]
    except Exception as e:
        logger.error(f"DB query failed: {str(e)}")
        return []


# ---------- Customer Order History ----------
def query_customer_history(args: dict) -> str:
    error = validate_payload(
        args,
        required={"customer": (str,)},
        optional={"time_range": (str,), "group_by": (list,)},
    )
    if error:
        return json.dumps({"error": error})

    customer = args.get("customer")
    time_range = args.get("time_range", "2024")
    group_by = args.get("group_by", ["payment_status", "category_level_1"])

    if not all(isinstance(field, str) for field in group_by):
        return json.dumps({"error": "group_by entries must be strings"})

    customer_id = None
    if customer:
        matches = resolve_dimension_value("dim_customer_mv", customer, "customer", "customer_id")
        customer_id = matches[0]["value"] if matches else None
    if not customer_id:
        return json.dumps({"error": f"Customer '{customer}' not found"})

    start, end = parse_time_range(time_range)
    cache_key = f"customer_history_{customer_id}_{start}_{end}_{'_'.join(group_by)}"

    cached = cache.get_query(cache_key)
    if cached:
        return json.dumps(cached)

    try:
        group_fields = ", ".join(group_by)
        select_fields = (
            "product_id, item_description, sum(ordered_qty) as total_ordered, "
            "sum(qty) as total_qty, sum(subtotal_taxable) as total_taxable, "
            "sum(gross_sales) as total_gross, sum(line_discount) as total_discount, "
            "sum(cash_discount) as total_cash_discount"
        )
        if group_fields:
            select_fields += f", {group_fields}"

        query = f"""
        SELECT {select_fields}
        FROM cda_it_custom.fact_sales_mv
        WHERE customer_ref = '{customer_id}'
        AND order_date BETWEEN '{start}' AND '{end}'
        """
        if group_by:
            query += f" GROUP BY product_id, item_description, {group_fields}"
        else:
            query += " GROUP BY product_id, item_description"

        result = query_database(query)
        output = {"customer_id": customer_id, "purchase_history": result}
        cache.cache_query(cache_key, output)
        return json.dumps(output)
    except Exception as e:
        return json.dumps({"error": f"Query failed: {str(e)}"})


customer_order_history_tool = Tool(
    name="query_customer_purchase_history",
    func=query_customer_history,
    description="Query customer purchase history. Args: customer (str), time_range (str), group_by (list of str)."
)


# ---------- Order Status ----------
def query_order_status(args: dict) -> str:
    error = validate_payload(
        args,
        optional={"customer": (str,), "time_range": (str,)},
        allow_extra=False,
    )
    if error:
        return json.dumps({"error": error})

    customer = args.get("customer")
    time_range = args.get("time_range", "2024")
    start_date, end_date = parse_time_range(time_range)

    cache_key = f"order_status_{customer or 'all'}_{start_date}_{end_date}"
    cached = cache.get_query(cache_key)
    if cached:
        return json.dumps(cached)

    customer_id = None
    if customer:
        matches = resolve_dimension_value("dim_customer_mv", customer, "customer", "customer_id")
        customer_id = matches[0]["value"] if matches else None
    try:
        query = """
        SELECT so_number, so_status, invoice_status, delivery_status, order_date
        FROM cda_it_custom.fact_sales_mv
        WHERE order_date BETWEEN %s AND %s
        """
        params = [start_date, end_date]
        if customer_id:
            query += " AND customer_ref = %s"
            params.append(customer_id)

        result = query_database(query, params)
        output = {"order_status": result}
        cache.cache_query(cache_key, output)
        return json.dumps(output)
    except Exception as e:
        logger.error(f"Order status query failed: {str(e)}")
        return json.dumps({"error": str(e)})


order_status_tool = Tool(
    name="query_order_status",
    func=query_order_status,
    description="Check sales order statuses. Args: customer (str), time_range (str)."
)


# ---------- Sales Metrics ----------
def query_sales_metrics(args: dict) -> str:
    error = validate_payload(
        args,
        required={"customer_id": (str,)},
        optional={"time_range": (str,)},
    )
    if error:
        return json.dumps({"error": error})

    customer_id = args.get("customer_id")
    time_range = args.get("time_range", "2025-01-01 to 2025-12-31")
    cache_key = f"sales_metrics_{customer_id}_{time_range}"

    cached = cache.get_query(cache_key)
    if cached:
        return json.dumps(cached)

    try:
        start, end = parse_time_range(time_range)
        if not customer_id:
            raise ValueError("customer_id is required")

        query = """
        SELECT item_code, item_description,
               ROUND(SUM(price_unit * weight_kg)/SUM(weight_kg), 2) AS avg_unit_price,
               SUM(gross_sales) AS total_gross_sales,
               SUM(trade_discount) AS total_trade_discount,
               SUM(line_discount) AS total_line_discount,
               SUM(percent_discount) AS total_percent_discount,
               SUM(fixed_discount) AS total_fixed_discount,
               SUM(subtotal_taxable) AS total_untaxed_sales,
               SUM(total_price) AS total_sales,
               SUM(qty) AS total_quantity,
               SUM(weight_kg) AS total_weight
        FROM cda_it_custom.fact_sales_mv
        WHERE order_date >= %s AND order_date <= %s
          AND invoice_status = 'posted' AND customer_ref = %s
        GROUP BY item_code, item_description
        HAVING SUM(subtotal_taxable) IS NOT NULL
        ORDER BY total_untaxed_sales DESC
        LIMIT 10
        """
        params = [start, end, customer_id]
        result = query_database(query, params)
        output = {"customer_id": customer_id, "sales_metrics": result}
        cache.cache_query(cache_key, output)
        return json.dumps(output)
    except Exception as e:
        logger.error(f"Sales metrics query failed: {str(e)}")
        return json.dumps({"error": str(e)})


sales_metrics_tool = Tool(
    name="query_sales_metrics",
    func=query_sales_metrics,
    description="Query aggregated sales metrics. Args: customer_id (str), time_range (str)."
)


# ---------- Product Affinities ----------
def query_product_affinities(args: dict) -> str:
    error = validate_payload(args, required={"customer_id": (str,)}, allow_extra=False)
    if error:
        return json.dumps({"error": error})

    customer_id = args.get("customer_id")
    cache_key = f"product_affinities_{customer_id}"

    cached = cache.get_query(cache_key)
    if cached:
        return json.dumps(cached)

    try:
        query = """
        SELECT p1.product_id, p2.product_id AS related_product_id, COUNT(*) AS co_purchase_count
        FROM cda_it_custom.fact_sales_mv p1
        JOIN cda_it_custom.fact_sales_mv p2
          ON p1.so_number = p2.so_number AND p1.product_id != p2.product_id
        WHERE p1.customer_ref = %s
        GROUP BY p1.product_id, p2.product_id
        ORDER BY co_purchase_count DESC
        LIMIT 5
        """
        params = [customer_id]
        result = query_database(query, params)
        output = {"affinities": result}
        cache.cache_query(cache_key, output)
        return json.dumps(output)
    except Exception as e:
        logger.error(f"Product affinities query failed: {str(e)}")
        return json.dumps({"error": str(e)})


affinity_tool = Tool(
    name="query_product_affinities",
    func=query_product_affinities,
    description="Find products frequently bought together. Args: customer_id (str)."
)


__all__ = [
    "customer_order_history_tool",
    "order_status_tool",
    "sales_metrics_tool",
    "affinity_tool",
    "query_customer_history",
    "query_order_status",
    "query_sales_metrics",
    "query_product_affinities",
]
