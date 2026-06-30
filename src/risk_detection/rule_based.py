"""
rule_based.py — Deterministic risk checks that don't require an LLM call:
missing critical dates, excessive penalty clauses, and suspiciously
fragmented (split) tenders.
"""
from __future__ import annotations

from src.common.config import get_settings
from src.common.schemas import RiskFlag, RiskFlagType, RiskSeverity, TenderData


def check_missing_dates(tender: TenderData) -> list[RiskFlag]:
    flags = []
    meta = tender.metadata

    if meta.bid_submission_deadline is None:
        flags.append(
            RiskFlag(
                flag_type=RiskFlagType.MISSING_DATE,
                severity=RiskSeverity.HIGH,
                description="Bid submission deadline could not be extracted from the tender document",
            )
        )
    if meta.published_on is None:
        flags.append(
            RiskFlag(
                flag_type=RiskFlagType.MISSING_DATE,
                severity=RiskSeverity.LOW,
                description="Tender publish date could not be extracted",
            )
        )
    return flags


def check_excessive_penalty(tender: TenderData) -> list[RiskFlag]:
    flags = []
    settings = get_settings()
    max_pct = settings.get("risk_detection", {}).get("max_performance_security_pct", 10.0)

    pct = tender.financial_terms.performance_security_pct
    if pct is not None and pct > max_pct:
        flags.append(
            RiskFlag(
                flag_type=RiskFlagType.EXCESSIVE_PENALTY,
                severity=RiskSeverity.HIGH,
                description=f"Performance security of {pct}% exceeds the configured threshold of {max_pct}%",
                detail={"performance_security_pct": pct, "threshold_pct": max_pct},
            )
        )

    penalty_text = (tender.financial_terms.penalty_clause or "").lower()
    severe_keywords = ["blacklist", "debar", "forfeit entire", "unlimited liability"]
    for kw in severe_keywords:
        if kw in penalty_text:
            flags.append(
                RiskFlag(
                    flag_type=RiskFlagType.EXCESSIVE_PENALTY,
                    severity=RiskSeverity.MEDIUM,
                    description=f"Penalty clause contains severe term: '{kw}'",
                    detail={"matched_keyword": kw},
                )
            )

    return flags


def check_split_tender(tender: TenderData, related_tender_values: list[float]) -> list[RiskFlag]:
    """
    Flags possible tender-splitting: this tender plus recently seen tenders
    from the same department summing suspiciously close to (but under) a
    procurement threshold that would otherwise require a different process.
    """
    flags = []
    settings = get_settings()
    split_threshold = settings.get("risk_detection", {}).get("split_tender_value_threshold_inr")

    if split_threshold is None or tender.metadata.estimated_value_inr is None:
        return flags

    total = tender.metadata.estimated_value_inr + sum(related_tender_values)
    if tender.metadata.estimated_value_inr < split_threshold and total >= split_threshold:
        flags.append(
            RiskFlag(
                flag_type=RiskFlagType.SPLIT_TENDER,
                severity=RiskSeverity.MEDIUM,
                description=(
                    "This tender's value is below the procurement threshold, but combined with "
                    "related recent tenders from the same authority it exceeds it — possible split tender"
                ),
                detail={"combined_value": total, "threshold": split_threshold},
            )
        )

    return flags
