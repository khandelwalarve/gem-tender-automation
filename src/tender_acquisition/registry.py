"""
registry.py — Register a tender (and its files) in the database once the
completeness check has passed. Also handles corrigendum re-checks: re-hashing
files for active bids to detect amendments published after initial download.
"""
from __future__ import annotations

from sqlalchemy import text

from src.audit_logging import Phase, log_decision, log_error, log_info, log_warning
from src.audit_logging.db import get_session

from .download import DownloadedFile, check_completeness, download_tender_files, IncompleteDownloadError
from .session import SessionExpiredError, assert_session_valid, load_context


def register_tender(bid_id: str, files: list[DownloadedFile]) -> int:
    """Insert a tender + its files into the DB. Returns the new tender row id."""
    session = get_session()
    try:
        result = session.execute(
            text(
                """
                INSERT INTO tenders (bid_id, status)
                VALUES (:bid_id, 'registered')
                ON CONFLICT (bid_id) DO UPDATE SET status = 'registered'
                RETURNING id
                """
            ),
            {"bid_id": bid_id},
        )
        tender_id = result.scalar_one()

        for f in files:
            session.execute(
                text(
                    """
                    INSERT INTO tender_files (tender_id, file_name, file_hash, storage_path)
                    VALUES (:tender_id, :file_name, :file_hash, :storage_path)
                    """
                ),
                {
                    "tender_id": tender_id,
                    "file_name": f.file_name,
                    "file_hash": f.file_hash,
                    "storage_path": f.storage_path,
                },
            )
        session.commit()
        return tender_id
    finally:
        session.close()


def get_existing_file_hashes(tender_id: int) -> set[str]:
    session = get_session()
    try:
        rows = session.execute(
            text("SELECT file_hash FROM tender_files WHERE tender_id = :tid"),
            {"tid": tender_id},
        ).scalars().all()
        return set(rows)
    finally:
        session.close()


def run_acquisition(bid_id: str, headless: bool = True) -> int | None:
    """
    Full Phase 1 pipeline for a single bid:
    1. Restore GeM session (alert + abort if expired)
    2. Download all attachments
    3. Run completeness check
    4. Register tender + files in DB

    Returns the tender_id on success, None if it could not proceed.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            context = load_context(p, headless=headless)
        except SessionExpiredError as e:
            log_error(phase=Phase.TENDER_ACQUISITION, step="Restore Session", exc=e, bid_id=bid_id)
            return None

        try:
            assert_session_valid(context)
        except SessionExpiredError as e:
            log_error(phase=Phase.TENDER_ACQUISITION, step="Verify Session", exc=e, bid_id=bid_id)
            context.browser.close()
            return None

        log_info(phase=Phase.TENDER_ACQUISITION, step="Session Verified", owner="automation", detail={"bid_id": bid_id})

        try:
            files = download_tender_files(context, bid_id)
            check_completeness(files)
        except IncompleteDownloadError as e:
            log_error(phase=Phase.TENDER_ACQUISITION, step="Download Tender Files", exc=e, bid_id=bid_id)
            context.browser.close()
            return None
        except Exception as e:  # noqa: BLE001
            log_error(phase=Phase.TENDER_ACQUISITION, step="Download Tender Files", exc=e, bid_id=bid_id)
            context.browser.close()
            return None

        context.browser.close()

    tender_id = register_tender(bid_id, files)
    log_decision(
        phase=Phase.TENDER_ACQUISITION,
        step="Register Tender",
        decision="registered",
        tender_id=tender_id,
        detail={"bid_id": bid_id, "file_count": len(files)},
    )
    return tender_id


def check_for_corrigendum(bid_id: str, tender_id: int, headless: bool = True) -> bool:
    """
    Re-downloads tender files and compares hashes against what's stored.
    Returns True if a change (corrigendum) was detected.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            context = load_context(p, headless=headless)
            assert_session_valid(context)
            new_files = download_tender_files(context, bid_id)
        except (SessionExpiredError, IncompleteDownloadError) as e:
            log_error(phase=Phase.TENDER_ACQUISITION, step="Corrigendum Check", exc=e, bid_id=bid_id, tender_id=tender_id)
            return False
        finally:
            try:
                context.browser.close()
            except Exception:  # noqa: BLE001
                pass

    existing_hashes = get_existing_file_hashes(tender_id)
    new_hashes = {f.file_hash for f in new_files}

    if new_hashes != existing_hashes:
        log_warning(
            phase=Phase.TENDER_ACQUISITION,
            step="Corrigendum Detected",
            tender_id=tender_id,
            detail={"bid_id": bid_id, "new_file_count": len(new_files)},
        )
        register_tender(bid_id, new_files)
        return True

    return False
