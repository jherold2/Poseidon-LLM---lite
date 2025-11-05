# src/tools/email_client.py

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")  # your bot email address
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") or os.getenv("EMAIL_PASSWORD")


def send(email_data: dict) -> None:
    """
    Send an email using SMTP.
    
    Args:
        email_data (dict): {
            "to": "recipient@example.com",
            "cc": "manager@example.com",   # optional
            "subject": "Task Assignment",
            "body": "Task details..."
        }
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        raise ValueError("❌ SMTP_USER and SMTP_PASSWORD must be set in environment variables")

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = email_data["to"]
    if email_data.get("cc"):
        msg["Cc"] = email_data["cc"]
    msg["Subject"] = email_data["subject"]

    msg.attach(MIMEText(email_data["body"], "plain"))

    recipients = [email_data["to"]]
    if email_data.get("cc"):
        recipients.append(email_data["cc"])

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, recipients, msg.as_string())
            logger.info(f"✅ Email sent to {email_data['to']} (cc: {email_data.get('cc')})")
    except Exception as e:
        logger.exception(f"❌ Failed to send email: {e}")
        raise
