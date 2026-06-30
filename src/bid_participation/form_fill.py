"""
form_fill.py — Fills the GeM bid submission form section by section,
checkpointing after each section so a crash mid-submission can resume
rather than restart (which would risk double EMD payment / duplicate bids).
"""
from __future__ import annotations

from playwright.sync_api import Page

from src.audit_logging import Phase, log_info
from src.common.schemas import TenderData

from .checkpoint import save_checkpoint
from .human_in_the_loop import check_for_captcha

FORM_SECTIONS = ["technical_details", "commercial_details", "documents_upload", "declaration", "review"]


def fill_technical_details(page: Page, tender: TenderData, tender_id: int) -> None:
    check_for_captcha(page, tender_id=tender_id)
    for spec in tender.technical_specifications:
        # Selector pattern depends on the live GeM form structure;
        # this targets fields by data-item-name attribute as a stable anchor.
        selector = f"input[data-item-name='{spec.item_name}']"
        if page.query_selector(selector):
            page.fill(selector, str(spec.quantity or ""))
    save_checkpoint(tender_id, "technical_details")
    log_info(phase=Phase.BID_PARTICIPATION, step="Technical Details Filled", tender_id=tender_id, owner="automation")


def fill_commercial_details(page: Page, tender: TenderData, tender_id: int, quoted_price_inr: float) -> None:
    check_for_captcha(page, tender_id=tender_id)
    page.fill("input[name='quotedPrice']", str(quoted_price_inr))
    save_checkpoint(tender_id, "commercial_details", detail={"quoted_price_inr": quoted_price_inr})
    log_info(phase=Phase.BID_PARTICIPATION, step="Commercial Details Filled", tender_id=tender_id, owner="automation")


def upload_documents(page: Page, tender_id: int, document_paths: list[str]) -> None:
    check_for_captcha(page, tender_id=tender_id)
    file_input = page.query_selector("input[type='file']")
    if file_input:
        file_input.set_input_files(document_paths)
    save_checkpoint(tender_id, "documents_upload", detail={"document_count": len(document_paths)})
    log_info(phase=Phase.BID_PARTICIPATION, step="Documents Uploaded", tender_id=tender_id, owner="automation", detail={"count": len(document_paths)})


def accept_declaration(page: Page, tender_id: int) -> None:
    check_for_captcha(page, tender_id=tender_id)
    checkbox = page.query_selector("input[type='checkbox'][name='declaration']")
    if checkbox:
        checkbox.check()
    save_checkpoint(tender_id, "declaration")
    log_info(phase=Phase.BID_PARTICIPATION, step="Declaration Accepted", tender_id=tender_id, owner="automation")


def get_resume_section(tender_id: int) -> str:
    from .checkpoint import get_checkpoint

    checkpoint = get_checkpoint(tender_id)
    if checkpoint is None:
        return FORM_SECTIONS[0]
    idx = FORM_SECTIONS.index(checkpoint)
    next_idx = min(idx + 1, len(FORM_SECTIONS) - 1)
    return FORM_SECTIONS[next_idx]
