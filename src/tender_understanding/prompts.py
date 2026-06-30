"""
prompts.py — Prompt templates for tender field extraction.
Kept separate from extractor.py so prompt iteration doesn't require touching logic.
"""

SYSTEM_PROMPT = """You are an expert government tender analyst. You read GeM
(Government e-Marketplace) tender documents and extract structured data with
high precision. You never invent values that are not present in the text —
if a field is not stated, you set it to null. You always respond with valid
JSON only, no commentary, no markdown formatting."""


EXTRACTION_PROMPT_TEMPLATE = """Extract the following fields from this tender
document text and respond with ONLY a JSON object matching this exact schema:

{{
  "metadata": {{
    "bid_id": string or null,
    "title": string or null,
    "department": string or null,
    "issuing_authority": string or null,
    "published_on": "YYYY-MM-DD" or null,
    "bid_submission_deadline": "YYYY-MM-DD HH:MM" or null,
    "bid_opening_date": "YYYY-MM-DD HH:MM" or null,
    "estimated_value_inr": number or null,
    "category": string or null
  }},
  "scope_of_work": {{
    "summary": string or null,
    "deliverables": [string],
    "timeline_days": number or null,
    "location": string or null
  }},
  "eligibility_criteria": {{
    "min_turnover_inr": number or null,
    "min_years_experience": number or null,
    "required_certifications": [string],
    "required_categories": [string],
    "mse_exemption": boolean,
    "startup_exemption": boolean,
    "other_conditions": [string]
  }},
  "financial_terms": {{
    "emd_amount_inr": number or null,
    "emd_exemption_available": boolean,
    "performance_security_pct": number or null,
    "payment_terms": string or null,
    "penalty_clause": string or null
  }},
  "technical_specifications": [
    {{"item_name": string, "specification": string, "quantity": number or null, "unit": string or null}}
  ]
}}

Document text:
---
{chunk_text}
---

Respond with ONLY the JSON object, nothing else.
"""


MERGE_PROMPT_TEMPLATE = """You are merging multiple partial JSON extractions
of the same tender document (each extracted from a different chunk of the
same file). Combine them into a single JSON object following the same
schema. Prefer non-null values over null ones. For list fields, take the
union of all unique items. Respond with ONLY the merged JSON object.

Partial extractions:
---
{partial_jsons}
---
"""
