import os
import imaplib
import email
import json
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_USER = os.getenv("IMAP_USER")
EMAIL_PASSWORD = os.getenv("IMAP_PASSWORD")
RESPONSES_FILE = Path("data/task_responses.jsonl")
RESPONSES_FILE.parent.mkdir(parents=True, exist_ok=True)

def _get_email_body(msg):
    """Handle multipart messages and return text/plain body."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" and part.get_content_disposition() != "attachment":
                return part.get_payload(decode=True).decode(errors="ignore")
    else:
        return msg.get_payload(decode=True).decode(errors="ignore")
    return ""

def poll_responses(subject_filter="[Task Assignment]"):
    """
    Poll unread emails with the given subject filter and log responses to a JSONL file.
    Marks messages as seen after processing.
    """
    logger.info("📥 Connecting to IMAP server...")
    try:
        conn = imaplib.IMAP4_SSL(IMAP_SERVER)
        conn.login(IMAP_USER, IMAP_PASSWORD)
    except imaplib.IMAP4.error as e:
        logger.error(f"❌ IMAP authentication failed: {e}")
        return []

    conn.select("INBOX")
    status, data = conn.search(None, f'(UNSEEN SUBJECT "{subject_filter}")')

    if status != "OK":
        logger.error("❌ Failed to search mailbox.")
        return []

    responses = []
    for num in data[0].split():
        try:
            _, msg_data = conn.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            sender = email.utils.parseaddr(msg["From"])[1]
            subject = msg["Subject"]
            body = _get_email_body(msg).strip()

            if not body:
                logger.warning(f"⚠️ Empty body for email from {sender}")
                continue

            record = {
                "timestamp": datetime.utcnow().isoformat(),
                "sender": sender,
                "subject": subject,
                "response": body,
            }
            responses.append(record)
            logger.info(f"✅ Logged response from {sender} - {subject}")

            # Mark message as seen
            conn.store(num, "+FLAGS", "\\Seen")

        except Exception as e:
            logger.exception(f"❌ Failed to process message {num}: {e}")

    conn.logout()

    if responses:
        with RESPONSES_FILE.open("a") as f:
            for r in responses:
                f.write(json.dumps(r) + "\n")
        logger.info(f"📊 {len(responses)} responses appended to {RESPONSES_FILE}")
    else:
        logger.info("📭 No new responses found.")

    return responses

if __name__ == "__main__":
    poll_responses()
