#!/usr/bin/env python3
"""
scheduler.py — Runs periodic background jobs:
1. Corrigendum re-check for every active (non-terminal) tender
2. Deadline reminder / auto-reject sweep for pending human reviews

Run this as a long-lived process (e.g. via systemd or a Docker sidecar).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import text

from src.audit_logging.db import get_session
from src.human_approval import check_pending_deadlines
from src.tender_acquisition import check_for_corrigendum


def corrigendum_sweep():
    session = get_session()
    try:
        active = session.execute(
            text("SELECT id, bid_id FROM tenders WHERE status NOT IN ('rejected', 'submitted')")
        ).mappings().all()
    finally:
        session.close()

    for row in active:
        check_for_corrigendum(row["bid_id"], row["id"])


def deadline_sweep():
    check_pending_deadlines()


def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(corrigendum_sweep, "interval", hours=6, id="corrigendum_sweep")
    scheduler.add_job(deadline_sweep, "interval", minutes=30, id="deadline_sweep")

    print("Scheduler started. Corrigendum sweep every 6h, deadline sweep every 30m.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
