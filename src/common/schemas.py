"""
Shared data contracts used across every phase of the pipeline.

TenderData is the canonical structured representation of a tender, produced
by Phase 3 (Tender Understanding) and consumed by every phase after it.
Keeping it in one place avoids circular imports between modules.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Phase 3 — Tender Understanding output
# ---------------------------------------------------------------------------

class TenderMetadata(BaseModel):
    bid_id: str
    title: str
    department: str | None = None
    issuing_authority: str | None = None
    published_on: date | None = None
    bid_submission_deadline: datetime | None = None
    bid_opening_date: datetime | None = None
    estimated_value_inr: float | None = None
    category: str | None = None


class EligibilityCriteria(BaseModel):
    min_turnover_inr: float | None = None
    min_years_experience: int | None = None
    required_certifications: list[str] = Field(default_factory=list)
    required_categories: list[str] = Field(default_factory=list)
    mse_exemption: bool = False
    startup_exemption: bool = False
    other_conditions: list[str] = Field(default_factory=list)


class FinancialTerms(BaseModel):
    emd_amount_inr: float | None = None
    emd_exemption_available: bool = False
    performance_security_pct: float | None = None
    payment_terms: str | None = None
    penalty_clause: str | None = None


class ScopeOfWork(BaseModel):
    summary: str | None = None
    deliverables: list[str] = Field(default_factory=list)
    timeline_days: int | None = None
    location: str | None = None


class TechnicalSpecification(BaseModel):
    item_name: str
    specification: str
    quantity: float | None = None
    unit: str | None = None


class TenderData(BaseModel):
    """Canonical structured tender record. Validated against this schema after LLM extraction."""

    metadata: TenderMetadata
    scope_of_work: ScopeOfWork = Field(default_factory=ScopeOfWork)
    eligibility_criteria: EligibilityCriteria = Field(default_factory=EligibilityCriteria)
    financial_terms: FinancialTerms = Field(default_factory=FinancialTerms)
    technical_specifications: list[TechnicalSpecification] = Field(default_factory=list)
    raw_extraction_confidence: float | None = None
    extraction_warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 4 — Eligibility Engine output
# ---------------------------------------------------------------------------

class EligibilityCheck(BaseModel):
    criterion: str
    required: str
    company_value: str | None = None
    met: bool
    confidence: float = 1.0
    note: str | None = None


class EligibilityResult(BaseModel):
    tender_bid_id: str
    score: float                 # 0.0 - 1.0
    is_eligible: bool
    checks: list[EligibilityCheck] = Field(default_factory=list)
    low_confidence_flags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 5 — Feasibility Analysis output
# ---------------------------------------------------------------------------

class FeasibilityCheck(BaseModel):
    parameter: str
    threshold: str
    tender_value: str | None = None
    within_threshold: bool
    note: str | None = None


class FeasibilityResult(BaseModel):
    tender_bid_id: str
    is_feasible: bool
    checks: list[FeasibilityCheck] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 6 — Risk Detection output
# ---------------------------------------------------------------------------

class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskFlagType(str, Enum):
    MISSING_DATE = "missing_date"
    CONFLICTING_CLAUSE = "conflicting_clause"
    SPLIT_TENDER = "split_tender"
    AMBIGUOUS_REQUIREMENT = "ambiguous"
    EXCESSIVE_PENALTY = "excessive_penalty"


class RiskFlag(BaseModel):
    flag_type: RiskFlagType
    severity: RiskSeverity
    description: str
    detail: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase 7 — Decision Engine output
# ---------------------------------------------------------------------------

class DecisionOutcome(str, Enum):
    AUTO_SUBMIT = "auto_submit"
    HUMAN_APPROVAL = "human_approval"
    REJECTED = "rejected"


class Decision(BaseModel):
    tender_bid_id: str
    outcome: DecisionOutcome
    score: float
    reasons: list[str] = Field(default_factory=list)
