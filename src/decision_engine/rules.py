"""
rules.py — Combines eligibility score, feasibility result, and risk flags
into a single outcome: AUTO_SUBMIT, HUMAN_APPROVAL, or REJECTED.

Thresholds (score cutoffs, value limits, max allowed risk flags) come from
config/settings.yaml under decision_engine — never hardcoded here.
"""
from __future__ import annotations

from src.common.config import get_settings
from src.common.schemas import (
    Decision,
    DecisionOutcome,
    EligibilityResult,
    FeasibilityResult,
    RiskFlag,
    RiskSeverity,
    TenderData,
)


def make_decision(
    tender: TenderData,
    eligibility: EligibilityResult,
    feasibility: FeasibilityResult,
    risks: list[RiskFlag],
) -> Decision:
    settings = get_settings()
    cfg = settings.get("decision_engine", {})

    auto_submit_min_score = cfg.get("auto_submit_min_score", 0.85)
    review_min_score = cfg.get("review_min_score", 0.60)
    max_auto_submit_value = cfg.get("max_auto_submit_value_inr", 5_000_000)
    max_risk_flags = cfg.get("max_risk_flags", 0)

    reasons: list[str] = []

    # Hard rejects first.
    if not eligibility.is_eligible:
        reasons.append(f"Not eligible (score {eligibility.score})")
        return Decision(tender_bid_id=tender.metadata.bid_id, outcome=DecisionOutcome.REJECTED, score=eligibility.score, reasons=reasons)

    if not feasibility.is_feasible:
        reasons.append("Failed feasibility checks")
        return Decision(tender_bid_id=tender.metadata.bid_id, outcome=DecisionOutcome.REJECTED, score=eligibility.score, reasons=reasons)

    high_risk_count = sum(1 for r in risks if r.severity == RiskSeverity.HIGH)
    if high_risk_count > 0:
        reasons.append(f"{high_risk_count} high-severity risk flag(s) present")

    if eligibility.low_confidence_flags:
        reasons.append(f"Low-confidence eligibility checks: {', '.join(eligibility.low_confidence_flags)}")

    value = tender.metadata.estimated_value_inr or 0
    if value > max_auto_submit_value:
        reasons.append(f"Tender value {value} exceeds auto-submit limit {max_auto_submit_value}")

    risk_count = len(risks)
    if risk_count > max_risk_flags:
        reasons.append(f"{risk_count} risk flag(s) exceeds max allowed {max_risk_flags} for auto-submit")

    # Decide based on score plus the human-review triggers above.
    needs_review = bool(reasons) or eligibility.score < auto_submit_min_score

    if eligibility.score < review_min_score:
        reasons.append(f"Eligibility score {eligibility.score} below review threshold {review_min_score}")
        return Decision(tender_bid_id=tender.metadata.bid_id, outcome=DecisionOutcome.REJECTED, score=eligibility.score, reasons=reasons)

    if needs_review:
        if not reasons:
            reasons.append(f"Eligibility score {eligibility.score} below auto-submit threshold {auto_submit_min_score}")
        return Decision(tender_bid_id=tender.metadata.bid_id, outcome=DecisionOutcome.HUMAN_APPROVAL, score=eligibility.score, reasons=reasons)

    reasons.append("All checks passed within auto-submit thresholds")
    return Decision(tender_bid_id=tender.metadata.bid_id, outcome=DecisionOutcome.AUTO_SUBMIT, score=eligibility.score, reasons=reasons)
