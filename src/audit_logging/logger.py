"""
logger.py — Core audit logging functions.

Every phase/step should call one of these instead of writing directly to the DB.
All writes are append-only; rows are never updated or deleted.

Usage
-----
from src.audit_logging.logger import log_info, log_warning, log_error, log_decision

log_info(
    tender_id=42,
    phase=Phase.TENDER_ACQUISITION,
    step="Download Tender Files",
    owner="automation",
    detail={"files": ["notice.pdf", "annexure_1.pdf"]},
)

log_error(
    tender_id=42,
    phase=Phase.BID_PARTICIPATION,
    step="Submit Bid",
    exc=e,
    bid_id="BID-2024-001",
)
"""
from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime
from typing import Any

from sqlalchemy import text

from .db import get_session
from .models import AuditEntry, EventType, ExceptionDetail, Phase

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal write
# ---------------------------------------------------------------------------

def _write(entry: AuditEntry) -> None:
    """Insert one audit row. Swallows DB errors so logging never crashes the caller."""
    try:
        session = get_session()
        session.execute(
            text(
                """
                INSERT INTO audit_log (tender_id, phase, step, owner, event_type, detail, occurred_at)
                VALUES (:tender_id, :phase, :step, :owner, :event_type, :detail, :occurred_at)
                """
            ),
            {
                "tender_id": entry.tender_id,
                "phase": entry.phase.value,
                "step": entry.step,
                "owner": entry.owner,
                "event_type": entry.event_type.value,
                "detail": json.dumps(entry.detail),
                "occurred_at": entry.occurred_at,
            },
        )
        session.commit()
    except Exception as db_exc:  # noqa: BLE001
        _log.error("audit_logging: failed to write row — %s", db_exc)
    finally:
        try:
            session.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def log_info(
    phase: Phase,
    step: str,
    tender_id: int | None = None,
    owner: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Log an informational event (normal progress)."""
    _write(
        AuditEntry(
            tender_id=tender_id,
            phase=phase,
            step=step,
            owner=owner,
            event_type=EventType.INFO,
            detail=detail or {},
        )
    )


def log_warning(
    phase: Phase,
    step: str,
    tender_id: int | None = None,
    owner: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Log a non-fatal warning (e.g. low OCR confidence, stale profile)."""
    _write(
        AuditEntry(
            tender_id=tender_id,
            phase=phase,
            step=step,
            owner=owner,
            event_type=EventType.WARNING,
            detail=detail or {},
        )
    )


def log_error(
    phase: Phase,
    step: str,
    exc: Exception,
    tender_id: int | None = None,
    bid_id: str | None = None,
    owner: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Log a failure event.

    Captures exception type, message, traceback, bid_id, phase, and step
    as required by the framework spec (Audit & Logging — Error & Exception Log).
    """
    err = ExceptionDetail(
        exception_type=type(exc).__name__,
        message=str(exc),
        traceback=traceback.format_exc(),
        bid_id=bid_id,
        phase=phase.value,
        step=step,
    )
    detail = err.model_dump()
    if extra:
        detail.update(extra)

    _write(
        AuditEntry(
            tender_id=tender_id,
            phase=phase,
            step=step,
            owner=owner,
            event_type=EventType.ERROR,
            detail=detail,
        )
    )


def log_decision(
    phase: Phase,
    step: str,
    decision: str,
    tender_id: int | None = None,
    owner: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Log an AI or rules-engine decision (e.g. Auto Submit, Human Approval, Reject)."""
    payload = {"decision": decision}
    if detail:
        payload.update(detail)

    _write(
        AuditEntry(
            tender_id=tender_id,
            phase=phase,
            step=step,
            owner=owner,
            event_type=EventType.DECISION,
            detail=payload,
        )
    )
