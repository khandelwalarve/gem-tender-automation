"""
approval_flow.py — Phase 8 entry point: given a HUMAN_APPROVAL decision,
build a readable summary and create the review request.
"""
from __future__ import annotations

from src.common.schemas import Decision, EligibilityResult, FeasibilityResult, RiskFlag, TenderData

from .review import create_review_request


def build_summary(tender: TenderData, decision: Decision, eligibility: EligibilityResult, risks: list[RiskFlag]) -> str:
    lines = [
        f"Bid ID: {tender.metadata.bid_id}",
        f"Title: {tender.metadata.title}",
        f"Estimated value: INR {tender.metadata.estimated_value_inr}",
        f"Deadline: {tender.metadata.bid_submission_deadline}",
        f"Eligibility score: {eligibility.score}",
        f"Decision reasons: {'; '.join(decision.reasons)}",
    ]
    if risks:
        lines.append("Risk flags:")
        lines.extend(f"  - [{r.severity.value}] {r.description}" for r in risks)
    return "\n".join(lines)


def route_for_approval(
    tender: TenderData,
    decision: Decision,
    eligibility: EligibilityResult,
    risks: list[RiskFlag],
    tender_id: int,
    reviewer_email: str,
    reviewer_phone: str | None = None,
) -> int:
    summary = build_summary(tender, decision, eligibility, risks)
    return create_review_request(tender_id, tender.metadata.bid_id, reviewer_email, reviewer_phone, summary)
