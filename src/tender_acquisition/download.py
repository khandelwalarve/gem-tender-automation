"""
download.py — Search for a Bid ID on GeM, download all attached documents,
hash them, and run a completeness check before the tender is registered.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import BrowserContext

from src.common.config import get_settings

DOWNLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "files"


class IncompleteDownloadError(Exception):
    """Raised when expected tender files are missing after a download attempt."""


@dataclass
class DownloadedFile:
    file_name: str
    storage_path: str
    file_hash: str
    size_bytes: int


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def search_tender(context: BrowserContext, bid_id: str):
    """Navigate to the GeM bid search page and open the tender detail page for bid_id."""
    page = context.new_page()
    page.goto("https://bidplus.gem.gov.in/bidresultlist")
    page.fill("input[name='bidNo']", bid_id)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    page.click(f"text={bid_id}")
    page.wait_for_load_state("networkidle")
    return page


def download_tender_files(context: BrowserContext, bid_id: str) -> list[DownloadedFile]:
    """
    Downloads every attachment listed on the tender detail page.
    Returns the list of downloaded files with hashes for dedupe / corrigendum detection.
    """
    dest_dir = DOWNLOAD_ROOT / bid_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    page = search_tender(context, bid_id)
    attachment_links = page.query_selector_all("a.attachment-link")

    if not attachment_links:
        raise IncompleteDownloadError(f"No attachments found on tender page for {bid_id}")

    downloaded: list[DownloadedFile] = []
    for link in attachment_links:
        with page.expect_download() as download_info:
            link.click()
        download = download_info.value
        target_path = dest_dir / download.suggested_filename
        download.save_as(str(target_path))

        downloaded.append(
            DownloadedFile(
                file_name=download.suggested_filename,
                storage_path=str(target_path),
                file_hash=_hash_file(target_path),
                size_bytes=target_path.stat().st_size,
            )
        )

    page.close()
    return downloaded


def check_completeness(files: list[DownloadedFile]) -> None:
    """
    Raises IncompleteDownloadError if mandatory document types are missing,
    or if any file is suspiciously small (likely a failed/partial download).
    """
    settings = get_settings()
    required_keywords = settings.get("tender_acquisition", {}).get(
        "required_doc_keywords", ["notice", "tender"]
    )

    names_lower = [f.file_name.lower() for f in files]
    for keyword in required_keywords:
        if not any(keyword in name for name in names_lower):
            raise IncompleteDownloadError(
                f"Mandatory document containing '{keyword}' not found among downloaded files: {names_lower}"
            )

    for f in files:
        if f.size_bytes < 1024:  # 1 KB — almost certainly a failed download
            raise IncompleteDownloadError(f"File '{f.file_name}' is suspiciously small ({f.size_bytes} bytes)")
