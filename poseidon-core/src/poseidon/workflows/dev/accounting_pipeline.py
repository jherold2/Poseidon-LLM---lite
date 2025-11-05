# src/workflows/accounting_pipeline.py
accounting_workflow = [
    {"module": "accounting", "input": "Reconcile bank statement for September 2025", "session_id": "accounting_sess"},
    {"module": "accounting", "input": "List unpaid invoices past due date", "session_id": "accounting_sess"},
    {"module": "accounting", "input": "Generate journal entries for closing month", "session_id": "accounting_sess"},
]
