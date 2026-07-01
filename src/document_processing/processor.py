"""
processor.py — Orchestrates the full Phase 2 pipeline for one document:
OCR (if needed) -> text extraction -> table extraction -> clean -> detect
language -> translate -> chunk -> discover & fetch linked documents.
Logs progress and warnings to the audit log.
"""
from __future__ import annotations

from pathlib import Path

from src.audit_logging import Phase, log_error, log_info, log_warning

from .linked_documents import FetchedLinkedFile, discover_and_fetch_linked_documents
from .ocr import process_pdf_ocr
from .tables import extract_tables, ExtractedTable
from .text_pipeline import (
    ProcessedDocument,
    chunk_text,
    clean_text,
    detect_language,
    extract_raw_text,
    translate_to_english,
)


def process_document(pdf_path: str, tender_id: int | None = None) -> ProcessedDocument | None:
    """Full document processing pipeline for a single file. Returns None and logs an error if processing fails."""
    try:
        final_pdf_path, page_quality = process_pdf_ocr(pdf_path)

        low_quality_pages = [p for p in page_quality if p.needs_human_qc]
        if low_quality_pages:
            log_warning(
                phase=Phase.DOCUMENT_PROCESSING,
                step="OCR Quality Check",
                tender_id=tender_id,
                detail={
                    "file": pdf_path,
                    "low_confidence_pages": [p.page_number for p in low_quality_pages],
                },
            )

        raw_text = extract_raw_text(final_pdf_path)
        tables: list[ExtractedTable] = extract_tables(final_pdf_path)

        # Append a simple textual rendering of tables so the LLM sees them too.
        table_text = "\n\n".join(
            f"[Table on page {t.page} ({t.source})]\n"
            + "\n".join(" | ".join(str(cell) for cell in row) for row in t.rows)
            for t in tables
        )
        combined_text = raw_text + ("\n\n" + table_text if table_text else "")

        cleaned = clean_text(combined_text)
        language = detect_language(cleaned)
        translated = translate_to_english(cleaned, language)
        chunks = chunk_text(translated)

        log_info(
            phase=Phase.DOCUMENT_PROCESSING,
            step="Document Processed",
            tender_id=tender_id,
            owner="automation",
            detail={
                "file": pdf_path,
                "language": language,
                "table_count": len(tables),
                "chunk_count": len(chunks),
            },
        )

        return ProcessedDocument(
            source_path=pdf_path,
            full_text=translated,
            language=language,
            chunks=chunks,
            page_warnings=[f"Page {p.page_number}: low OCR confidence" for p in low_quality_pages],
        )

    except Exception as e:  # noqa: BLE001
        log_error(phase=Phase.DOCUMENT_PROCESSING, step="Process Document", exc=e, tender_id=tender_id, extra={"file": pdf_path})
        return None


def process_document_with_linked_files(
    pdf_path: str,
    tender_id: int | None = None,
    linked_files_dir: str | None = None,
    max_link_depth: int = 1,
) -> tuple[ProcessedDocument | None, list[FetchedLinkedFile]]:
    """
    Like process_document, but also discovers URLs referenced inside the PDF
    (e.g. "see detailed BOQ at https://dept.gov.in/boq.pdf"), downloads any
    that look like documents, and processes those too — recursively up to
    max_link_depth (default 1, i.e. links-within-linked-documents are fetched
    but not followed further, to avoid runaway crawling).

    Returns (processed_main_document, list_of_fetched_linked_files).
    The chunks from linked documents are NOT merged into the main document's
    chunks automatically — callers (e.g. the pipeline) should process each
    fetched linked file through process_document() separately and combine
    chunks as needed, since they may warrant separate audit trail entries.
    """
    main_doc = process_document(pdf_path, tender_id=tender_id)

    dest_dir = Path(linked_files_dir) if linked_files_dir else Path(pdf_path).parent / "linked"
    fetched = discover_and_fetch_linked_documents(pdf_path, dest_dir, tender_id=tender_id)

    if max_link_depth > 1 and fetched:
        # One additional hop: check freshly fetched documents for further links.
        for f in list(fetched):
            if Path(f.file_name).suffix.lower() == ".pdf":
                nested = discover_and_fetch_linked_documents(f.storage_path, dest_dir, tender_id=tender_id)
                fetched.extend(nested)

    return main_doc, fetched
