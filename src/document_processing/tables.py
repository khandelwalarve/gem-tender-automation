"""
tables.py — Extracts tables from a PDF using both Camelot (bordered/lattice
tables) and Tabula (whitespace-aligned/stream tables), then merges the results,
preferring whichever extractor found more populated cells per table region.
"""
from __future__ import annotations

from dataclasses import dataclass

import camelot
import tabula


@dataclass
class ExtractedTable:
    page: int
    source: str          # "camelot" | "tabula"
    rows: list[list[str]]
    accuracy: float | None = None  # camelot only


def extract_with_camelot(pdf_path: str) -> list[ExtractedTable]:
    """Best for tables with visible borders/lines (lattice mode)."""
    tables = []
    try:
        result = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")
        for t in result:
            tables.append(
                ExtractedTable(
                    page=int(t.page),
                    source="camelot",
                    rows=t.df.values.tolist(),
                    accuracy=t.accuracy if hasattr(t, "accuracy") else None,
                )
            )
    except Exception:  # noqa: BLE001 — camelot raises broadly on malformed PDFs
        pass
    return tables


def extract_with_tabula(pdf_path: str) -> list[ExtractedTable]:
    """Best for whitespace-aligned tables with no visible borders (stream mode)."""
    tables = []
    try:
        dfs = tabula.read_pdf(pdf_path, pages="all", multiple_tables=True, lattice=False, stream=True)
        for i, df in enumerate(dfs):
            tables.append(
                ExtractedTable(
                    page=i,  # tabula doesn't reliably report page number per table
                    source="tabula",
                    rows=df.fillna("").values.tolist(),
                )
            )
    except Exception:  # noqa: BLE001
        pass
    return tables


def extract_tables(pdf_path: str) -> list[ExtractedTable]:
    """
    Runs both extractors and merges results. If Camelot found tables with
    reasonable accuracy (>70%) for a page, prefer those; otherwise fall back
    to Tabula's output for that page.
    """
    camelot_tables = extract_with_camelot(pdf_path)
    tabula_tables = extract_with_tabula(pdf_path)

    good_camelot_pages = {t.page for t in camelot_tables if (t.accuracy or 0) > 70}

    merged = [t for t in camelot_tables if t.page in good_camelot_pages]
    merged += [t for t in tabula_tables if t.page not in good_camelot_pages]

    # If Camelot found nothing useful at all, just return everything Tabula found.
    if not merged and tabula_tables:
        merged = tabula_tables

    return merged
