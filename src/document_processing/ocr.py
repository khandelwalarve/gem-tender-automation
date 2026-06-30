"""
ocr.py — Detects whether a PDF is text-based or scanned, and runs OCR on
scanned pages. Pages where OCR confidence is too low are flagged for human
QC rather than silently passed on to the LLM with garbage text.
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

OCR_CONFIDENCE_THRESHOLD = 0.65


@dataclass
class PageQuality:
    page_number: int
    text_char_count: int
    is_scanned: bool
    ocr_confidence: float | None = None
    needs_human_qc: bool = False


def detect_pdf_type(pdf_path: str) -> list[PageQuality]:
    """
    Per page, decide whether it already has extractable text (digital PDF)
    or needs OCR (scanned image). Heuristic: very low character count per
    page with a non-trivial page size implies a scanned page.
    """
    doc = fitz.open(pdf_path)
    results: list[PageQuality] = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        is_scanned = len(text) < 20  # essentially no extractable text
        results.append(PageQuality(page_number=i, text_char_count=len(text), is_scanned=is_scanned))
    doc.close()
    return results


def run_ocr(pdf_path: str, output_path: str | None = None) -> str:
    """
    Runs ocrmypdf on the given file to add a searchable text layer.
    Returns the path to the OCR'd output file.
    """
    output_path = output_path or str(Path(pdf_path).with_suffix(".ocr.pdf"))
    subprocess.run(
        [
            "ocrmypdf",
            "--skip-text",       # don't re-OCR pages that already have text
            "--output-type", "pdf",
            "--sidecar", str(Path(output_path).with_suffix(".txt")),
            pdf_path,
            output_path,
        ],
        check=True,
        capture_output=True,
    )
    return output_path


def estimate_ocr_confidence(sidecar_txt_path: str) -> float:
    """
    ocrmypdf's sidecar text doesn't include per-word confidence directly;
    as a practical proxy we check for garbled-text indicators (very short
    average word length, high ratio of non-alphanumeric characters).
    """
    path = Path(sidecar_txt_path)
    if not path.exists():
        return 0.0

    text = path.read_text(errors="ignore")
    if not text.strip():
        return 0.0

    words = text.split()
    if not words:
        return 0.0

    avg_word_len = sum(len(w) for w in words) / len(words)
    alnum_ratio = sum(c.isalnum() or c.isspace() for c in text) / len(text)

    # crude scoring: reasonable word length + mostly alphanumeric = higher confidence
    score = min(1.0, (avg_word_len / 6.0) * 0.5 + alnum_ratio * 0.5)
    return round(score, 2)


def process_pdf_ocr(pdf_path: str) -> tuple[str, list[PageQuality]]:
    """
    Full OCR pipeline for one file:
    1. Detect which pages need OCR
    2. Run OCR if any page needs it
    3. Estimate confidence and flag low-confidence pages for human QC

    Returns (final_pdf_path, page_quality_list).
    """
    pages = detect_pdf_type(pdf_path)
    needs_ocr = any(p.is_scanned for p in pages)

    if not needs_ocr:
        return pdf_path, pages

    ocr_output = run_ocr(pdf_path)
    sidecar = str(Path(ocr_output).with_suffix(".txt"))
    confidence = estimate_ocr_confidence(sidecar)

    for p in pages:
        if p.is_scanned:
            p.ocr_confidence = confidence
            p.needs_human_qc = confidence < OCR_CONFIDENCE_THRESHOLD

    return ocr_output, pages
