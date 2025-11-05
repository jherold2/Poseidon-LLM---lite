"""
sales_recommendations.py
-----------------
Centralized LangChain Tools for generating sales insights from query data.
Each tool:
  - Takes JSON inputs (e.g., from query tools like query_tools_generic.py)
  - Performs inference logic for segmentation, risk analysis, or recommendations
  - Returns JSON output with insights and evidence
  - Includes error handling and logging for robustness
"""

import logging

# ==== Imports & Setup ====
from langchain_core.tools import Tool
import json
from typing import Dict
from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


# ==== Inference Tools ====

def infer_upsell_opportunities(args: dict) -> str:
    """
    Infer upsell opportunities by combining purchase data, product affinities, and contract terms.
    Identifies products frequently bought together that the customer hasn't purchased yet.
    Args:
        purchases (dict): JSON with customer_id and list of purchases (product_id)
        affinities (dict): JSON with product affinity data (related_product_id)
        contract_terms (dict): JSON with allowed_products list (optional)
    Returns:
        JSON string with recommended product to upsell and supporting evidence
    """
    purchases = args.get("purchases", {})
    affinities = args.get("affinities", {})
    contract_terms = args.get("contract_terms", {})
    customer_id = purchases.get("customer_id", "unknown")

    try:
        # Extract purchased product IDs
        bought_products = [p["product_id"] for p in purchases.get("purchases", [])]
        # Extract related product IDs from affinities
        related_products = [a["related_product_id"] for a in affinities.get("affinities", [])]
        # Get allowed products from contract terms (if any)
        allowed_products = contract_terms.get("allowed_products", [])

        # Filter for products not yet bought and allowed by contract
        recommendations = [
            p for p in related_products
            if p not in bought_products and (not allowed_products or p in allowed_products)
        ]

        if not recommendations:
            logger.info("No upsell opportunities found for customer %s", customer_id)
            return json.dumps({"error": "No upsell opportunities found"})

        # Return the top recommendation
        output = {
            "recommendation": f"Upsell {recommendations[0]} to Customer {customer_id}",
            "evidence": {
                "purchases": purchases,
                "affinities": affinities,
                "contract_terms": contract_terms
            }
        }
        logger.debug("Upsell recommendation generated: %s", output)
        return json.dumps(output)
    except Exception as e:
        logger.error("Upsell inference failed: %s", str(e))
        return json.dumps({"error": f"Upsell inference failed: {str(e)}"})




def infer_payment_risk(args: dict) -> str:
    """
    Analyze sales risks based on payment delays relative to contract terms.
    Considers overdue payments to classify risk as 'High', 'Medium', or 'Low'.
    Args:
        purchases (dict): JSON with purchases list (amount, days_since_payment)
        contract_terms (dict): JSON with payment_terms (e.g., "30 days")
    Returns:
        JSON string with risk level and evidence
    """
    purchases = args.get("purchases", {})
    contract_terms = args.get("contract_terms", {})
    payment_terms = contract_terms.get("payment_terms", "30 days")

    try:
        # Extract payment term days (e.g., "30 days" -> 30)
        payment_days = int(payment_terms.split()[0])
        customers = purchases.get("purchases", [])

        overdue_count = 0
        total_purchases = len(customers)

        for purchase in customers:
            amount = float(purchase.get("amount", 0))
            days_since_payment = int(purchase.get("days_since_payment", 0))
            if amount > 0 and days_since_payment > payment_days:
                overdue_count += 1

        # Risk classification based on overdue proportion
        overdue_ratio = overdue_count / total_purchases if total_purchases > 0 else 0
        if overdue_ratio > 0.5:
            risk = "High payment delay risk"
        elif overdue_ratio > 0.2:
            risk = "Medium payment delay risk"
        else:
            risk = "Low payment delay risk"

        output = {
            "risk": risk,
            "evidence": {
                "purchases": purchases,
                "contract_terms": contract_terms,
                "overdue_count": overdue_count,
                "total_purchases": total_purchases
            }
        }
        logger.debug("Sales risk analysis completed: %s", output)
        return json.dumps(output)
    except Exception as e:
        logger.error("Risk analysis failed: %s", str(e))
        return json.dumps({"error": f"Risk analysis failed: {str(e)}"})


def simulate_price_sensitivity(args: Dict[str, float]) -> str:
    """Estimate revenue impact of a price change using elasticity assumptions."""
    try:
        baseline_volume = float(args["baseline_volume"])
        baseline_revenue = float(args["baseline_revenue"])
        price_change_pct = float(args.get("price_change_pct", 0.0))
        elasticity = float(args.get("elasticity", -1.2))
    except KeyError as exc:
        return json.dumps({"error": f"missing required field: {exc}"})
    except Exception as exc:
        logger.error("Invalid price sensitivity inputs: %s", exc)
        return json.dumps({"error": str(exc)})

    baseline_price = baseline_revenue / baseline_volume if baseline_volume else 0.0
    price_factor = 1 + price_change_pct / 100
    volume_factor = max(0.0, 1 + elasticity * (price_change_pct / 100))
    new_price = baseline_price * price_factor
    new_volume = baseline_volume * volume_factor
    new_revenue = new_price * new_volume
    payload = {
        "baseline": {
            "price": baseline_price,
            "volume": baseline_volume,
            "revenue": baseline_revenue,
        },
        "scenario": {
            "price_change_pct": price_change_pct,
            "elasticity": elasticity,
            "estimated_price": new_price,
            "estimated_volume": new_volume,
            "estimated_revenue": new_revenue,
            "revenue_delta": new_revenue - baseline_revenue,
        },
    }
    return json.dumps(payload)


