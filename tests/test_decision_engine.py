import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest

from src.common.schemas import (
    DecisionOutcome,
    EligibilityResult,
    FeasibilityResult,
    RiskFlag,
    RiskFlagType,
    RiskSeverity,
    TenderData,
    TenderMetadata,
)
from src.decision_engine.rules import make_decision


def make_tender(value=1_000_000):
    return TenderData(metadata=TenderMetadata(bid_id="BID-1", title="Test Tender", estimated_value_inr=value))


def test_not_eligible_is_rejected():
    tender = make_tender()
    eligibility = EligibilityResult(tender_bid_id="BID-1", score=0.3, is_eligible=False)
    feasibility = FeasibilityResult(tender_bid_id="BID-1", is_feasible=True)

    decision = make_decision(tender, eligibility, feasibility, [])
    assert decision.outcome == DecisionOutcome.REJECTED


def test_not_feasible_is_rejected():
    tender = make_tender()
    eligibility = EligibilityResult(tender_bid_id="BID-1", score=0.9, is_eligible=True)
    feasibility = FeasibilityResult(tender_bid_id="BID-1", is_feasible=False)

    decision = make_decision(tender, eligibility, feasibility, [])
    assert decision.outcome == DecisionOutcome.REJECTED


def test_high_score_clean_risk_auto_submits():
    tender = make_tender(value=1_000_000)
    eligibility = EligibilityResult(tender_bid_id="BID-1", score=0.95, is_eligible=True)
    feasibility = FeasibilityResult(tender_bid_id="BID-1", is_feasible=True)

    decision = make_decision(tender, eligibility, feasibility, [])
    assert decision.outcome == DecisionOutcome.AUTO_SUBMIT


def test_high_risk_flag_forces_human_approval():
    tender = make_tender(value=1_000_000)
    eligibility = EligibilityResult(tender_bid_id="BID-1", score=0.95, is_eligible=True)
    feasibility = FeasibilityResult(tender_bid_id="BID-1", is_feasible=True)
    risks = [RiskFlag(flag_type=RiskFlagType.EXCESSIVE_PENALTY, severity=RiskSeverity.HIGH, description="test")]

    decision = make_decision(tender, eligibility, feasibility, risks)
    assert decision.outcome == DecisionOutcome.HUMAN_APPROVAL


def test_value_over_auto_submit_limit_forces_review():
    tender = make_tender(value=50_000_000)  # default limit is 5,000,000
    eligibility = EligibilityResult(tender_bid_id="BID-1", score=0.95, is_eligible=True)
    feasibility = FeasibilityResult(tender_bid_id="BID-1", is_feasible=True)

    decision = make_decision(tender, eligibility, feasibility, [])
    assert decision.outcome == DecisionOutcome.HUMAN_APPROVAL


def test_low_score_below_review_threshold_is_rejected():
    tender = make_tender()
    eligibility = EligibilityResult(tender_bid_id="BID-1", score=0.4, is_eligible=True)  # below review_min_score (0.60)
    feasibility = FeasibilityResult(tender_bid_id="BID-1", is_feasible=True)

    decision = make_decision(tender, eligibility, feasibility, [])
    assert decision.outcome == DecisionOutcome.REJECTED


def test_mid_score_routes_to_human_approval():
    tender = make_tender()
    eligibility = EligibilityResult(tender_bid_id="BID-1", score=0.7, is_eligible=True)  # between thresholds
    feasibility = FeasibilityResult(tender_bid_id="BID-1", is_feasible=True)

    decision = make_decision(tender, eligibility, feasibility, [])
    assert decision.outcome == DecisionOutcome.HUMAN_APPROVAL
