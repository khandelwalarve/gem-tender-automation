"""
gate.py — Compares tender field values against parsed feasibility thresholds
and produces a go/no-go style result with a full check breakdown.
"""
from __future__ import annotations

from src.common.schemas import FeasibilityCheck, FeasibilityResult, TenderData

from .thresholds import FeasibilityThresholds


def check_project_value(tender: TenderData, thresholds: FeasibilityThresholds) -> FeasibilityCheck:
    value = tender.metadata.estimated_value_inr
    if thresholds.max_project_value_inr is None:
        return FeasibilityCheck(parameter="project_value", threshold="none configured", tender_value=str(value), within_threshold=True)

    within = value is not None and value <= thresholds.max_project_value_inr
    return FeasibilityCheck(
        parameter="project_value",
        threshold=f"<= {thresholds.max_project_value_inr}",
        tender_value=str(value),
        within_threshold=within,
    )


def check_timeline(tender: TenderData, thresholds: FeasibilityThresholds) -> FeasibilityCheck:
    timeline = tender.scope_of_work.timeline_days
    if thresholds.min_timeline_days is None:
        return FeasibilityCheck(parameter="timeline", threshold="none configured", tender_value=str(timeline), within_threshold=True)

    within = timeline is not None and timeline >= thresholds.min_timeline_days
    return FeasibilityCheck(
        parameter="timeline",
        threshold=f">= {thresholds.min_timeline_days} days",
        tender_value=str(timeline),
        within_threshold=within,
        note="Timeline too short for available capacity" if not within else None,
    )


def check_category_exclusion(tender: TenderData, thresholds: FeasibilityThresholds) -> FeasibilityCheck:
    category = (tender.metadata.category or "").lower()
    excluded = [c.lower() for c in thresholds.excluded_categories]

    is_excluded = category in excluded
    return FeasibilityCheck(
        parameter="category_exclusion",
        threshold=f"not in {excluded}" if excluded else "none configured",
        tender_value=category,
        within_threshold=not is_excluded,
    )


def analyse_feasibility(tender: TenderData, thresholds: FeasibilityThresholds) -> FeasibilityResult:
    checks = [
        check_project_value(tender, thresholds),
        check_timeline(tender, thresholds),
        check_category_exclusion(tender, thresholds),
    ]

    is_feasible = all(c.within_threshold for c in checks)

    return FeasibilityResult(
        tender_bid_id=tender.metadata.bid_id,
        is_feasible=is_feasible,
        checks=checks,
    )
