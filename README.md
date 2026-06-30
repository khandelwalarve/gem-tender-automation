# GeM Tender Automation – PS ITCONS

An end-to-end automation framework for Government e-Marketplace (GeM) tender bidding.

## Architecture Overview

The pipeline runs through 11 sequential phases:

| # | Phase | Owner | Key Tools |
|---|-------|-------|-----------|
| 1 | Tender Acquisition | Automation | Playwright, PostgreSQL, Pandas |
| 2 | Document Processing | AI Engine | PyMuPDF, OCRmyPDF, Camelot, Tabula |
| 3 | Tender Understanding | AI Engine | Qwen, Pydantic |
| 4 | Eligibility Engine | Rules Engine | Python, PostgreSQL |
| 5 | Feasibility Analysis | Rules Engine | Python, Qwen |
| 6 | Risk Detection | AI + Rules | Qwen, PostgreSQL |
| 7 | Decision Engine | Rules Engine | Python |
| 8 | Human Approval | Human + Dashboard | React, FastAPI |
| 9 | Bid Participation | Automation | Playwright, Python |
| 10 | Audit & Logging | Automation | PostgreSQL, Pandas |
| 11 | Dashboard | Dashboard | React, FastAPI |

## Project Structure

```
gem-tender-automation/
├── src/
│   ├── tender_acquisition/      # GeM session management, download, storage
│   ├── document_processing/     # PDF parsing, OCR, chunking
│   ├── tender_understanding/    # LLM extraction, JSON schema
│   ├── eligibility_engine/      # Company profile matching
│   ├── feasibility_analysis/    # Threshold checks vs. feasibility PDF
│   ├── risk_detection/          # Clause conflict, penalty, ambiguity flags
│   ├── decision_engine/         # Auto-submit / Human-approval / Reject
│   ├── human_approval/          # Notification, escalation, deadline timer
│   ├── bid_participation/       # Form fill, EMD, OTP, submission
│   ├── audit_logging/           # Immutable event log
│   └── dashboard/               # React frontend
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       └── api/
├── config/                      # YAML/env config files
├── migrations/                  # DB schema migrations
├── tests/                       # Unit + integration tests
├── scripts/                     # One-off / maintenance scripts
└── docs/                        # Architecture docs, ADRs
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp config/settings.example.yaml config/settings.yaml
# Edit config/settings.yaml with your credentials and DB URL

# Run DB migrations
python scripts/migrate.py

# Seed the initial company profile (edit scripts/seed_profile.py first)
python scripts/seed_profile.py

# One-time human login to GeM (saves session cookies for automation)
python -c "from src.tender_acquisition import save_session_interactive; save_session_interactive()"

# Start the backend
uvicorn src.main:app --reload

# Start the dashboard
cd src/dashboard && npm install && npm run dev
```

## Running the Pipeline

```bash
# Process a single Bid ID end-to-end
python scripts/run_pipeline.py BID-2024-001 \
  --feasibility-pdf docs/feasibility_thresholds.pdf \
  --reviewer-email ops@psitcons.example \
  --price 1234567

# Long-running background jobs (corrigendum checks, deadline reminders)
python scripts/scheduler.py
```

## Configuration

All runtime config lives in `config/settings.yaml` (never committed). See `config/settings.example.yaml` for required keys:

- PostgreSQL connection string
- MinIO / local storage path
- Qwen endpoint / API key
- Alert email / SMS credentials
- Approval rule thresholds (score cutoffs, value limits, risk caps)

## Key Design Decisions

- **Session management**: Human logs in once; automation stores and reuses cookies. Expired sessions trigger an operator alert before any processing begins.
- **Download completeness gate**: All files must pass a completeness check before a tender is registered in the DB.
- **Corrigendum re-checks**: A scheduler re-hashes GeM files for every active Bid ID to catch amendments.
- **OCR quality gate**: Low-confidence pages are flagged for human QC before text extraction proceeds.
- **JSON schema validation**: LLM output is validated against a Pydantic schema; failures route to human review.
- **Feasibility thresholds**: Extracted from a client-provided PDF; no hardcoded limits.
- **Decision engine**: Approval rules (score cutoffs, value limits) must be configured before first deployment.
- **Form checkpointing**: Playwright saves form state after each section; failures attempt resume from last checkpoint.
- **CAPTCHA handling**: Detected after every Playwright interaction; triggers human takeover via dashboard alert.
- **OTP escalation**: Alert at T-1h; backup OTP holder notified if primary is unavailable.
- **Audit log**: Every failure captures exception type, phase, step, timestamp, and tender ID.

## Running Tests

```bash
pytest tests/
```
