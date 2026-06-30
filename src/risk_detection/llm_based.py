"""
llm_based.py — Uses the LLM to find risks that need semantic understanding:
contradicting clauses and ambiguous requirements that simple rules can't catch.
"""
from __future__ import annotations

from src.common.schemas import RiskFlag, RiskFlagType, RiskSeverity, TenderData
from src.tender_understanding.llm_client import LLMError, call_llm_json

SYSTEM_PROMPT = """You are a contract risk analyst reviewing a government
tender. You identify only genuine, material risks — not stylistic
nitpicks. Respond with ONLY a JSON array, no commentary."""

PROMPT_TEMPLATE = """Review this tender's scope of work and conditions for:
1. Contradicting clauses (e.g. conflicting deadlines, conflicting deliverable counts)
2. Ambiguous requirements (e.g. vague specs that could be interpreted multiple ways)

Tender data (JSON):
---
{tender_json}
---

Respond with ONLY a JSON array of objects, each with this shape:
{{"flag_type": "conflicting_clause" | "ambiguous", "severity": "low"|"medium"|"high", "description": string}}

If no risks are found, respond with an empty array: []
"""


def detect_semantic_risks(tender: TenderData) -> list[RiskFlag]:
    prompt = PROMPT_TEMPLATE.format(tender_json=tender.model_dump_json(indent=2))

    try:
        result = call_llm_json(prompt, system=SYSTEM_PROMPT)
    except LLMError:
        # If the LLM call fails, return no flags rather than blocking the pipeline —
        # rule-based checks still run independently.
        return []

    # call_llm_json expects a dict; handle the array case explicitly.
    items = result if isinstance(result, list) else result.get("risks", [])

    flags = []
    for item in items:
        try:
            flags.append(
                RiskFlag(
                    flag_type=RiskFlagType(item["flag_type"]),
                    severity=RiskSeverity(item["severity"]),
                    description=item["description"],
                )
            )
        except (KeyError, ValueError):
            continue  # skip malformed entries rather than failing the whole batch

    return flags
