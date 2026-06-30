"""
thresholds.py — Parses operating thresholds (max project value, min timeline,
max travel distance, etc.) from a client-provided feasibility PDF, rather than
hardcoding limits in code. Falls back to config defaults if a field can't be
parsed from the PDF.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import fitz  # PyMuPDF

from src.common.config import get_settings


@dataclass
class FeasibilityThresholds:
    max_project_value_inr: float | None = None
    min_timeline_days: int | None = None
    max_travel_distance_km: float | None = None
    excluded_categories: list[str] = field(default_factory=list)
    min_team_size_available: int | None = None


_PATTERNS = {
    "max_project_value_inr": r"(?:max(?:imum)?\s+project\s+value)\D{0,20}([\d,]+)",
    "min_timeline_days": r"(?:min(?:imum)?\s+timeline)\D{0,20}(\d+)\s*days?",
    "max_travel_distance_km": r"(?:max(?:imum)?\s+travel\s+distance)\D{0,20}([\d,.]+)\s*km",
    "min_team_size_available": r"(?:min(?:imum)?\s+team\s+size)\D{0,20}(\d+)",
}


def _parse_number(raw: str) -> float:
    return float(raw.replace(",", ""))


def parse_feasibility_pdf(pdf_path: str) -> FeasibilityThresholds:
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()

    thresholds = FeasibilityThresholds()
    text_lower = text.lower()

    for field_name, pattern in _PATTERNS.items():
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            value = _parse_number(match.group(1))
            if field_name == "min_timeline_days" or field_name == "min_team_size_available":
                setattr(thresholds, field_name, int(value))
            else:
                setattr(thresholds, field_name, value)

    excl_match = re.search(r"excluded\s+categories?:?\s*([^\n]+)", text_lower)
    if excl_match:
        thresholds.excluded_categories = [c.strip() for c in excl_match.group(1).split(",")]

    return thresholds


def get_thresholds(feasibility_pdf_path: str | None = None) -> FeasibilityThresholds:
    """
    Returns thresholds parsed from the given PDF, falling back to any defaults
    configured in settings.yaml for fields the PDF parse couldn't find.
    """
    settings = get_settings()
    config_defaults = settings.get("feasibility_analysis", {}).get("default_thresholds", {})

    thresholds = FeasibilityThresholds(**config_defaults) if config_defaults else FeasibilityThresholds()

    if feasibility_pdf_path:
        parsed = parse_feasibility_pdf(feasibility_pdf_path)
        for f in parsed.__dataclass_fields__:
            value = getattr(parsed, f)
            if value:
                setattr(thresholds, f, value)

    return thresholds
