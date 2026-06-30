"""Audit & Logging: immutable event log for every phase/step/failure."""
from .logger import log_info, log_warning, log_error, log_decision
from .models import AuditEntry, EventType, Phase, ExceptionDetail
from .queries import (
    get_tender_trace,
    get_recent_errors,
    get_decisions_for_tender,
    get_phase_failure_counts,
    get_audit_log_page,
)

__all__ = [
    "log_info",
    "log_warning",
    "log_error",
    "log_decision",
    "AuditEntry",
    "EventType",
    "Phase",
    "ExceptionDetail",
    "get_tender_trace",
    "get_recent_errors",
    "get_decisions_for_tender",
    "get_phase_failure_counts",
    "get_audit_log_page",
]
