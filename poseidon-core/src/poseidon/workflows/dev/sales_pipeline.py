# src/workflows/sales_pipeline.py
sales_workflow = [
    {"module": "sales", "input": "Get total sales and gross margin for customer C101 this month", "session_id": "sales_sess"},
    {"module": "sales", "input": "List top 5 products by revenue", "session_id": "sales_sess"},
    {"module": "inference", "input": "Suggest potential upsell products for customer C101", "session_id": "sales_sess"},
    {"module": "sales", "input": "Check status of outstanding orders for customer C101", "session_id": "sales_sess"},
]
