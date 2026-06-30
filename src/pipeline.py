"""
pipeline.py — Top-level orchestration that runs a single Bid ID through the
entire pipeline, phase by phase, stopping early (and logging why) whenever
a phase can't proceed.

This is the function a scheduler / CLI / API endpoint should call per tender.
"""
from __future__ import annotations

from src.audit_logging import Phase, log_decision, log_info
from src.bid_participation import submit_bid
from src.common.schemas import DecisionOutcome
from src.decision_engine import run_decision_engine
from src.document_processing import process_document
from src.eligibility_engine import get_active_profile, run_eligibility_check
from src.feasibility_analysis import run_feasibility_analysis
from src.human_approval import route_for_approval
from src.risk_detection import detect_risks
from src.tender_acquisition import run_acquisition
from src.tender_understanding import understand_tender


def run_pipeline(
    bid_id: str,
    feasibility_pdf_path: str | None = None,
    reviewer_email: str | None = None,
    reviewer_phone: str | None = None,
    quoted_price_inr: float | None = None,
    headless: bool = True,
) -> dict:
    """
    Runs the full pipeline for one Bid ID. Returns a summary dict describing
    how far the pipeline got and the final outcome.
    """
    summary: dict = {"bid_id": bid_id, "stage_reached": None, "outcome": None}

    # Phase 1
    tender_id = run_acquisition(bid_id, headless=headless)
    if tender_id is None:
        summary["stage_reached"] = "tender_acquisition_failed"
        return summary
    summary["tender_id"] = tender_id
    summary["stage_reached"] = "acquired"

    # Phase 2 — process every downloaded file, concatenate chunks.
    from sqlalchemy import text

    from src.audit_logging.db import get_session

    session = get_session()
    try:
        file_rows = session.execute(
            text("SELECT storage_path FROM tender_files WHERE tender_id = :tid"),
            {"tid": tender_id},
        ).scalars().all()
    finally:
        session.close()

    all_chunks: list[str] = []
    for path in file_rows:
        processed = process_document(path, tender_id=tender_id)
        if processed:
            all_chunks.extend(processed.chunks)

    if not all_chunks:
        summary["stage_reached"] = "document_processing_failed"
        return summary
    summary["stage_reached"] = "documents_processed"

    # Phase 3
    tender = understand_tender(all_chunks, tender_id=tender_id, bid_id=bid_id)
    if tender is None:
        summary["stage_reached"] = "tender_understanding_failed"
        return summary
    summary["stage_reached"] = "understood"

    from src.tender_understanding import save_tender_data
    save_tender_data(tender_id, tender)

    # Phase 4
    eligibility = run_eligibility_check(tender, tender_id=tender_id)
    if eligibility is None:
        summary["stage_reached"] = "eligibility_check_failed"
        return summary
    summary["stage_reached"] = "eligibility_checked"
    summary["eligibility_score"] = eligibility.score

    # Phase 5
    feasibility = run_feasibility_analysis(tender, feasibility_pdf_path, tender_id=tender_id)
    summary["stage_reached"] = "feasibility_checked"

    # Phase 6
    risks = detect_risks(tender, tender_id=tender_id)
    summary["stage_reached"] = "risks_detected"
    summary["risk_count"] = len(risks)

    # Phase 7
    decision = run_decision_engine(tender, eligibility, feasibility, risks, tender_id=tender_id)
    summary["stage_reached"] = "decision_made"
    summary["outcome"] = decision.outcome.value

    # Phase 8 / 9
    if decision.outcome == DecisionOutcome.REJECTED:
        log_info(phase=Phase.DECISION_ENGINE, step="Pipeline Complete (Rejected)", tender_id=tender_id)
        return summary

    if decision.outcome == DecisionOutcome.HUMAN_APPROVAL:
        if not reviewer_email:
            summary["stage_reached"] = "human_approval_skipped_no_reviewer_configured"
            return summary
        route_for_approval(tender, decision, eligibility, risks, tender_id, reviewer_email, reviewer_phone)
        summary["stage_reached"] = "routed_for_human_approval"
        return summary

    # AUTO_SUBMIT
    if quoted_price_inr is None:
        summary["stage_reached"] = "auto_submit_blocked_no_price"
        return summary

    profile = get_active_profile() or {}
    success = submit_bid(tender, tender_id, profile, quoted_price_inr, document_paths=list(file_rows), headless=headless)
    summary["stage_reached"] = "submitted" if success else "submission_failed"
    return summary
