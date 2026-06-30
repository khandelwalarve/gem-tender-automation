"""
notify.py — Sends email/SMS alerts to the assigned reviewer or operator.
Used for: routing a tender to human approval, deadline reminders, and
escalation when a primary reviewer is unresponsive.
"""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

from src.audit_logging import Phase, log_error, log_info
from src.common.config import get_settings


def send_email(to_addr: str, subject: str, body: str, tender_id: int | None = None) -> bool:
    settings = get_settings()
    cfg = settings.get("alerts", {}).get("email", {})

    if not cfg.get("smtp_host"):
        log_info(phase=Phase.HUMAN_APPROVAL, step="Send Email (skipped, not configured)", tender_id=tender_id, detail={"to": to_addr, "subject": subject})
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = cfg.get("from_addr", "")
    msg["To"] = to_addr

    try:
        with smtplib.SMTP(cfg["smtp_host"], cfg.get("smtp_port", 587)) as server:
            server.starttls()
            if cfg.get("username"):
                server.login(cfg["username"], cfg["password"])
            server.send_message(msg)
        log_info(phase=Phase.HUMAN_APPROVAL, step="Email Sent", tender_id=tender_id, detail={"to": to_addr, "subject": subject})
        return True
    except Exception as e:  # noqa: BLE001
        log_error(phase=Phase.HUMAN_APPROVAL, step="Send Email", exc=e, tender_id=tender_id, extra={"to": to_addr})
        return False


def send_sms(to_number: str, body: str, tender_id: int | None = None) -> bool:
    """
    Sends an SMS via the configured provider (e.g. Twilio). Implementation
    is provider-agnostic at the interface level; fill in the actual API call
    once a provider is chosen.
    """
    settings = get_settings()
    cfg = settings.get("alerts", {}).get("sms", {})

    if not cfg.get("provider"):
        log_info(phase=Phase.HUMAN_APPROVAL, step="Send SMS (skipped, not configured)", tender_id=tender_id, detail={"to": to_number})
        return False

    try:
        if cfg["provider"] == "twilio":
            from twilio.rest import Client

            client = Client(cfg["account_sid"], cfg["auth_token"])
            client.messages.create(body=body, from_=cfg["from_number"], to=to_number)
        else:
            raise NotImplementedError(f"SMS provider '{cfg['provider']}' is not implemented")

        log_info(phase=Phase.HUMAN_APPROVAL, step="SMS Sent", tender_id=tender_id, detail={"to": to_number})
        return True
    except Exception as e:  # noqa: BLE001
        log_error(phase=Phase.HUMAN_APPROVAL, step="Send SMS", exc=e, tender_id=tender_id, extra={"to": to_number})
        return False


def notify_reviewer(reviewer_email: str, reviewer_phone: str | None, tender_id: int, bid_id: str, summary: str) -> None:
    subject = f"[Action Required] Tender {bid_id} needs your approval"
    body = (
        f"Tender {bid_id} has been routed for human approval.\n\n"
        f"Summary:\n{summary}\n\n"
        f"Please review in the dashboard before the submission deadline."
    )
    send_email(reviewer_email, subject, body, tender_id=tender_id)
    if reviewer_phone:
        send_sms(reviewer_phone, f"Tender {bid_id} needs your approval. Check the dashboard.", tender_id=tender_id)
