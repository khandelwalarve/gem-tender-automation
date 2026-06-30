"""
submitter.py — Phase 9 orchestration: full bid submission flow with resume
support, EMD payment, OTP verification, and final submission confirmation.
"""
from __future__ import annotations

from src.audit_logging import Phase, log_decision, log_error
from src.common.schemas import TenderData

from .checkpoint import get_checkpoint, mark_failed, mark_needs_human, mark_submitted, save_checkpoint
from .emd import EMDPaymentError, confirm_emd_paid, determine_emd_requirement, pay_emd
from .form_fill import accept_declaration, fill_commercial_details, fill_technical_details, upload_documents
from .human_in_the_loop import CaptchaDetectedError, OTPTimeoutError, request_otp


def submit_bid(
    tender: TenderData,
    tender_id: int,
    profile: dict,
    quoted_price_inr: float,
    document_paths: list[str],
    headless: bool = True,
) -> bool:
    """
    Full bid submission flow. Returns True on success.
    On CAPTCHA or OTP issues, marks the submission as needing human takeover
    rather than failing silently — the checkpoint lets a human or a retry
    resume from where automation stopped.
    """
    from playwright.sync_api import sync_playwright

    from src.tender_acquisition.session import assert_session_valid, load_context

    resume_point = get_checkpoint(tender_id)

    with sync_playwright() as p:
        try:
            context = load_context(p, headless=headless)
            assert_session_valid(context)
            page = context.new_page()
            page.goto(f"https://bidplus.gem.gov.in/bid/{tender.metadata.bid_id}/participate")
            page.wait_for_load_state("networkidle")

            if resume_point is None or resume_point == "technical_details":
                fill_technical_details(page, tender, tender_id)

            if resume_point in (None, "technical_details", "commercial_details"):
                fill_commercial_details(page, tender, tender_id, quoted_price_inr)

            must_pay_emd, reason = determine_emd_requirement(tender, profile)
            if must_pay_emd:
                pay_emd(page, tender_id, tender.financial_terms.emd_amount_inr)
                if not confirm_emd_paid(page, tender_id):
                    mark_needs_human(tender_id, "EMD payment could not be confirmed")
                    return False

            upload_documents(page, tender_id, document_paths)
            accept_declaration(page, tender_id)

            # OTP verification before final submit.
            otp = request_otp(tender_id, tender.metadata.bid_id)
            page.fill("input[name='otp']", otp)
            page.click("button#verifyOtp")
            page.wait_for_load_state("networkidle")

            page.click("button#finalSubmit")
            page.wait_for_load_state("networkidle")

            mark_submitted(tender_id, detail={"quoted_price_inr": quoted_price_inr})
            log_decision(
                phase=Phase.BID_PARTICIPATION,
                step="Bid Submitted",
                decision="submitted",
                tender_id=tender_id,
                owner="automation",
                detail={"bid_id": tender.metadata.bid_id, "quoted_price_inr": quoted_price_inr},
            )
            return True

        except CaptchaDetectedError as e:
            mark_needs_human(tender_id, f"CAPTCHA detected: {e}")
            log_error(phase=Phase.BID_PARTICIPATION, step="Submit Bid", exc=e, tender_id=tender_id, bid_id=tender.metadata.bid_id)
            return False

        except OTPTimeoutError as e:
            mark_needs_human(tender_id, f"OTP timeout: {e}")
            log_error(phase=Phase.BID_PARTICIPATION, step="Submit Bid", exc=e, tender_id=tender_id, bid_id=tender.metadata.bid_id)
            return False

        except EMDPaymentError as e:
            mark_failed(tender_id, f"EMD payment failed: {e}")
            log_error(phase=Phase.BID_PARTICIPATION, step="Submit Bid", exc=e, tender_id=tender_id, bid_id=tender.metadata.bid_id)
            return False

        except Exception as e:  # noqa: BLE001
            mark_failed(tender_id, f"Unexpected error: {e}")
            log_error(phase=Phase.BID_PARTICIPATION, step="Submit Bid", exc=e, tender_id=tender_id, bid_id=tender.metadata.bid_id)
            return False

        finally:
            try:
                context.browser.close()
            except Exception:  # noqa: BLE001
                pass
