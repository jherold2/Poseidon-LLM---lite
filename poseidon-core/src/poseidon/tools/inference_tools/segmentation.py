# ==== Imports & Setup ====
import logging
from langchain_core.tools import Tool
import json
from datetime import datetime
from poseidon.tools.query_tools.sales_history_queries import query_database
from poseidon.utils.logger_setup import setup_logging
import pandas as pd
from poseidon.tools.inference_tools.utils import parse_date

setup_logging()
logger = logging.getLogger(__name__)

def calculate_rfm():
    """Calculate RFM scores from fact_sales and dim_customer."""
    query = """
    SELECT 
        c.customer_id,
        c.name,
        MAX(s.order_date) AS last_purchase,
        COUNT(s.order_id) AS frequency,
        SUM(s.total_price) AS monetary
    FROM fact_sales s
    JOIN dim_customer c ON s.customer_id = c.customer_id
    GROUP BY c.customer_id, c.name
    """
    try:
        df = pd.DataFrame(query_database(query))
        if df.empty:
            logger.warning("No data returned for RFM calculation")
            return []
        df['last_purchase'] = pd.to_datetime(df['last_purchase'])
        df['recency'] = (datetime.now() - df['last_purchase']).dt.days
        df['recency_score'] = 100 - (df['recency'] / df['recency'].max() * 100)
        df['frequency_score'] = (df['frequency'] / df['frequency'].max() * 100)
        df['monetary_score'] = (df['monetary'] / df['monetary'].max() * 100)
        df['rfm_score'] = (df['recency_score'] + df['frequency_score'] + df['monetary_score']) / 3
        logger.info(f"Calculated RFM scores for {len(df)} customers")
        return df[['customer_id', 'name', 'rfm_score']].to_dict('records')
    except Exception as e:
        logger.error(f"RFM calculation failed: {str(e)}")
        return []

def infer_customer_segmentation(args: dict) -> str:
    """
    Segment customers based on purchase data using RFM (Recency, Frequency, Monetary) analysis
    enhanced with dim_customer attributes (sales_channel, region, state).
    Segments customers into 'high_value', 'medium_value', or 'low_value' based on thresholds.
    Args:
        purchases (dict): JSON with customer_id, purchases list (total_amount, order_date, so_number),
                         and dim_customer attributes (sales_channel, region, state)
    Returns:
        JSON string with segment, customer IDs, and evidence
    """
    purchases = args.get("purchases", {})
    current_date = datetime.now()

    try:
        customers = purchases.get("purchases", [])
        if not customers:
            raise ValueError("No purchase data provided")

        high_value_customers = []
        medium_value_customers = []
        low_value_customers = []

        for customer in customers:
            customer_id = customer.get("customer_id")
            total_amount = float(customer.get("total_amount", 0))
            order_date = parse_date(customer.get("order_date"))
            so_number = customer.get("so_number")

            # Calculate recency (days since last order)
            recency = (current_date - order_date).days
            # Calculate frequency (number of orders)
            frequency = len([p for p in customers if p["customer_id"] == customer_id])
            # Total past orders (same as frequency in this context)
            total_orders = frequency

            # Extract dim_customer attributes
            sales_channel = customer.get("sales_channel", "unknown")
            region = customer.get("region", "unknown")
            state = customer.get("state", "unknown")

            # RFM thresholds for segmentation
            is_high_value = (
                    total_amount > 10000 and  # Monetary threshold
                    recency < 90 and  # Recent purchase (within 3 months)
                    frequency >= 5  # Frequent orders
            )
            is_medium_value = (
                    total_amount > 5000 and  # Moderate spend
                    recency < 180 and  # Within 6 months
                    frequency >= 2  # At least 2 orders
            )

            # Segment customer
            if is_high_value:
                high_value_customers.append({
                    "customer_id": customer_id,
                    "sales_channel": sales_channel,
                    "region": region,
                    "state": state
                })
            elif is_medium_value:
                medium_value_customers.append({
                    "customer_id": customer_id,
                    "sales_channel": sales_channel,
                    "region": region,
                    "state": state
                })
            else:
                low_value_customers.append({
                    "customer_id": customer_id,
                    "sales_channel": sales_channel,
                    "region": region,
                    "state": state
                })

        output = {
            "segments": {
                "high_value": high_value_customers,
                "medium_value": medium_value_customers,
                "low_value": low_value_customers
            },
            "evidence": {
                "purchases": purchases,
                "analysis": {
                    "recency_thresholds": {"high": "<90 days", "medium": "<180 days"},
                    "frequency_thresholds": {"high": ">=5 orders", "medium": ">=2 orders"},
                    "monetary_thresholds": {"high": ">10000", "medium": ">5000"}
                }
            }
        }
        logger.debug("Customer segmentation completed: %s", output)
        return json.dumps(output)
    except Exception as e:
        logger.error("Segmentation failed: %s", str(e))
        return json.dumps({"error": f"Segmentation failed: {str(e)}"})


segmentation_basic_tool = Tool(
    name="RFM_Analysis",
    func=calculate_rfm,
    description="Calculate RFM scores for customers using fact_sales and dim_customer."
)

segmentation_tool = Tool(
    name="infer_customer_segmentation",
    func=infer_customer_segmentation,
    description="Segment customers based on RFM (recency, frequency, monetary) and dim_customer attributes (sales_channel, region, state). Args: purchases (json with customer_id, total_amount, order_date, so_number, sales_channel, region, state)."
)
