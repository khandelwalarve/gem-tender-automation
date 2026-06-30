"""
text_pipeline.py — Cleans extracted text, detects language, translates
non-English content, and chunks the final text for LLM consumption.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import fitz  # PyMuPDF
from langdetect import detect, LangDetectException

CHUNK_SIZE_CHARS = 4000
CHUNK_OVERLAP_CHARS = 400


def extract_raw_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    text_parts = [page.get_text() for page in doc]
    doc.close()
    return "\n\n".join(text_parts)


def clean_text(text: str) -> str:
    """Strips repeated whitespace, page-number artifacts, and stray control characters."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^\s*Page\s+\d+\s*(of\s*\d+)?\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return text.strip()


def detect_language(text: str) -> str:
    """Returns an ISO 639-1 language code, defaulting to 'en' if detection fails."""
    sample = text[:2000]
    if not sample.strip():
        return "en"
    try:
        return detect(sample)
    except LangDetectException:
        return "en"


def translate_to_english(text: str, source_lang: str) -> str:
    """
    Translates non-English text to English using Argos Translate.
    Assumes the relevant language package has already been installed
    (see scripts/setup_translation.py).
    """
    if source_lang == "en":
        return text

    import argostranslate.translate

    try:
        return argostranslate.translate.translate(text, source_lang, "en")
    except Exception:  # noqa: BLE001 — package not installed for this language pair
        return text  # fall back to original text rather than failing the pipeline


@dataclass
class ProcessedDocument:
    source_path: str
    full_text: str
    language: str
    chunks: list[str]
    page_warnings: list[str]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Splits text into overlapping chunks sized for the LLM's context window."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks
