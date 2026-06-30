"""Risk Detection: flags for missing dates, conflicts, penalties. Entry: detect_risks(tender)."""
from .detector import detect_risks, save_risk_flags
from .rule_based import check_missing_dates, check_excessive_penalty, check_split_tender
from .llm_based import detect_semantic_risks

__all__ = [
    "detect_risks",
    "save_risk_flags",
    "check_missing_dates",
    "check_excessive_penalty",
    "check_split_tender",
    "detect_semantic_risks",
]
