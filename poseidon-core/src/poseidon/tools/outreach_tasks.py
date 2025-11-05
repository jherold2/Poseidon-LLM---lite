"""Outbound email helpers for employee task assignments."""

from __future__ import annotations

from datetime import datetime
from poseidon.tools.email_client import send as send_email
from poseidon.tools.task_assignment import log_sent_task


def send_task_email(employee, task):
    subject = f"[Task Assignment] {task['name']} - Due EOD Today"
    body = f"""
    Hi {employee['name']},

    You have been assigned the following high-impact task:
    - Task: {task['name']}
    - Description: {task['description']}
    - Deadline: End of day today ({datetime.utcnow().strftime('%Y-%m-%d')})

    Please reply to this email once complete.

    Best,
    Automation Orchestrator
    """

    email_data = {
        "to": employee["email"],
        "cc": employee["manager_email"],
        "subject": subject,
        "body": body,
    }

    send_email(email_data)
    log_sent_task(employee, task, email_data)
