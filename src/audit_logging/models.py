"""Pydantic models for audit log entries."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DECISION = "decision"


class Phase(str, Enum):
    TENDER_ACQUISITION = "tender_acquisition"
    DOCUMENT_PROCESSING = "document_processing"
    TENDER_UNDERSTANDING = "tender_understanding"
    ELIGIBILITY_ENGINE = "eligibility_engine"
    FEASIBILITY_ANALYSIS = "feasibility_analysis"
    RISK_DETECTION = "risk_detection"
    DECISION_ENGINE = "decision_engine"
    HUMAN_APPROVAL = "human_approval"
    BID_PARTICIPATION = "bid_participation"
    AUDIT_LOGGING = "audit_logging"
    DASHBOARD = "dashboard"


class AuditEntry(BaseModel):
    """A single immutable audit log record."""

    tender_id: int | None = None
    phase: Phase
    step: str
    owner: str | None = None          # "automation" | "ai_engine" | "rules_engine" | "human"
    event_type: EventType
    detail: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=datetime.utcnow)


class ExceptionDetail(BaseModel):
    """Standard structure for error detail payloads."""

    exception_type: str
    message: str
    traceback: str | None = None
    bid_id: str | None = None
    phase: str | None = None
    step: str | None = None
