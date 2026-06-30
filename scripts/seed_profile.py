#!/usr/bin/env python3
"""
scripts/seed_profile.py — Inserts the initial ITCONS company profile.
Edit the PROFILE_DATA dict below to reflect real company details, then run once.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from src.audit_logging.db import get_session

PROFILE_DATA = {
    "company_name": "PS ITCONS",
    "annual_turnover_inr": 0,
    "years_in_operation": 0,
    "certifications": [],
    "service_categories": [],
    "is_mse": False,
    "is_startup": False,
}


def main():
    session = get_session()
    try:
        session.execute(text("UPDATE company_profile SET is_active = FALSE WHERE is_active = TRUE"))
        result = session.execute(
            text(
                """
                INSERT INTO company_profile (version, data, is_active)
                VALUES (
                    COALESCE((SELECT MAX(version) FROM company_profile), 0) + 1,
                    :data,
                    TRUE
                )
                RETURNING version
                """
            ),
            {"data": json.dumps(PROFILE_DATA)},
        )
        version = result.scalar_one()
        session.commit()
        print(f"Seeded company profile version {version}.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
