"""detector.py — Phase 6 orchestration: run all risk checks, persist + log results."""
from __future__ import annotations

from sqlalchemy import text

from src.audit_logging import Phase, log_decision
from src.audit_logging.db import get_session
from src.common.schemas import RiskFlag, TenderData

from .llm_based import detect_semantic_risks
from .rule_based import check_excessive_penalty, check_missing_dates, check_split_tender


def save_risk_flags(tender_id: int, flags: list[RiskFlag]) -> None:
    if not flags:
        return
    session = get_session()
    try:
        for flag in flags:
            session.execute(
                text(
                    """
                    INSERT INTO risk_flags (tender_id, flag_type, severity, description, detail)
                    VALUES (:tender_id, :flag_type, :severity, :description, :detail)
                    """
                ),
                {
                    "tender_id": tender_id,
                    "flag_type": flag.flag_type.value,
                    "severity": flag.severity.value,
                    "description": flag.description,
                    "detail": flag.model_dump_json(include={"detail"}),
                },
            )
        session.commit()
    finally:
        session.close()


def detect_risks(
    tender: TenderData,
    tender_id: int | None = None,
    related_tender_values: list[float] | None = None,
) -> list[RiskFlag]:
    flags: list[RiskFlag] = []
    flags += check_missing_dates(tender)
    flags += check_excessive_penalty(tender)
    flags += check_split_tender(tender, related_tender_values or [])
    flags += detect_semantic_risks(tender)

    if tender_id is not None:
        save_risk_flags(tender_id, flags)

    log_decision(
        phase=Phase.RISK_DETECTION,
        step="Risk Scan Completed",
        decision=f"{len(flags)} risk(s) found",
        tender_id=tender_id,
        owner="ai_engine",
        detail={"flags": [f.model_dump(mode="json") for f in flags]},
    )

    return flags
