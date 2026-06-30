#!/usr/bin/env python3
"""scripts/migrate.py — Applies migrations/*.sql in order against DATABASE_URL."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from src.audit_logging.db import get_engine

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def main():
    engine = get_engine()
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print("No migration files found.")
        return

    with engine.connect() as conn:
        for f in files:
            print(f"Applying {f.name}...")
            sql = f.read_text()
            conn.execute(text(sql))
            conn.commit()
    print(f"Applied {len(files)} migration(s).")


if __name__ == "__main__":
    main()
