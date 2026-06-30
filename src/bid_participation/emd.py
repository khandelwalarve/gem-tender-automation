"""
emd.py — Handles Earnest Money Deposit payment during bid submission.
EMD is a real money transaction, so this module never auto-confirms a
payment without checking exemption eligibility first, and always records
the outcome for audit purposes.
"""
from __future__ import annotations

from playwright.sync_api import Page

from src.audit_logging import Phase, log_decision, log_info
from src.common.schemas import TenderData

from .human_in_the_loop import check_for_captcha


class EMDPaymentError(Exception):
    pass


def determine_emd_requirement(tender: TenderData, profile: dict) -> tuple[bool, str]:
    """
    Returns (must_pay, reason). EMD exemption applies if the tender allows it
    AND the company qualifies as MSE/Startup per its profile.
    """
    ft = tender.financial_terms
    if ft.emd_amount_inr is None or ft.emd_amount_inr == 0:
        return False, "No EMD amount specified in tender"

    if ft.emd_exemption_available and (profile.get("is_mse") or profile.get("is_startup")):
        return False, "EMD exemption claimed (MSE/Startup status)"

    return True, f"EMD of INR {ft.emd_amount_inr} required"


def pay_emd(page: Page, tender_id: int, amount_inr: float) -> None:
    """
    Fills the EMD payment section of the GeM bid form. Actual payment gateway
    interaction (bank redirect, UTR entry) happens within the page the
    gateway redirects to; this function handles the GeM-side form only.
    """
    check_for_captcha(page, tender_id=tender_id)

    page.fill("input[name='emdAmount']", str(amount_inr))
    page.click("button#proceedToPayment")
    page.wait_for_load_state("networkidle")

    check_for_captcha(page, tender_id=tender_id)

    log_info(
        phase=Phase.BID_PARTICIPATION,
        step="EMD Payment Initiated",
        tender_id=tender_id,
        owner="automation",
        detail={"amount_inr": amount_inr},
    )


def confirm_emd_paid(page: Page, tender_id: int) -> bool:
    """Checks the GeM form for a payment confirmation indicator after gateway redirect."""
    confirmation = page.query_selector("div.payment-success, span.emd-confirmed")
    success = confirmation is not None

    log_decision(
        phase=Phase.BID_PARTICIPATION,
        step="EMD Payment Confirmation",
        decision="confirmed" if success else "not_confirmed",
        tender_id=tender_id,
        owner="automation",
    )

    return success
