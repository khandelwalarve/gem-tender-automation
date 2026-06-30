"""analyzer.py — Phase 5 orchestration: load thresholds, run gate checks, persist + log."""
from __future__ import annotations

from sqlalchemy import text

from src.audit_logging import Phase, log_decision
from src.audit_logging.db import get_session
from src.common.schemas import FeasibilityResult, TenderData

from .gate import analyse_feasibility
from .thresholds import get_thresholds


def save_feasibility_result(tender_id: int, result: FeasibilityResult) -> None:
    session = get_session()
    try:
        session.execute(
            text(
                """
                INSERT INTO feasibility_results (tender_id, is_feasible, report)
                VALUES (:tender_id, :is_feasible, :report)
                """
            ),
            {
                "tender_id": tender_id,
                "is_feasible": result.is_feasible,
                "report": result.model_dump_json(),
            },
        )
        session.commit()
    finally:
        session.close()


def run_feasibility_analysis(
    tender: TenderData,
    feasibility_pdf_path: str | None = None,
    tender_id: int | None = None,
) -> FeasibilityResult:
    thresholds = get_thresholds(feasibility_pdf_path)
    result = analyse_feasibility(tender, thresholds)

    if tender_id is not None:
        save_feasibility_result(tender_id, result)

    log_decision(
        phase=Phase.FEASIBILITY_ANALYSIS,
        step="Feasibility Evaluated",
        decision="feasible" if result.is_feasible else "not_feasible",
        tender_id=tender_id,
        owner="rules_engine",
        detail={"checks": [c.model_dump() for c in result.checks]},
    )

    return result
