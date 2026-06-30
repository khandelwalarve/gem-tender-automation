#!/usr/bin/env python3
"""
run_pipeline.py — CLI entry point to run the full pipeline for one or more
Bid IDs.

Usage:
    python scripts/run_pipeline.py BID-2024-001 [--feasibility-pdf path] [--reviewer email] [--price 1234567]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Run the GeM tender automation pipeline for a Bid ID")
    parser.add_argument("bid_id", help="GeM Bid ID to process")
    parser.add_argument("--feasibility-pdf", default=None, help="Path to feasibility threshold PDF")
    parser.add_argument("--reviewer-email", default=None, help="Email to notify for human approval")
    parser.add_argument("--reviewer-phone", default=None, help="Phone number to notify for human approval")
    parser.add_argument("--price", type=float, default=None, help="Quoted price (INR) for auto-submit bids")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--headed", dest="headless", action="store_false")
    args = parser.parse_args()

    result = run_pipeline(
        bid_id=args.bid_id,
        feasibility_pdf_path=args.feasibility_pdf,
        reviewer_email=args.reviewer_email,
        reviewer_phone=args.reviewer_phone,
        quoted_price_inr=args.price,
        headless=args.headless,
    )

    print("\n--- Pipeline Result ---")
    for k, v in result.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
