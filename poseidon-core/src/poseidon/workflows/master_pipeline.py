"""Default development workflow used by the supervisor CLI.

Only reference modules that are enabled in ``config/feature_flags.yaml``.  The list is
meant for quick smoke tests during development and should be updated if feature flags
change.  This file intentionally stays under ``src/workflows/`` so Streamlit and CLI
entrypoints can import it without extra wiring.
"""

# Reuse a shared session so guardrails cache correctly across steps.
_SESSION = "master_sess"

master_workflow = [
    # ----- Sales -----
    {"module": "sales", "input": "Get total sales and gross margin for top 10 customers this month", "session_id": _SESSION},
    {"module": "sales", "input": "List top 5 products by revenue", "session_id": _SESSION},
    {"module": "inference", "input": "Suggest priority follow-ups for high-value customers", "session_id": _SESSION},

    # ----- Purchasing -----
    {"module": "purchasing", "input": "Get all open purchase orders from key suppliers", "session_id": _SESSION},
    {"module": "purchasing", "input": "Check supplier lead times and reliability metrics", "session_id": _SESSION},
    {"module": "purchasing", "input": "Summarize purchase spend by product category for last quarter", "session_id": _SESSION},

    # ----- Inventory & Logistics -----
    {"module": "logistics", "input": "Check stock levels for all finished goods", "session_id": _SESSION},
    {"module": "logistics", "input": "List items below reorder point", "session_id": _SESSION},
    {"module": "logistics", "input": "Track pending shipments and delivery dates", "session_id": _SESSION},

    # ----- Manufacturing -----
    {"module": "manufacturing", "input": "Get production status for all active work orders", "session_id": _SESSION},
    {"module": "manufacturing", "input": "List all delayed work orders", "session_id": _SESSION},
    {"module": "manufacturing", "input": "Check BOM compliance for top-selling products", "session_id": _SESSION},

    # ----- Accounting -----
    {"module": "accounting", "input": "Reconcile bank statement for current month", "session_id": _SESSION},
    {"module": "accounting", "input": "List unpaid invoices past due date", "session_id": _SESSION},
    {"module": "accounting", "input": "Generate journal entries for closing month", "session_id": _SESSION},

    # ----- Inference / Upsell -----
    {"module": "inference", "input": "Suggest upsell opportunities for top 20 customers", "session_id": _SESSION},
    {"module": "inference", "input": "Identify cross-selling opportunities for low-activity customers", "session_id": _SESSION},
]
