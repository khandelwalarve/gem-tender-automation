"""
matcher.py — Compares tender eligibility_criteria against the company
profile and produces a weighted score plus a per-criterion breakdown.
"""
from __future__ import annotations

from typing import Any

from src.common.schemas import EligibilityCheck, EligibilityResult, TenderData

# Weight each criterion contributes to the overall score.
WEIGHTS = {
    "turnover": 0.25,
    "experience": 0.20,
    "certifications": 0.25,
    "categories": 0.20,
    "other_conditions": 0.10,
}


def check_turnover(criteria_min: float | None, profile: dict[str, Any]) -> EligibilityCheck:
    company_turnover = profile.get("annual_turnover_inr")
    if criteria_min is None:
        return EligibilityCheck(criterion="turnover", required="none", company_value=str(company_turnover), met=True)

    met = company_turnover is not None and company_turnover >= criteria_min
    return EligibilityCheck(
        criterion="turnover",
        required=f">= {criteria_min}",
        company_value=str(company_turnover),
        met=met,
    )


def check_experience(criteria_min_years: int | None, profile: dict[str, Any]) -> EligibilityCheck:
    company_years = profile.get("years_in_operation")
    if criteria_min_years is None:
        return EligibilityCheck(criterion="experience", required="none", company_value=str(company_years), met=True)

    met = company_years is not None and company_years >= criteria_min_years
    return EligibilityCheck(
        criterion="experience",
        required=f">= {criteria_min_years} years",
        company_value=str(company_years),
        met=met,
    )


def check_certifications(required: list[str], profile: dict[str, Any]) -> EligibilityCheck:
    company_certs = set(c.lower() for c in profile.get("certifications", []))
    required_lower = set(c.lower() for c in required)

    if not required_lower:
        return EligibilityCheck(criterion="certifications", required="none", company_value=", ".join(company_certs), met=True)

    missing = required_lower - company_certs
    met = len(missing) == 0
    note = f"Missing: {', '.join(missing)}" if missing else None
    return EligibilityCheck(
        criterion="certifications",
        required=", ".join(required),
        company_value=", ".join(profile.get("certifications", [])),
        met=met,
        note=note,
    )


def check_categories(required: list[str], profile: dict[str, Any]) -> EligibilityCheck:
    company_categories = set(c.lower() for c in profile.get("service_categories", []))
    required_lower = set(c.lower() for c in required)

    if not required_lower:
        return EligibilityCheck(criterion="categories", required="none", company_value=", ".join(company_categories), met=True)

    overlap = required_lower & company_categories
    met = len(overlap) > 0
    return EligibilityCheck(
        criterion="categories",
        required=", ".join(required),
        company_value=", ".join(profile.get("service_categories", [])),
        met=met,
    )


def check_other_conditions(conditions: list[str]) -> EligibilityCheck:
    """
    Free-text conditions can't be deterministically verified — flagged as
    low-confidence for human review rather than auto-passed or auto-failed.
    """
    if not conditions:
        return EligibilityCheck(criterion="other_conditions", required="none", met=True, confidence=1.0)

    return EligibilityCheck(
        criterion="other_conditions",
        required="; ".join(conditions),
        met=True,  # assumed met pending human verification
        confidence=0.4,
        note="Free-text conditions require manual verification",
    )


def evaluate_eligibility(tender: TenderData, profile: dict[str, Any]) -> EligibilityResult:
    crit = tender.eligibility_criteria

    checks = [
        check_turnover(crit.min_turnover_inr, profile),
        check_experience(crit.min_years_experience, profile),
        check_certifications(crit.required_certifications, profile),
        check_categories(crit.required_categories, profile),
        check_other_conditions(crit.other_conditions),
    ]

    weight_keys = ["turnover", "experience", "certifications", "categories", "other_conditions"]
    score = sum(WEIGHTS[k] * (1.0 if c.met else 0.0) for k, c in zip(weight_keys, checks))

    # MSE/startup exemptions can waive the turnover and experience requirements.
    is_exempt = crit.mse_exemption or crit.startup_exemption
    hard_fail = (not checks[2].met) or (not checks[3].met)  # certs and categories are non-waivable
    if is_exempt and not hard_fail:
        is_eligible = True
        score = max(score, 0.8)
    else:
        is_eligible = all(c.met for c in checks)

    low_confidence_flags = [c.criterion for c in checks if c.confidence < 0.7]

    return EligibilityResult(
        tender_bid_id=tender.metadata.bid_id,
        score=round(score, 2),
        is_eligible=is_eligible,
        checks=checks,
        low_confidence_flags=low_confidence_flags,
    )
