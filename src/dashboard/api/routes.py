"""
routes.py — REST API endpoints backing the React dashboard. Read-heavy:
tender list, tender detail/trace, error log, pending human reviews, and a
write endpoint for recording human approval decisions.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from src.audit_logging import (
    get_audit_log_page,
    get_decisions_for_tender,
    get_phase_failure_counts,
    get_recent_errors,
    get_tender_trace,
)
from src.audit_logging.db import get_session
from src.human_approval import record_human_decision

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/tenders")
def list_tenders(status: Optional[str] = None, limit: int = 50, offset: int = 0):
    session = get_session()
    try:
        if status:
            rows = session.execute(
                text(
                    """
                    SELECT id, bid_id, status, decision, submission_status, deadline, registered_at
                    FROM tenders WHERE status = :status
                    ORDER BY registered_at DESC LIMIT :limit OFFSET :offset
                    """
                ),
                {"status": status, "limit": limit, "offset": offset},
            ).mappings().all()
        else:
            rows = session.execute(
                text(
                    """
                    SELECT id, bid_id, status, decision, submission_status, deadline, registered_at
                    FROM tenders ORDER BY registered_at DESC LIMIT :limit OFFSET :offset
                    """
                ),
                {"limit": limit, "offset": offset},
            ).mappings().all()
        return {"items": [dict(r) for r in rows]}
    finally:
        session.close()


@router.get("/tenders/{tender_id}")
def get_tender_detail(tender_id: int):
    session = get_session()
    try:
        row = session.execute(
            text("SELECT * FROM tenders WHERE id = :tid"),
            {"tid": tender_id},
        ).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="Tender not found")
        return dict(row)
    finally:
        session.close()


@router.get("/tenders/{tender_id}/trace")
def get_trace(tender_id: int):
    return {"trace": get_tender_trace(tender_id)}


@router.get("/tenders/{tender_id}/decisions")
def get_decisions(tender_id: int):
    return {"decisions": get_decisions_for_tender(tender_id)}


@router.get("/errors")
def list_errors(limit: int = 50):
    return {"errors": get_recent_errors(limit=limit)}


@router.get("/errors/by-phase")
def errors_by_phase(since_days: int = 30):
    return {"counts": get_phase_failure_counts(since_days=since_days)}


@router.get("/audit-log")
def audit_log_feed(page: int = 1, page_size: int = 50, phase: Optional[str] = None, event_type: Optional[str] = None, tender_id: Optional[int] = None):
    return get_audit_log_page(page=page, page_size=page_size, phase=phase, event_type=event_type, tender_id=tender_id)


@router.get("/pending-reviews")
def pending_reviews():
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT hr.id, hr.tender_id, hr.assigned_to, hr.notified_at, t.bid_id, t.deadline
                FROM human_reviews hr
                JOIN tenders t ON t.id = hr.tender_id
                WHERE hr.decision IS NULL
                ORDER BY t.deadline ASC
                """
            )
        ).mappings().all()
        return {"items": [dict(r) for r in rows]}
    finally:
        session.close()


class ReviewDecisionRequest(BaseModel):
    decision: str   # "approved" | "approved_with_edits" | "rejected"
    edits: dict | None = None


@router.post("/reviews/{review_id}/decide")
def decide_review(review_id: int, body: ReviewDecisionRequest, tender_id: int):
    if body.decision not in ("approved", "approved_with_edits", "rejected"):
        raise HTTPException(status_code=400, detail="Invalid decision value")
    record_human_decision(review_id, tender_id, body.decision, edits=body.edits)
    return {"status": "ok"}


@router.get("/stats/pipeline-summary")
def pipeline_summary():
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE decision = 'auto_submit') AS auto_submit,
                    COUNT(*) FILTER (WHERE decision = 'human_approval') AS human_approval,
                    COUNT(*) FILTER (WHERE decision = 'rejected') AS rejected,
                    COUNT(*) FILTER (WHERE submission_status = 'submitted') AS submitted
                FROM tenders
                """
            )
        ).mappings().first()
        return dict(row) if row else {}
    finally:
        session.close()
