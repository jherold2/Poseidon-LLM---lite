# src/workflows/inventory_pipeline.py
inventory_workflow = [
    {"module": "logistics", "input": "Check stock levels for all finished goods", "session_id": "inventory_sess"},
    {"module": "logistics", "input": "List items below reorder point", "session_id": "inventory_sess"},
    {"module": "logistics", "input": "Track pending shipments and delivery dates", "session_id": "inventory_sess"},
]
