"""Tools for escalating issues or notifying human operators."""

from __future__ import annotations

import logging

import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional

import yaml
from langchain_core.tools import Tool

from poseidon.observability.audit_log import append_event
from poseidon.utils.logger_setup import setup_logging
from poseidon.utils.path_utils import resolve_config_path

setup_logging()
logger = logging.getLogger(__name__)

_EMAIL_CONFIG_PATH = resolve_config_path("email_config.yaml")


def escalate_issue(args: Dict[str, str]) -> str:
    """Persist an escalation request so on-call staff can review it."""
    payload = {
        "module": args.get("module"),
        "severity": args.get("severity", "medium"),
        "message": args.get("message"),
        "metadata": args.get("metadata"),
    }
    try:
        path = append_event("issue_escalated", payload)
        logger.info("Escalation recorded for module %s", payload["module"])
        return json.dumps({"status": "recorded", "path": str(path)})
    except Exception as exc:  # pragma: no cover - file IO protection
        logger.error("Failed to record escalation: %s", exc)
        return json.dumps({"error": str(exc)})


escalation_tool = Tool(
    name="escalate_issue",
    func=escalate_issue,
    description=(
        "Escalate an issue to human operators. Args: module (str), severity (str), "
        "message (str), metadata (dict, optional)."
    ),
)


def _load_email_config() -> Dict[str, str]:
    if not _EMAIL_CONFIG_PATH.exists():
        logger.warning(
            "Email config %s not found; email notifications disabled.", _EMAIL_CONFIG_PATH
        )
        return {}
    with _EMAIL_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


class EmailTool:
    def __init__(self):
        """Initialize the email tool with configuration."""
        self.config = _load_email_config()
        self.smtp_server = self.config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = int(self.config.get("smtp_port", 587))
        self.sender_email = self.config.get("sender_email")
        # Prefer environment variable; fall back to config for local testing only.
        self.sender_password = (
            os.getenv("SMTP_PASSWORD")
            or os.getenv("EMAIL_PASSWORD")
            or self.config.get("password")
        )

    def _validate(self) -> Optional[str]:
        if not self.sender_email:
            return "Missing sender_email in email configuration"
        if not self.sender_password:
            return "Missing EMAIL_PASSWORD environment variable or config password"
        recipients = self.config.get("allowed_recipients")
        if recipients is not None and not isinstance(recipients, list):
            return "allowed_recipients must be a list if provided"
        return None

    def send_email(self, recipient_email: str, subject: str, body: str) -> Dict[str, str]:
        """
        Send an email with the provided subject and body to the recipient.

        Args:
            recipient_email (str): The recipient's email address.
            subject (str): The subject of the email.
            body (str): The body content of the email.

        Returns:
            Dict[str, str]: Status and message indicating success or failure.
        """
        error = self._validate()
        if error:
            logger.error(error)
            return {"status": "error", "message": error}

        allowed = self.config.get("allowed_recipients")
        if allowed and recipient_email not in allowed:
            message = f"Recipient {recipient_email} not in allowed_recipients"
            logger.error(message)
            return {"status": "error", "message": message}

        try:
            # Create the MIME object
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = recipient_email
            msg["Subject"] = subject

            # Attach the body
            msg.attach(MIMEText(body, "plain"))

            # Set up the SMTP server
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()  # Enable TLS
            server.login(self.sender_email, self.sender_password)

            # Send the email
            server.sendmail(self.sender_email, recipient_email, msg.as_string())
            server.quit()

            logger.info(f"Email sent successfully to {recipient_email}")
            return {"status": "success", "message": f"Email sent to {recipient_email}"}

        except Exception as exc:  # pragma: no cover - network interaction
            logger.error("Failed to send email to %s: %s", recipient_email, exc)
            return {"status": "error", "message": f"Failed to send email: {exc}"}


def email_tool(recipient_email: str, subject: str, body: str) -> Dict[str, str]:
    """
    Wrapper function for the email tool to be used by agents.

    Args:
        recipient_email (str): The recipient's email address.
        subject (str): The subject of the email.
        body (str): The body content of the email.

    Returns:
        Dict[str, str]: Result of the email sending operation.
    """
    email_tool_instance = EmailTool()
    return email_tool_instance.send_email(recipient_email, subject, body)

__all__ = ["escalation_tool", "email_tool"]
