"""
queries.py — Read-side helpers for the audit log.

These power the dashboard's "Process Trace" and "Error & Exception Log" views,
and the periodic summary reports.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from .db import get_session


def get_tender_trace(tender_id: int) -> list[dict[str, Any]]:
    """Full chronological trace of every step for one tender (for drill-down view)."""
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT id, tender_id, phase, step, owner, event_type, detail, occurred_at
                FROM audit_log
                WHERE tender_id = :tender_id
                ORDER BY occurred_at ASC
                """
            ),
            {"tender_id": tender_id},
        ).mappings().all()
        return [dict(r) for r in rows]
    finally:
        session.close()


def get_recent_errors(limit: int = 50) -> list[dict[str, Any]]:
    """Most recent error events across all tenders, for the Error & Exception Log view."""
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT id, tender_id, phase, step, owner, detail, occurred_at
                FROM audit_log
                WHERE event_type = 'error'
                ORDER BY occurred_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
        return [dict(r) for r in rows]
    finally:
        session.close()


def get_decisions_for_tender(tender_id: int) -> list[dict[str, Any]]:
    """All decision events for one tender (eligibility, feasibility, final decision, human review)."""
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT id, phase, step, owner, detail, occurred_at
                FROM audit_log
                WHERE tender_id = :tender_id AND event_type = 'decision'
                ORDER BY occurred_at ASC
                """
            ),
            {"tender_id": tender_id},
        ).mappings().all()
        return [dict(r) for r in rows]
    finally:
        session.close()


def get_phase_failure_counts(since_days: int = 30) -> list[dict[str, Any]]:
    """
    Count of errors per phase over the trailing window — used for the
    "which phase fails most often" dashboard widget.
    """
    since = datetime.utcnow() - timedelta(days=since_days)
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT phase, COUNT(*) AS error_count
                FROM audit_log
                WHERE event_type = 'error' AND occurred_at >= :since
                GROUP BY phase
                ORDER BY error_count DESC
                """
            ),
            {"since": since},
        ).mappings().all()
        return [dict(r) for r in rows]
    finally:
        session.close()


def get_audit_log_page(
    page: int = 1,
    page_size: int = 50,
    phase: str | None = None,
    event_type: str | None = None,
    tender_id: int | None = None,
) -> dict[str, Any]:
    """Paginated, filterable audit log feed for the dashboard's main log view."""
    session = get_session()
    try:
        filters = []
        params: dict[str, Any] = {"limit": page_size, "offset": (page - 1) * page_size}

        if phase:
            filters.append("phase = :phase")
            params["phase"] = phase
        if event_type:
            filters.append("event_type = :event_type")
            params["event_type"] = event_type
        if tender_id is not None:
            filters.append("tender_id = :tender_id")
            params["tender_id"] = tender_id

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        rows = session.execute(
            text(
                f"""
                SELECT id, tender_id, phase, step, owner, event_type, detail, occurred_at
                FROM audit_log
                {where_clause}
                ORDER BY occurred_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

        total = session.execute(
            text(f"SELECT COUNT(*) FROM audit_log {where_clause}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        ).scalar_one()

        return {
            "items": [dict(r) for r in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    finally:
        session.close()
