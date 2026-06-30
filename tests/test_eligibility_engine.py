from src.common.schemas import EligibilityCriteria, TenderData, TenderMetadata
from src.eligibility_engine.matcher import evaluate_eligibility

PROFILE = {
    "annual_turnover_inr": 10_000_000,
    "years_in_operation": 5,
    "certifications": ["ISO 9001", "ISO 27001"],
    "service_categories": ["IT Services", "Software Development"],
    "is_mse": False,
    "is_startup": False,
}


def make_tender(**criteria_kwargs):
    return TenderData(
        metadata=TenderMetadata(bid_id="BID-1", title="Test"),
        eligibility_criteria=EligibilityCriteria(**criteria_kwargs),
    )


def test_fully_eligible_tender_passes():
    tender = make_tender(
        min_turnover_inr=5_000_000,
        min_years_experience=3,
        required_certifications=["ISO 9001"],
        required_categories=["IT Services"],
    )
    result = evaluate_eligibility(tender, PROFILE)
    assert result.is_eligible is True
    assert result.score > 0.9


def test_missing_certification_fails():
    tender = make_tender(required_certifications=["ISO 14001"])  # not in profile
    result = evaluate_eligibility(tender, PROFILE)
    assert result.is_eligible is False


def test_insufficient_turnover_fails():
    tender = make_tender(min_turnover_inr=50_000_000)
    result = evaluate_eligibility(tender, PROFILE)
    assert result.is_eligible is False


def test_mse_exemption_waives_turnover_and_experience():
    tender = make_tender(min_turnover_inr=50_000_000, min_years_experience=20, mse_exemption=True)
    exempt_profile = {**PROFILE, "is_mse": True}
    result = evaluate_eligibility(tender, exempt_profile)
    assert result.is_eligible is True


def test_no_criteria_is_trivially_eligible():
    tender = make_tender()
    result = evaluate_eligibility(tender, PROFILE)
    assert result.is_eligible is True
    assert result.score == 1.0
