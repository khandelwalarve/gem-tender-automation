"""orchestrator.py — Phase 7 orchestration: persist decision, update tender status, log."""
from __future__ import annotations

from sqlalchemy import text

from src.audit_logging import Phase, log_decision
from src.audit_logging.db import get_session
from src.common.schemas import Decision, DecisionOutcome, EligibilityResult, FeasibilityResult, RiskFlag, TenderData

from .rules import make_decision


def save_decision(tender_id: int, decision: Decision) -> None:
    session = get_session()
    try:
        session.execute(
            text(
                """
                INSERT INTO decisions (tender_id, outcome, score, reasons)
                VALUES (:tender_id, :outcome, :score, :reasons)
                ON CONFLICT (tender_id) DO UPDATE
                SET outcome = :outcome, score = :score, reasons = :reasons, decided_at = NOW()
                """
            ),
            {
                "tender_id": tender_id,
                "outcome": decision.outcome.value,
                "score": decision.score,
                "reasons": decision.model_dump_json(include={"reasons"}),
            },
        )
        session.execute(
            text("UPDATE tenders SET decision = :decision WHERE id = :tid"),
            {"decision": decision.outcome.value, "tid": tender_id},
        )
        session.commit()
    finally:
        session.close()


def run_decision_engine(
    tender: TenderData,
    eligibility: EligibilityResult,
    feasibility: FeasibilityResult,
    risks: list[RiskFlag],
    tender_id: int | None = None,
) -> Decision:
    decision = make_decision(tender, eligibility, feasibility, risks)

    if tender_id is not None:
        save_decision(tender_id, decision)

    log_decision(
        phase=Phase.DECISION_ENGINE,
        step="Final Decision",
        decision=decision.outcome.value,
        tender_id=tender_id,
        owner="rules_engine",
        detail={"score": decision.score, "reasons": decision.reasons},
    )

    return decision
