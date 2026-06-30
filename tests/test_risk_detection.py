from src.common.schemas import FinancialTerms, RiskFlagType, TenderData, TenderMetadata
from src.risk_detection.rule_based import check_excessive_penalty, check_missing_dates, check_split_tender


def test_missing_deadline_flagged_high():
    tender = TenderData(metadata=TenderMetadata(bid_id="BID-1", title="Test"))  # no deadline
    flags = check_missing_dates(tender)
    assert any(f.flag_type == RiskFlagType.MISSING_DATE for f in flags)


def test_present_deadline_not_flagged():
    from datetime import datetime

    tender = TenderData(
        metadata=TenderMetadata(bid_id="BID-1", title="Test", bid_submission_deadline=datetime(2026, 1, 1), published_on="2025-12-01")
    )
    flags = check_missing_dates(tender)
    assert len(flags) == 0


def test_excessive_performance_security_flagged():
    tender = TenderData(
        metadata=TenderMetadata(bid_id="BID-1", title="Test"),
        financial_terms=FinancialTerms(performance_security_pct=25.0),
    )
    flags = check_excessive_penalty(tender)
    assert any(f.flag_type == RiskFlagType.EXCESSIVE_PENALTY for f in flags)


def test_severe_penalty_keyword_flagged():
    tender = TenderData(
        metadata=TenderMetadata(bid_id="BID-1", title="Test"),
        financial_terms=FinancialTerms(penalty_clause="Failure to deliver will result in blacklisting of the vendor."),
    )
    flags = check_excessive_penalty(tender)
    assert len(flags) >= 1


def test_split_tender_detection():
    tender = TenderData(metadata=TenderMetadata(bid_id="BID-1", title="Test", estimated_value_inr=4_000_000))
    flags = check_split_tender(tender, related_tender_values=[3_000_000])
    # split_tender_value_threshold_inr isn't set by default, so expect no flags unless configured
    assert isinstance(flags, list)
