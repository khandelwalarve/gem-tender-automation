-- migrations/001_initial_schema.sql
-- Run once to set up the core tables.

CREATE TABLE IF NOT EXISTS tenders (
    id              SERIAL PRIMARY KEY,
    bid_id          TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL DEFAULT 'pending',
    registered_at   TIMESTAMPTZ DEFAULT NOW(),
    deadline        TIMESTAMPTZ,
    decision        TEXT,          -- auto_submit | human_approval | rejected
    submission_status TEXT,
    win_loss        TEXT,
    profile_version_at_eval TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tender_files (
    id          SERIAL PRIMARY KEY,
    tender_id   INT REFERENCES tenders(id),
    file_name   TEXT NOT NULL,
    file_hash   TEXT NOT NULL,
    downloaded_at TIMESTAMPTZ DEFAULT NOW(),
    storage_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          SERIAL PRIMARY KEY,
    tender_id   INT REFERENCES tenders(id),
    phase       TEXT NOT NULL,
    step        TEXT NOT NULL,
    owner       TEXT,
    event_type  TEXT NOT NULL,   -- info | warning | error | decision
    detail      JSONB,
    occurred_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS human_reviews (
    id          SERIAL PRIMARY KEY,
    tender_id   INT REFERENCES tenders(id),
    assigned_to TEXT,
    notified_at TIMESTAMPTZ,
    decision    TEXT,            -- approved | approved_with_edits | rejected
    decided_at  TIMESTAMPTZ,
    edits       JSONB
);

CREATE INDEX IF NOT EXISTS idx_tenders_bid_id ON tenders(bid_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_tender_id ON audit_log(tender_id);
