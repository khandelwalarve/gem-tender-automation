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

CREATE TABLE IF NOT EXISTS company_profile (
    id              SERIAL PRIMARY KEY,
    version         INT NOT NULL,
    data            JSONB NOT NULL,         -- certifications, categories, turnover, experience, etc.
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS past_projects (
    id              SERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    client          TEXT,
    value_inr       NUMERIC,
    category        TEXT,
    completed_on    DATE,
    detail          JSONB
);

CREATE TABLE IF NOT EXISTS tender_extracted_data (
    id              SERIAL PRIMARY KEY,
    tender_id       INT REFERENCES tenders(id) UNIQUE,
    data            JSONB NOT NULL,         -- validated TenderData per Pydantic schema
    extracted_at    TIMESTAMPTZ DEFAULT NOW(),
    schema_version  TEXT
);

CREATE TABLE IF NOT EXISTS eligibility_results (
    id              SERIAL PRIMARY KEY,
    tender_id       INT REFERENCES tenders(id),
    score           NUMERIC NOT NULL,
    is_eligible     BOOLEAN NOT NULL,
    report          JSONB,
    evaluated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feasibility_results (
    id              SERIAL PRIMARY KEY,
    tender_id       INT REFERENCES tenders(id),
    is_feasible     BOOLEAN NOT NULL,
    report          JSONB,
    evaluated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk_flags (
    id              SERIAL PRIMARY KEY,
    tender_id       INT REFERENCES tenders(id),
    flag_type       TEXT NOT NULL,          -- missing_date | conflicting_clause | split_tender | ambiguous | excessive_penalty
    severity        TEXT NOT NULL,          -- low | medium | high
    description     TEXT,
    detail          JSONB,
    detected_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decisions (
    id              SERIAL PRIMARY KEY,
    tender_id       INT REFERENCES tenders(id) UNIQUE,
    outcome         TEXT NOT NULL,          -- auto_submit | human_approval | rejected
    score           NUMERIC,
    reasons         JSONB,
    decided_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bid_submissions (
    id              SERIAL PRIMARY KEY,
    tender_id       INT REFERENCES tenders(id) UNIQUE,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | in_progress | submitted | failed | needs_human
    emd_paid        BOOLEAN DEFAULT FALSE,
    otp_verified    BOOLEAN DEFAULT FALSE,
    checkpoint      TEXT,                   -- last completed form section, for resume
    submitted_at    TIMESTAMPTZ,
    detail          JSONB
);

CREATE INDEX IF NOT EXISTS idx_tenders_bid_id ON tenders(bid_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_tender_id ON audit_log(tender_id);
CREATE INDEX IF NOT EXISTS idx_risk_flags_tender_id ON risk_flags(tender_id);
CREATE INDEX IF NOT EXISTS idx_company_profile_active ON company_profile(is_active);
