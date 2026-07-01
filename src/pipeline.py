"""
pipeline.py — Top-level orchestration that runs a single Bid ID through the
entire pipeline, phase by phase, stopping early (and logging why) whenever
a phase can't proceed.

This is the function a scheduler / CLI / API endpoint should call per tender.
"""
from __future__ import annotations

from pathlib import Path

from src.audit_logging import Phase, log_info
from src.bid_participation import submit_bid
from src.common.schemas import DecisionOutcome
from src.decision_engine import run_decision_engine
from src.document_processing import process_document
from src.document_processing.processor import process_document_with_linked_files
from src.eligibility_engine import get_active_profile, run_eligibility_check
from src.feasibility_analysis import run_feasibility_analysis
from src.human_approval import route_for_approval
from src.risk_detection import detect_risks
from src.tender_acquisition import run_acquisition
from src.tender_understanding import save_tender_data, understand_tender


def _register_linked_file(session, tender_id: int, fetched) -> None:
    """Insert a fetched linked document into tender_files so it's tracked in the audit trail."""
    from sqlalchemy import text
    session.execute(
        text(
            """
            INSERT INTO tender_files (tender_id, file_name, file_hash, storage_path, source_url, file_type)
            VALUES (:tender_id, :file_name, :file_hash, :storage_path, :source_url, 'linked')
            ON CONFLICT (tender_id, file_hash) DO NOTHING
            """
        ),
        {
            "tender_id": tender_id,
            "file_name": fetched.file_name,
            "file_hash": fetched.file_hash,
            "storage_path": fetched.storage_path,
            "source_url": fetched.url,
        },
    )


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

    # ------------------------------------------------------------------ #
    # Phase 1 — Tender Acquisition                                        #
    # ------------------------------------------------------------------ #
    tender_id = run_acquisition(bid_id, headless=headless)
    if tender_id is None:
        summary["stage_reached"] = "tender_acquisition_failed"
        return summary
    summary["tender_id"] = tender_id
    summary["stage_reached"] = "acquired"

    # ------------------------------------------------------------------ #
    # Phase 2 — Document Processing (including linked documents)          #
    # ------------------------------------------------------------------ #
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
    all_file_paths: list[str] = list(file_rows)  # keeps track for Phase 9 upload

    for path in file_rows:
        linked_dir = str(Path(path).parent / "linked")

        # Process the main file AND discover any URLs it links to.
        main_doc, linked_files = process_document_with_linked_files(
            path,
            tender_id=tender_id,
            linked_files_dir=linked_dir,
        )

        if main_doc:
            all_chunks.extend(main_doc.chunks)

        if linked_files:
            # Register each newly discovered file in tender_files and process it.
            session = get_session()
            try:
                for lf in linked_files:
                    _register_linked_file(session, tender_id, lf)
                    all_file_paths.append(lf.storage_path)
                session.commit()
            finally:
                session.close()

            for lf in linked_files:
                linked_doc = process_document(lf.storage_path, tender_id=tender_id)
                if linked_doc:
                    all_chunks.extend(linked_doc.chunks)

    if not all_chunks:
        summary["stage_reached"] = "document_processing_failed"
        return summary
    summary["stage_reached"] = "documents_processed"
    summary["total_chunks"] = len(all_chunks)
    summary["linked_files_discovered"] = len(all_file_paths) - len(file_rows)

    # ------------------------------------------------------------------ #
    # Phase 3 — Tender Understanding                                      #
    # ------------------------------------------------------------------ #
    tender = understand_tender(all_chunks, tender_id=tender_id, bid_id=bid_id)
    if tender is None:
        summary["stage_reached"] = "tender_understanding_failed"
        return summary
    summary["stage_reached"] = "understood"
    save_tender_data(tender_id, tender)

    # ------------------------------------------------------------------ #
    # Phase 4 — Eligibility Engine                                        #
    # ------------------------------------------------------------------ #
    eligibility = run_eligibility_check(tender, tender_id=tender_id)
    if eligibility is None:
        summary["stage_reached"] = "eligibility_check_failed"
        return summary
    summary["stage_reached"] = "eligibility_checked"
    summary["eligibility_score"] = eligibility.score

    # ------------------------------------------------------------------ #
    # Phase 5 — Feasibility Analysis                                      #
    # ------------------------------------------------------------------ #
    feasibility = run_feasibility_analysis(tender, feasibility_pdf_path, tender_id=tender_id)
    summary["stage_reached"] = "feasibility_checked"

    # ------------------------------------------------------------------ #
    # Phase 6 — Risk Detection                                            #
    # ------------------------------------------------------------------ #
    risks = detect_risks(tender, tender_id=tender_id)
    summary["stage_reached"] = "risks_detected"
    summary["risk_count"] = len(risks)

    # ------------------------------------------------------------------ #
    # Phase 7 — Decision Engine                                           #
    # ------------------------------------------------------------------ #
    decision = run_decision_engine(tender, eligibility, feasibility, risks, tender_id=tender_id)
    summary["stage_reached"] = "decision_made"
    summary["outcome"] = decision.outcome.value

    # ------------------------------------------------------------------ #
    # Phase 8 / 9 — Human Approval or Auto Submit                        #
    # ------------------------------------------------------------------ #
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
    success = submit_bid(
        tender,
        tender_id,
        profile,
        quoted_price_inr,
        document_paths=all_file_paths,  # includes linked files now
        headless=headless,
    )
    summary["stage_reached"] = "submitted" if success else "submission_failed"
    return summary
