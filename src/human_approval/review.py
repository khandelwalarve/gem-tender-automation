"""
review.py — Creates a human_reviews record when a tender is routed for
approval, tracks deadline reminders and auto-rejection if a reviewer doesn't
respond in time, and records the final human decision.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from src.audit_logging import Phase, log_decision, log_warning
from src.audit_logging.db import get_session
from src.common.config import get_settings

from .notify import notify_reviewer, send_email


def create_review_request(tender_id: int, bid_id: str, reviewer_email: str, reviewer_phone: str | None, summary: str) -> int:
    session = get_session()
    try:
        result = session.execute(
            text(
                """
                INSERT INTO human_reviews (tender_id, assigned_to, notified_at)
                VALUES (:tender_id, :assigned_to, NOW())
                RETURNING id
                """
            ),
            {"tender_id": tender_id, "assigned_to": reviewer_email},
        )
        review_id = result.scalar_one()
        session.commit()
    finally:
        session.close()

    notify_reviewer(reviewer_email, reviewer_phone, tender_id, bid_id, summary)
    return review_id


def record_human_decision(review_id: int, tender_id: int, decision: str, edits: dict | None = None) -> None:
    """decision: 'approved' | 'approved_with_edits' | 'rejected'"""
    session = get_session()
    try:
        session.execute(
            text(
                """
                UPDATE human_reviews
                SET decision = :decision, decided_at = NOW(), edits = :edits
                WHERE id = :review_id
                """
            ),
            {"decision": decision, "edits": str(edits) if edits else None, "review_id": review_id},
        )
        session.commit()
    finally:
        session.close()

    log_decision(
        phase=Phase.HUMAN_APPROVAL,
        step="Human Decision Recorded",
        decision=decision,
        tender_id=tender_id,
        owner="human",
        detail={"review_id": review_id, "edits": edits or {}},
    )


def check_pending_deadlines() -> None:
    """
    Scheduled job: finds reviews still pending close to the bid deadline and
    sends a reminder, or auto-rejects if the deadline is imminent and no
    decision has been made. Should be run periodically (e.g. every 30 min).
    """
    settings = get_settings()
    cfg = settings.get("human_approval", {})
    reminder_hours = cfg.get("reminder_hours_before_deadline", 24)
    auto_reject_hours = cfg.get("auto_reject_hours_before_deadline", 2)

    session = get_session()
    try:
        pending = session.execute(
            text(
                """
                SELECT hr.id AS review_id, hr.tender_id, hr.assigned_to, t.bid_id, t.deadline
                FROM human_reviews hr
                JOIN tenders t ON t.id = hr.tender_id
                WHERE hr.decision IS NULL AND t.deadline IS NOT NULL
                """
            )
        ).mappings().all()

        now = datetime.utcnow()
        for row in pending:
            deadline = row["deadline"].replace(tzinfo=None)
            hours_left = (deadline - now).total_seconds() / 3600

            if hours_left <= auto_reject_hours:
                record_human_decision(
                    row["review_id"],
                    row["tender_id"],
                    "rejected",
                    edits={"reason": "auto-rejected: deadline passed without review"},
                )
                log_warning(
                    phase=Phase.HUMAN_APPROVAL,
                    step="Auto-Reject (Deadline Passed)",
                    tender_id=row["tender_id"],
                    detail={"bid_id": row["bid_id"], "hours_left": hours_left},
                )
            elif hours_left <= reminder_hours:
                send_email(
                    row["assigned_to"],
                    f"[Reminder] Tender {row['bid_id']} approval due in {hours_left:.1f} hours",
                    f"This tender still needs your review. Deadline: {deadline}",
                    tender_id=row["tender_id"],
                )
    finally:
        session.close()
