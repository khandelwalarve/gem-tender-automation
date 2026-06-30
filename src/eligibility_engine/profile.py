"""
profile.py — Loads the active ITCONS company profile and past project history
from the database, and warns if the profile is stale.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from src.audit_logging import Phase, log_warning
from src.audit_logging.db import get_session
from src.common.config import get_settings


def get_active_profile() -> dict[str, Any] | None:
    session = get_session()
    try:
        row = session.execute(
            text(
                """
                SELECT data, created_at FROM company_profile
                WHERE is_active = TRUE
                ORDER BY version DESC
                LIMIT 1
                """
            )
        ).first()
        if row is None:
            return None

        data, created_at = row
        settings = get_settings()
        staleness_days = settings.get("profile", {}).get("staleness_warning_days", 30)

        if created_at and datetime.utcnow() - created_at.replace(tzinfo=None) > timedelta(days=staleness_days):
            log_warning(
                phase=Phase.ELIGIBILITY_ENGINE,
                step="Profile Staleness Check",
                detail={"created_at": str(created_at), "staleness_threshold_days": staleness_days},
            )

        return data
    finally:
        session.close()


def get_past_projects(category: str | None = None) -> list[dict[str, Any]]:
    session = get_session()
    try:
        if category:
            rows = session.execute(
                text("SELECT title, client, value_inr, category, completed_on, detail FROM past_projects WHERE category = :cat"),
                {"cat": category},
            ).mappings().all()
        else:
            rows = session.execute(
                text("SELECT title, client, value_inr, category, completed_on, detail FROM past_projects")
            ).mappings().all()
        return [dict(r) for r in rows]
    finally:
        session.close()