def simulate_margin_scenario(args: Dict[str, float]) -> str:
    """Project margin impact from revenue and cost adjustments."""
    try:
        baseline_revenue = float(args["baseline_revenue"])
        baseline_cost = float(args["baseline_cost"])
        revenue_change_pct = float(args.get("revenue_change_pct", 0.0))
        cost_change_pct = float(args.get("cost_change_pct", 0.0))
    except KeyError as exc:
        return json.dumps({"error": f"missing required field: {exc}"})
    except Exception as exc:
        logger.error("Invalid margin scenario inputs: %s", exc)
        return json.dumps({"error": str(exc)})

    new_revenue = baseline_revenue * (1 + revenue_change_pct / 100)
    new_cost = baseline_cost * (1 + cost_change_pct / 100)
    baseline_margin = baseline_revenue - baseline_cost
    new_margin = new_revenue - new_cost
    scenario = {
        "revenue_change_pct": revenue_change_pct,
        "cost_change_pct": cost_change_pct,
        "revenue": new_revenue,
        "cost": new_cost,
        "margin": new_margin,
        "margin_pct": (new_margin / new_revenue) if new_revenue else None,
        "margin_delta": new_margin - baseline_margin,
    }
    payload = {
        "baseline": {
            "revenue": baseline_revenue,
            "cost": baseline_cost,
            "margin": baseline_margin,
            "margin_pct": (baseline_margin / baseline_revenue) if baseline_revenue else None,
        },
        "scenario": scenario,
    }
    return json.dumps(payload)

def analyze_customer_behavior(args: Dict[str, object]) -> str:
    customer_id = args.get("customer_id")
    events = args.get("events") or []
    if not isinstance(events, list) or not events:
        return json.dumps({"error": "events must be a non-empty list"})

    inactivity_days = max((event.get("days_since_activity", 0) for event in events), default=0)
    engagement = sum(event.get("engagement_score", 0) for event in events) / len(events)
    complaints = sum(1 for event in events if event.get("type") == "complaint")

    churn_score = 0
    churn_score += inactivity_days / 30
    churn_score -= engagement
    churn_score += complaints * 0.5

    if churn_score >= 2:
        risk = "high"
    elif churn_score >= 1:
        risk = "medium"
    else:
        risk = "low"

    payload = {
        "customer_id": customer_id,
        "risk_level": risk,
        "metrics": {
            "max_days_inactive": inactivity_days,
            "avg_engagement": engagement,
            "complaints": complaints,
            "score": churn_score,
        },
    }
    return json.dumps(payload)


# ==== LangChain Tool Objects ====

upsell_inference_tool = Tool(
    name="infer_upsell_opportunities",
    func=infer_upsell_opportunities,
    description="Infer upsell opportunities from purchases, affinities, and contract terms. Args: purchases (json), affinities (json, optional), contract_terms (json, optional)."
)


payment_risk_tool = Tool(
    name="infer_payment_risk",
    func=infer_payment_risk,
    description="Analyze sales risks (e.g., payment delays). Args: purchases (json), contract_terms (json)."
)

price_sensitivity_tool = Tool(
    name="simulate_price_sensitivity",
    func=simulate_price_sensitivity,
    description="Simulate revenue impact of price changes. Args: baseline_volume, baseline_revenue, price_change_pct, elasticity (optional)."
)

margin_scenario_tool = Tool(
    name="simulate_margin_scenario",
    func=simulate_margin_scenario,
    description="Simulate margin impact from revenue/cost shifts. Args: baseline_revenue, baseline_cost, revenue_change_pct (optional), cost_change_pct (optional)."
)

behavior_tool = Tool(
    name="analyze_customer_behavior",
    func=analyze_customer_behavior,
    description="Assess churn risk using behaviour events. Args: customer_id (str), events (list of dict).",
)

# Commented out contract compliance tool as per request
# def validate_contract_compliance(args: dict) -> str:
#     """
#     Check if purchases comply with contract terms.
#     Args:
#         purchases (dict): JSON with purchases list (product_id)
#         contract_terms (dict): JSON with allowed_products list
#     Returns:
#         JSON string with compliance status and details
#     """
#     purchases = args.get("purchases", {})
#     contract_terms = args.get("contract_terms", {})
#     try:
#         bought_products = [p["product_id"] for p in purchases.get("purchases", [])]
#         allowed_products = contract_terms.get("allowed_products", [])
#         non_compliant = [p for p in bought_products if p not in allowed_products]
#         compliant = len(non_compliant) == 0
#         output = {"compliant": compliant, "details": {"non_compliant_products": non_compliant}}
#         logger.debug("Contract compliance check completed: %s", output)
#         return json.dumps(output)
#     except Exception as e:
#         logger.error("Compliance check failed: %s", str(e))
#         return json.dumps({"error": f"Compliance check failed: {str(e)}"})
#
# contract_compliance_tool = Tool(
#     name="validate_contract_compliance",
#     func=validate_contract_compliance,
#     description="Check if purchases comply with contract terms. Args: purchases (json), contract_terms (json)."
# )

# ==== Export Tools ====
# Export all active inference tools for use in agents
inference_tools = [
    upsell_inference_tool,
    payment_risk_tool,
    price_sensitivity_tool,
    margin_scenario_tool,
    behavior_tool
]

# ==== Additional Considerations ====
# - Future iterations could integrate ML libraries (e.g., scikit-learn) for advanced segmentation
# - Add batch processing support for large datasets using pandas
# - Incorporate external APIs for real-time market trend data
# - Optimize for longer chains with intermediate validation steps
# - Add caching for inference results to improve performance
