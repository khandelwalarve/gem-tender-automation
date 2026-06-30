"""
extractor.py — Runs LLM extraction over each document chunk, merges partial
results, validates against the TenderData Pydantic schema, and routes
validation failures to human review instead of silently failing.
"""
from __future__ import annotations

import json

from pydantic import ValidationError

from src.audit_logging import Phase, log_error, log_info, log_warning
from src.common.schemas import TenderData

from .llm_client import LLMError, call_llm_json
from .prompts import EXTRACTION_PROMPT_TEMPLATE, MERGE_PROMPT_TEMPLATE, SYSTEM_PROMPT


class ExtractionValidationError(Exception):
    """Raised when LLM output cannot be validated against TenderData even after merge."""


def extract_from_chunk(chunk_text: str) -> dict:
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(chunk_text=chunk_text)
    return call_llm_json(prompt, system=SYSTEM_PROMPT)


def merge_partial_extractions(partials: list[dict]) -> dict:
    """
    Merges N partial JSON extractions into one. For small numbers of chunks
    we do this with a second LLM call (more robust to messy partial data);
    callers with a single chunk can skip merging entirely.
    """
    if len(partials) == 1:
        return partials[0]

    prompt = MERGE_PROMPT_TEMPLATE.format(partial_jsons=json.dumps(partials, indent=2))
    return call_llm_json(prompt, system=SYSTEM_PROMPT)


def understand_tender(chunks: list[str], tender_id: int | None = None, bid_id: str | None = None) -> TenderData | None:
    """
    Full Phase 3 pipeline:
    1. Extract structured fields from every chunk
    2. Merge partial extractions
    3. Validate against TenderData schema
    4. On validation failure, log and route to human review (return None)
    """
    partials: list[dict] = []

    for i, chunk in enumerate(chunks):
        try:
            partial = extract_from_chunk(chunk)
            partials.append(partial)
        except LLMError as e:
            log_warning(
                phase=Phase.TENDER_UNDERSTANDING,
                step="Extract Chunk",
                tender_id=tender_id,
                detail={"chunk_index": i, "error": str(e)},
            )

    if not partials:
        log_error(
            phase=Phase.TENDER_UNDERSTANDING,
            step="Extract Chunks",
            exc=ExtractionValidationError("All chunk extractions failed"),
            tender_id=tender_id,
            bid_id=bid_id,
        )
        return None

    try:
        merged = merge_partial_extractions(partials)
    except LLMError as e:
        log_error(phase=Phase.TENDER_UNDERSTANDING, step="Merge Extractions", exc=e, tender_id=tender_id, bid_id=bid_id)
        # Fall back to the first partial rather than losing everything.
        merged = partials[0]

    try:
        tender_data = TenderData.model_validate(merged)
    except ValidationError as e:
        log_error(
            phase=Phase.TENDER_UNDERSTANDING,
            step="Validate Schema",
            exc=e,
            tender_id=tender_id,
            bid_id=bid_id,
            extra={"raw_merged": merged},
        )
        return None

    log_info(
        phase=Phase.TENDER_UNDERSTANDING,
        step="Tender Understood",
        tender_id=tender_id,
        owner="ai_engine",
        detail={"bid_id": tender_data.metadata.bid_id, "chunks_processed": len(chunks)},
    )

    return tender_data
