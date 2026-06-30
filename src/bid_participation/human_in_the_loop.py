"""
human_in_the_loop.py — Detects CAPTCHAs after every Playwright interaction
and pauses for human takeover via the dashboard. Manages OTP escalation:
alerts the primary holder at T-1h, falls back to a backup holder if needed.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

from playwright.sync_api import Page

from src.audit_logging import Phase, log_warning
from src.common.config import get_settings
from src.human_approval.notify import send_email, send_sms


class CaptchaDetectedError(Exception):
    """Raised when a CAPTCHA is detected; caller should pause automation and alert a human."""


class OTPTimeoutError(Exception):
    """Raised when no OTP was supplied via the dashboard within the allotted window."""


CAPTCHA_SELECTORS = [
    "img[id*='captcha' i]",
    "iframe[src*='captcha' i]",
    "div[class*='recaptcha' i]",
    "[id*='g-recaptcha' i]",
]


def check_for_captcha(page: Page, tender_id: int | None = None) -> None:
    """Call this after every significant Playwright interaction on a GeM form page."""
    for selector in CAPTCHA_SELECTORS:
        if page.query_selector(selector):
            log_warning(
                phase=Phase.BID_PARTICIPATION,
                step="CAPTCHA Detected",
                tender_id=tender_id,
                detail={"selector": selector, "url": page.url},
            )
            alert_operator_for_captcha(tender_id, page.url)
            raise CaptchaDetectedError(f"CAPTCHA detected at {page.url} (selector: {selector})")


def alert_operator_for_captcha(tender_id: int | None, url: str) -> None:
    settings = get_settings()
    operator_email = settings.get("alerts", {}).get("email", {}).get("operator_addr")
    if operator_email:
        send_email(
            operator_email,
            "[Action Required] CAPTCHA blocking bid automation",
            f"A CAPTCHA was detected during bid submission automation.\nURL: {url}\nTender ID: {tender_id}\n"
            "Please log in and complete the CAPTCHA manually, then resume the automation.",
            tender_id=tender_id,
        )


def request_otp(tender_id: int, bid_id: str, deadline_minutes: int = 60) -> str:
    """
    Alerts the primary OTP holder, then polls a dashboard-backed table for
    the OTP value the human entered. Escalates to a backup holder at T-1h
    if no value has appeared and the deadline is approaching.
    """
    from sqlalchemy import text

    from src.audit_logging.db import get_session

    settings = get_settings()
    cfg = settings.get("human_approval", {})
    primary = settings.get("alerts", {}).get("email", {}).get("operator_addr")
    primary_phone = settings.get("alerts", {}).get("sms", {}).get("operator_number")
    backup = cfg.get("backup_otp_holder_email")
    backup_phone = cfg.get("backup_otp_holder_phone")

    if primary:
        send_email(primary, f"[OTP Needed] Bid {bid_id}", "Enter the OTP in the dashboard to continue submission.", tender_id=tender_id)
    if primary_phone:
        send_sms(primary_phone, f"OTP needed for bid {bid_id}. Check dashboard.", tender_id=tender_id)

    deadline = datetime.utcnow() + timedelta(minutes=deadline_minutes)
    escalated = False
    session = get_session()
    try:
        while datetime.utcnow() < deadline:
            row = session.execute(
                text("SELECT detail->>'otp' FROM bid_submissions WHERE tender_id = :tid"),
                {"tid": tender_id},
            ).first()
            if row and row[0]:
                return row[0]

            # Escalate at the halfway point if still nothing.
            if not escalated and datetime.utcnow() > deadline - timedelta(minutes=deadline_minutes // 2):
                escalated = True
                log_warning(phase=Phase.BID_PARTICIPATION, step="OTP Escalation", tender_id=tender_id, detail={"bid_id": bid_id})
                if backup:
                    send_email(backup, f"[OTP Needed — ESCALATED] Bid {bid_id}", "Primary holder unresponsive. Please enter the OTP in the dashboard.", tender_id=tender_id)
                if backup_phone:
                    send_sms(backup_phone, f"ESCALATED: OTP needed for bid {bid_id}.", tender_id=tender_id)

            time.sleep(15)
    finally:
        session.close()

    raise OTPTimeoutError(f"No OTP received for bid {bid_id} within {deadline_minutes} minutes")
