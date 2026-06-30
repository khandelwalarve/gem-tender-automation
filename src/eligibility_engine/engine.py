"""engine.py — Phase 4 orchestration: load profile, run matcher, persist + log result."""
from __future__ import annotations

from sqlalchemy import text

from src.audit_logging import Phase, log_decision, log_error
from src.audit_logging.db import get_session
from src.common.schemas import EligibilityResult, TenderData

from .matcher import evaluate_eligibility
from .profile import get_active_profile


class NoActiveProfileError(Exception):
    pass


def save_eligibility_result(tender_id: int, result: EligibilityResult) -> None:
    session = get_session()
    try:
        session.execute(
            text(
                """
                INSERT INTO eligibility_results (tender_id, score, is_eligible, report)
                VALUES (:tender_id, :score, :is_eligible, :report)
                """
            ),
            {
                "tender_id": tender_id,
                "score": result.score,
                "is_eligible": result.is_eligible,
                "report": result.model_dump_json(),
            },
        )
        session.commit()
    finally:
        session.close()


def run_eligibility_check(tender: TenderData, tender_id: int | None = None) -> EligibilityResult | None:
    profile = get_active_profile()
    if profile is None:
        log_error(
            phase=Phase.ELIGIBILITY_ENGINE,
            step="Load Company Profile",
            exc=NoActiveProfileError("No active company profile found in database"),
            tender_id=tender_id,
            bid_id=tender.metadata.bid_id,
        )
        return None

    result = evaluate_eligibility(tender, profile)

    if tender_id is not None:
        save_eligibility_result(tender_id, result)

    log_decision(
        phase=Phase.ELIGIBILITY_ENGINE,
        step="Eligibility Evaluated",
        decision="eligible" if result.is_eligible else "not_eligible",
        tender_id=tender_id,
        owner="rules_engine",
        detail={"score": result.score, "low_confidence_flags": result.low_confidence_flags},
    )

    return result
