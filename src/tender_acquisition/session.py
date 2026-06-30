"""
session.py — GeM session management.

First-time login is done by a human (headed browser). The resulting cookies
are persisted to disk and reused by automation. If the session has expired,
this module raises SessionExpiredError so the caller can alert an operator
rather than silently failing mid-pipeline.
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright, sync_playwright

SESSION_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "gem_session.json"
GEM_LOGIN_URL = "https://mkp.gem.gov.in/login/seller/sso"
GEM_DASHBOARD_URL = "https://mkp.gem.gov.in/sellerdashboard"


class SessionExpiredError(Exception):
    """Raised when the stored GeM session cookies are no longer valid."""


def save_session_interactive() -> None:
    """
    Run once by a human. Opens a headed browser, waits for manual login,
    then persists the storage state (cookies + local storage) to disk.
    """
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(GEM_LOGIN_URL)
        print("Log in manually in the opened browser window, then press Enter here once done...")
        input()
        context.storage_state(path=str(SESSION_FILE))
        browser.close()
    print(f"Session saved to {SESSION_FILE}")


def load_context(playwright: Playwright, headless: bool = True) -> BrowserContext:
    """
    Restore a browser context from the saved session. Raises SessionExpiredError
    if no session file exists yet (first-time setup not done).
    """
    if not SESSION_FILE.exists():
        raise SessionExpiredError(
            "No saved GeM session found. Run save_session_interactive() once to log in manually."
        )
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(storage_state=str(SESSION_FILE))
    return context


def verify_session(context: BrowserContext) -> bool:
    """
    Navigate to the seller dashboard and check whether we were redirected
    to the login page (meaning the session has expired).
    """
    page = context.new_page()
    page.goto(GEM_DASHBOARD_URL)
    page.wait_for_load_state("networkidle")
    is_valid = "login" not in page.url.lower()
    page.close()
    return is_valid


def assert_session_valid(context: BrowserContext) -> None:
    if not verify_session(context):
        raise SessionExpiredError(
            "GeM session has expired. An operator must re-run save_session_interactive() "
            "before automation can continue."
        )
