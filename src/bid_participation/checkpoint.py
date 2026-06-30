"""
checkpoint.py — Persists form-fill progress after each section, so a failed
or interrupted submission can resume from the last completed section rather
than starting over (which risks duplicate EMD payment, etc.).
"""
from __future__ import annotations

from sqlalchemy import text

from src.audit_logging.db import get_session


def get_checkpoint(tender_id: int) -> str | None:
    session = get_session()
    try:
        row = session.execute(
            text("SELECT checkpoint FROM bid_submissions WHERE tender_id = :tid"),
            {"tid": tender_id},
        ).first()
        return row[0] if row else None
    finally:
        session.close()


def save_checkpoint(tender_id: int, section: str, detail: dict | None = None) -> None:
    session = get_session()
    try:
        session.execute(
            text(
                """
                INSERT INTO bid_submissions (tender_id, status, checkpoint, detail)
                VALUES (:tender_id, 'in_progress', :checkpoint, :detail)
                ON CONFLICT (tender_id) DO UPDATE
                SET checkpoint = :checkpoint, status = 'in_progress', detail = :detail
                """
            ),
            {"tender_id": tender_id, "checkpoint": section, "detail": str(detail) if detail else None},
        )
        session.commit()
    finally:
        session.close()


def mark_submitted(tender_id: int, detail: dict | None = None) -> None:
    session = get_session()
    try:
        session.execute(
            text(
                """
                UPDATE bid_submissions
                SET status = 'submitted', submitted_at = NOW(), detail = :detail
                WHERE tender_id = :tender_id
                """
            ),
            {"tender_id": tender_id, "detail": str(detail) if detail else None},
        )
        session.execute(
            text("UPDATE tenders SET submission_status = 'submitted' WHERE id = :tid"),
            {"tid": tender_id},
        )
        session.commit()
    finally:
        session.close()


def mark_failed(tender_id: int, reason: str) -> None:
    session = get_session()
    try:
        session.execute(
            text("UPDATE bid_submissions SET status = 'failed', detail = :reason WHERE tender_id = :tid"),
            {"tid": tender_id, "reason": reason},
        )
        session.commit()
    finally:
        session.close()


def mark_needs_human(tender_id: int, reason: str) -> None:
    session = get_session()
    try:
        session.execute(
            text("UPDATE bid_submissions SET status = 'needs_human', detail = :reason WHERE tender_id = :tid"),
            {"tid": tender_id, "reason": reason},
        )
        session.commit()
    finally:
        session.close()
