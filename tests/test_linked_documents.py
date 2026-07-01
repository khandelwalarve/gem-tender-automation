"""
Tests for linked_documents.py — runs without a real network by mocking
requests.get and without a real PDF by creating minimal in-memory PDFs.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import fitz  # PyMuPDF
import pytest

from src.document_processing.linked_documents import (
    DiscoveredLink,
    FetchedLinkedFile,
    _looks_like_document,
    extract_links,
    fetch_linked_document,
    discover_and_fetch_linked_documents,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_pdf_with_text(text: str, dest_path: str) -> None:
    """Creates a minimal single-page PDF with given text content."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), text, fontsize=11)
    doc.save(dest_path)
    doc.close()


def make_pdf_with_link(url: str, dest_path: str) -> None:
    """Creates a PDF with a clickable link annotation."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), f"Click here: {url}", fontsize=11)
    page.insert_link({"kind": fitz.LINK_URI, "uri": url, "from": fitz.Rect(50, 90, 200, 110)})
    doc.save(dest_path)
    doc.close()


# ---------------------------------------------------------------------------
# _looks_like_document
# ---------------------------------------------------------------------------

def test_pdf_url_looks_like_document():
    assert _looks_like_document("https://example.gov.in/files/boq.pdf") is True


def test_docx_url_looks_like_document():
    assert _looks_like_document("https://example.gov.in/files/tender.docx") is True


def test_html_url_does_not_look_like_document():
    assert _looks_like_document("https://example.gov.in/tender-details") is False


def test_jpg_url_does_not_look_like_document():
    assert _looks_like_document("https://example.gov.in/logo.jpg") is False


# ---------------------------------------------------------------------------
# extract_links
# ---------------------------------------------------------------------------

def test_extract_clickable_link_from_pdf():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = str(Path(tmpdir) / "test.pdf")
        make_pdf_with_link("https://dept.gov.in/boq.pdf", pdf_path)

        links = extract_links(pdf_path)
        urls = [l.url for l in links]
        assert "https://dept.gov.in/boq.pdf" in urls


def test_extract_plain_text_url_from_pdf():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = str(Path(tmpdir) / "test.pdf")
        make_pdf_with_text("See specifications at https://dept.gov.in/specs.pdf for details.", pdf_path)

        links = extract_links(pdf_path)
        urls = [l.url for l in links]
        assert any("specs.pdf" in u for u in urls)


def test_extract_links_empty_pdf_returns_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = str(Path(tmpdir) / "empty.pdf")
        make_pdf_with_text("No links here, just plain text.", pdf_path)

        links = extract_links(pdf_path)
        doc_links = [l for l in links if l.looks_like_document]
        assert doc_links == []


def test_duplicate_urls_not_returned_twice():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = str(Path(tmpdir) / "test.pdf")
        make_pdf_with_text("https://dept.gov.in/boq.pdf and https://dept.gov.in/boq.pdf again.", pdf_path)

        links = extract_links(pdf_path)
        urls = [l.url for l in links]
        assert len(urls) == len(set(urls))


# ---------------------------------------------------------------------------
# fetch_linked_document
# ---------------------------------------------------------------------------

def test_fetch_linked_document_success():
    fake_content = b"%PDF-1.4 fake pdf content"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-length": str(len(fake_content))}
    mock_response.iter_content = lambda chunk_size: iter([fake_content])
    mock_response.raise_for_status = MagicMock()

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir)
        with patch("src.document_processing.linked_documents.requests.get", return_value=mock_response):
            result = fetch_linked_document("https://dept.gov.in/boq.pdf", dest)

    assert result is not None
    assert result.file_name == "boq.pdf"
    assert result.size_bytes == len(fake_content)
    assert len(result.file_hash) == 64  # sha256 hex


def test_fetch_linked_document_network_error_returns_none():
    import requests as req

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir)
        with patch("src.document_processing.linked_documents.requests.get", side_effect=req.ConnectionError("offline")):
            result = fetch_linked_document("https://dept.gov.in/boq.pdf", dest)

    assert result is None


def test_fetch_linked_document_over_size_cap_returns_none():
    big_content = b"x" * (60 * 1024 * 1024)  # 60 MB > 50 MB cap

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-length": str(len(big_content))}
    mock_response.raise_for_status = MagicMock()

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir)
        with patch("src.document_processing.linked_documents.requests.get", return_value=mock_response):
            result = fetch_linked_document("https://dept.gov.in/huge.pdf", dest)

    assert result is None


# ---------------------------------------------------------------------------
# discover_and_fetch_linked_documents (integration)
# ---------------------------------------------------------------------------

def test_discover_and_fetch_full_flow():
    fake_content = b"%PDF-1.4 fake linked pdf"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-length": str(len(fake_content))}
    mock_response.iter_content = lambda chunk_size: iter([fake_content])
    mock_response.raise_for_status = MagicMock()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a source PDF that references an external PDF by URL.
        pdf_path = str(Path(tmpdir) / "notice.pdf")
        make_pdf_with_text("See BOQ at https://dept.gov.in/boq.pdf for item details.", pdf_path)

        dest = Path(tmpdir) / "linked"
        with patch("src.document_processing.linked_documents.requests.get", return_value=mock_response):
            fetched = discover_and_fetch_linked_documents(pdf_path, dest)

    assert len(fetched) == 1
    assert fetched[0].file_name == "boq.pdf"


def test_no_document_links_returns_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = str(Path(tmpdir) / "notice.pdf")
        make_pdf_with_text("This document has no external links at all.", pdf_path)

        dest = Path(tmpdir) / "linked"
        fetched = discover_and_fetch_linked_documents(pdf_path, dest)

    assert fetched == []
