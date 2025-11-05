# src/workflows/manufacturing_pipeline.py
manufacturing_workflow = [
    {"module": "manufacturing", "input": "Get production status for work order WO1234", "session_id": "manufacturing_sess"},
    {"module": "manufacturing", "input": "List all delayed work orders", "session_id": "manufacturing_sess"},
    {"module": "manufacturing", "input": "Check BOM compliance for product P5678", "session_id": "manufacturing_sess"},
]
