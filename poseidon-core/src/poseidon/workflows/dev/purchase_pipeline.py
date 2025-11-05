# src/workflows/purchase_pipeline.py
purchase_workflow = [
    {"module": "purchasing", "input": "Get all open purchase orders from supplier S202", "session_id": "purchase_sess"},
    {"module": "purchasing", "input": "Check supplier lead times and delivery reliability", "session_id": "purchase_sess"},
    {"module": "purchasing", "input": "Summarize purchase spend by product category for last quarter", "session_id": "purchase_sess"},
]
