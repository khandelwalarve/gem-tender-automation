"""
linked_documents.py — Tender PDFs sometimes reference external documents by
URL (e.g. "see detailed BOQ at https://dept.gov.in/files/boq.pdf") rather
than attaching them directly. This module extracts those links from a PDF
(both clickable annotations and plain-text URLs), filters to ones that look
like actual documents, downloads them, and feeds them back into the same
file registry so they get processed and extracted like any other attachment.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import fitz  # PyMuPDF
import requests

from src.audit_logging import Phase, log_info, log_warning

DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar"}

# Plain-text URLs embedded in the document body (not clickable annotations).
URL_PATTERN = re.compile(r"https?://[^\s\)\]\"'<>]+")

MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # 50 MB safety cap
REQUEST_TIMEOUT_SECONDS = 30


@dataclass
class DiscoveredLink:
    url: str
    source_page: int
    looks_like_document: bool


@dataclass
class FetchedLinkedFile:
    url: str
    file_name: str
    storage_path: str
    file_hash: str
    size_bytes: int


def extract_links(pdf_path: str) -> list[DiscoveredLink]:
    """Pulls both clickable link annotations and plain-text URLs out of a PDF."""
    doc = fitz.open(pdf_path)
    found: list[DiscoveredLink] = []
    seen_urls: set[str] = set()

    for page_num, page in enumerate(doc):
        # Clickable annotations (proper hyperlinks).
        for link in page.get_links():
            url = link.get("uri")
            if url and url not in seen_urls:
                seen_urls.add(url)
                found.append(DiscoveredLink(url=url, source_page=page_num, looks_like_document=_looks_like_document(url)))

        # Plain-text URLs typed into the document body (not real hyperlinks).
        text = page.get_text()
        for match in URL_PATTERN.finditer(text):
            url = match.group().rstrip(".,;")
            if url not in seen_urls:
                seen_urls.add(url)
                found.append(DiscoveredLink(url=url, source_page=page_num, looks_like_document=_looks_like_document(url)))

    doc.close()
    return found


def _looks_like_document(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in DOCUMENT_EXTENSIONS)


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_linked_document(url: str, dest_dir: Path, tender_id: int | None = None) -> FetchedLinkedFile | None:
    """
    Downloads one linked document. Returns None (and logs a warning) on any
    failure — a broken external link should not abort the whole pipeline,
    since the tender's own attachments may still be sufficient.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, stream=True)
        resp.raise_for_status()

        content_length = int(resp.headers.get("content-length", 0))
        if content_length and content_length > MAX_DOWNLOAD_BYTES:
            log_warning(
                phase=Phase.DOCUMENT_PROCESSING,
                step="Fetch Linked Document",
                tender_id=tender_id,
                detail={"url": url, "reason": "exceeds size cap", "content_length": content_length},
            )
            return None

        file_name = Path(urlparse(url).path).name or "linked_document"
        target_path = dest_dir / file_name

        size = 0
        with open(target_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                size += len(chunk)
                if size > MAX_DOWNLOAD_BYTES:
                    f.close()
                    target_path.unlink(missing_ok=True)
                    log_warning(
                        phase=Phase.DOCUMENT_PROCESSING,
                        step="Fetch Linked Document",
                        tender_id=tender_id,
                        detail={"url": url, "reason": "exceeded size cap mid-download"},
                    )
                    return None
                f.write(chunk)

        result = FetchedLinkedFile(
            url=url,
            file_name=file_name,
            storage_path=str(target_path),
            file_hash=_hash_file(target_path),
            size_bytes=target_path.stat().st_size,
        )

        log_info(
            phase=Phase.DOCUMENT_PROCESSING,
            step="Linked Document Fetched",
            tender_id=tender_id,
            owner="automation",
            detail={"url": url, "file_name": file_name, "size_bytes": result.size_bytes},
        )
        return result

    except requests.RequestException as e:
        log_warning(
            phase=Phase.DOCUMENT_PROCESSING,
            step="Fetch Linked Document",
            tender_id=tender_id,
            detail={"url": url, "error": str(e)},
        )
        return None


def discover_and_fetch_linked_documents(pdf_path: str, dest_dir: Path, tender_id: int | None = None) -> list[FetchedLinkedFile]:
    """
    Full flow for one PDF: extract links, filter to document-looking ones,
    fetch each, and return the successfully downloaded files. Failures on
    individual links are logged and skipped rather than raised.
    """
    links = extract_links(pdf_path)
    document_links = [l for l in links if l.looks_like_document]

    if not document_links:
        return []

    log_info(
        phase=Phase.DOCUMENT_PROCESSING,
        step="Linked Documents Discovered",
        tender_id=tender_id,
        detail={"source_pdf": pdf_path, "link_count": len(document_links)},
    )

    fetched = []
    for link in document_links:
        result = fetch_linked_document(link.url, dest_dir, tender_id=tender_id)
        if result:
            fetched.append(result)

    return fetched
