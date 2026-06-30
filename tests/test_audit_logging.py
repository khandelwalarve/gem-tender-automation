"""
Tests for the audit_logging module. Uses SQLite in-memory via DATABASE_URL
override so no real Postgres is needed.
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from sqlalchemy import text

from src.audit_logging.db import get_engine, get_session
from src.audit_logging.logger import log_info, log_warning, log_error, log_decision
from src.audit_logging.models import Phase
from src.audit_logging.queries import (
    get_tender_trace,
    get_recent_errors,
    get_decisions_for_tender,
)


@pytest.fixture(autouse=True)
def setup_schema():
    """Create a minimal audit_log table compatible with SQLite for testing."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tender_id INTEGER,
                    phase TEXT NOT NULL,
                    step TEXT NOT NULL,
                    owner TEXT,
                    event_type TEXT NOT NULL,
                    detail TEXT,
                    occurred_at TIMESTAMP
                )
                """
            )
        )
        conn.commit()
    yield
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM audit_log"))
        conn.commit()


def test_log_info_writes_row():
    log_info(phase=Phase.TENDER_ACQUISITION, step="Download Files", tender_id=1, detail={"count": 3})
    trace = get_tender_trace(1)
    assert len(trace) == 1
    assert trace[0]["event_type"] == "info"
    assert trace[0]["step"] == "Download Files"


def test_log_error_captures_exception_detail():
    try:
        raise ValueError("bad bid id")
    except ValueError as e:
        log_error(phase=Phase.BID_PARTICIPATION, step="Submit Bid", exc=e, tender_id=2, bid_id="BID-001")

    errors = get_recent_errors()
    assert len(errors) == 1
    detail = errors[0]["detail"]
    assert "ValueError" in detail
    assert "bad bid id" in detail


def test_log_decision_is_queryable():
    log_decision(
        phase=Phase.DECISION_ENGINE,
        step="Final Decision",
        decision="human_approval",
        tender_id=3,
        detail={"score": 0.72},
    )
    decisions = get_decisions_for_tender(3)
    assert len(decisions) == 1
    assert "human_approval" in decisions[0]["detail"]


def test_log_warning_does_not_raise():
    # Should not throw even with no tender_id
    log_warning(phase=Phase.DOCUMENT_PROCESSING, step="OCR Quality Check", detail={"confidence": 0.4})
