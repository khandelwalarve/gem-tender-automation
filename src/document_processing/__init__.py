"""Document Processing: OCR, table extraction, chunking, linked document discovery."""
from .processor import process_document, process_document_with_linked_files
from .ocr import process_pdf_ocr, detect_pdf_type, PageQuality
from .tables import extract_tables, ExtractedTable
from .text_pipeline import ProcessedDocument, clean_text, detect_language, translate_to_english, chunk_text
from .linked_documents import discover_and_fetch_linked_documents, extract_links, fetch_linked_document, DiscoveredLink, FetchedLinkedFile

__all__ = [
    "process_document",
    "process_document_with_linked_files",
    "process_pdf_ocr",
    "detect_pdf_type",
    "PageQuality",
    "extract_tables",
    "ExtractedTable",
    "ProcessedDocument",
    "clean_text",
    "detect_language",
    "translate_to_english",
    "chunk_text",
    "discover_and_fetch_linked_documents",
    "extract_links",
    "fetch_linked_document",
    "DiscoveredLink",
    "FetchedLinkedFile",
]
