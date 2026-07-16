-- Job Hunting Agent schema. All CREATE statements are idempotent (IF NOT EXISTS)
-- so `python app.py init` is safe to re-run.

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,              -- greenhouse | lever | ashby
    external_id TEXT NOT NULL,         -- ID from the source ATS
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    location TEXT,
    remote_type TEXT,                  -- remote | hybrid | onsite | unknown
    salary_min INTEGER,
    salary_max INTEGER,
    industry TEXT,                     -- from config/companies.yaml, for excluded_industries rule
    description TEXT,                  -- raw JD text
    jd_hash TEXT,                      -- hash of description, for change detection
    status TEXT NOT NULL DEFAULT 'sourced',
        -- sourced | filtered_title | scored | drafted | reviewed | approved | applied | skipped
        -- filtered_title = failed the deterministic title pre-filter (scoring/title_filter.py)
        -- before ever reaching the LLM; still browsable, never deleted.
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (source, external_id)
);

-- Reusable evidence library: real things Jais has done, cited by ID in
-- job evaluations, resume tailoring, cover letters, and application answers.
CREATE TABLE IF NOT EXISTS candidate_stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT,                     -- e.g. product_strategy, marketplace, growth, operations
    situation TEXT,
    actions TEXT,
    result TEXT,
    metrics TEXT,                      -- JSON array: [{name, value, confidence}]
    skills TEXT,                       -- JSON array of strings
    best_for_role_types TEXT,          -- JSON array of strings
    best_for_industries TEXT,          -- JSON array of strings
    confidence TEXT,                   -- verified | estimated | needs_review
    approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Every AI provider call, successful or failed. Nothing gets silently discarded.
CREATE TABLE IF NOT EXISTS model_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
        -- recommend_job | generate_resume_summary | tailor_resume
        -- | generate_cover_letter | answer_application_question
    job_id INTEGER REFERENCES jobs(id),
    prompt_file TEXT NOT NULL,
    prompt_version TEXT NOT NULL,      -- short hash of the prompt file content
    model_name TEXT NOT NULL,
    input_context TEXT,                -- JSON snapshot of what was sent to the model
    raw_output TEXT,
    parsed_output TEXT,                -- JSON, null if parsing/validation failed
    success INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Named positioning lenses for scoring/materials (e.g. Senior PM, Platform
-- PM, Chief of Staff). Not the same thing as `candidate_profile` below — this
-- is "which pitch angle", that's "who Jais is and what she wants". Not wired
-- into the evaluation engine yet — exists so routing logic lives in data,
-- not hardcoded Python, once we get there.
CREATE TABLE IF NOT EXISTS positioning_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    target_role_types TEXT,            -- JSON array of strings
    preferred_resume_template TEXT,     -- path under materials/docx_templates, nullable until M8
    preferred_prompt_set TEXT,          -- JSON mapping task_type -> prompt filename, null = defaults
    preferred_candidate_story_ids TEXT, -- JSON array of candidate_stories.id
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO positioning_profiles (name, target_role_types) VALUES
    ('Senior PM', '["Senior Product Manager"]'),
    ('Platform PM', '["Platform Product Manager", "Product Manager, Platform"]'),
    ('Marketplace PM', '["Product Manager, Marketplace", "Senior PM, Marketplace"]'),
    ('Product Operations', '["Product Operations Lead", "Head of Product Operations"]'),
    ('Chief of Staff', '["Chief of Staff", "Chief of Staff to the CEO"]');

-- The source of truth for evaluation: structured search criteria, editable
-- from the /profile page. Singleton row (id is always 1) since this is a
-- single-user tool. No long-form narrative text in the structured fields —
-- but linkedin_text/resume_text hold raw imported source material, which is
-- read via scoring/context.build_candidate_context() rather than referenced
-- directly by name in provider code. That indirection is deliberate: a
-- future "Career Brain" can become the candidate_context source later
-- without changing the AIProvider interface.
CREATE TABLE IF NOT EXISTS candidate_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    linkedin_url TEXT,
    linkedin_text TEXT,                 -- raw pasted LinkedIn profile text, source for extraction + context
    resume_text TEXT,                   -- raw pasted resume text, supporting context
    target_titles TEXT NOT NULL DEFAULT '[]',           -- JSON array of strings, deterministic title filter
    excluded_titles TEXT NOT NULL DEFAULT '[]',         -- JSON array of strings, deterministic title filter
    preferred_industries TEXT NOT NULL DEFAULT '[]',    -- JSON array of strings, LLM context only
    excluded_industries TEXT NOT NULL DEFAULT '[]',     -- JSON array of strings, hard rule
    preferred_locations TEXT NOT NULL DEFAULT '[]',     -- JSON array of strings
    remote_preference TEXT,            -- remote_only | hybrid_ok | onsite_ok | no_preference
    min_salary INTEGER,                -- hard rule
    preferred_salary INTEGER,          -- LLM context only
    strongest_skills TEXT NOT NULL DEFAULT '[]',        -- JSON array of strings
    known_gaps TEXT NOT NULL DEFAULT '[]',              -- JSON array of strings
    preferred_company_size TEXT NOT NULL DEFAULT '[]',  -- JSON array of strings, LLM context only
    years_experience INTEGER,
    stretch_willingness TEXT,          -- low | medium | high
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Sensible starting point for the title filter on a brand-new profile.
-- INSERT OR IGNORE means this only ever fires once, on first creation of
-- row id=1 — re-running `init` never touches an existing, possibly
-- customized profile.
INSERT OR IGNORE INTO candidate_profile (id, target_titles, excluded_titles) VALUES (
    1,
    '["product manager", "product operations", "chief of staff"]',
    '["engineer", "designer", "accountant", "accounting", "finance", "security", "attorney", "counsel", "sales", "recruiter", "hr", "people partner", "customer support"]'
);

-- Historical evaluation records: every time a job is scored, a new row is
-- added here rather than overwriting the previous one. This is what lets us
-- compare different prompts, candidate profiles, or models over time.
--
-- No job is ever "rejected" — every evaluated job stays visible, grouped by
-- decision: priority (best fit, apply now), apply (solid fit), stretch
-- (experience isn't an obvious fit today, but the role/company/learning may
-- justify applying anyway), archive (hard disqualifier, e.g. rule-based
-- salary/location/industry mismatch, or the AI found no credible angle).
CREATE TABLE IF NOT EXISTS job_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    positioning_profile_id INTEGER REFERENCES positioning_profiles(id),
    model_run_id INTEGER REFERENCES model_runs(id),
    score INTEGER,                     -- 0-100
    decision TEXT,                     -- priority | apply | stretch | archive
    reasons_to_apply TEXT,             -- JSON array of strings
    gaps TEXT,                         -- JSON array of strings
    disqualifiers TEXT,                -- JSON array of strings
    positioning_strategy TEXT,
    evidence_story_ids TEXT,           -- JSON array of candidate_stories.id
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    resume_summary TEXT,               -- generated text, reviewable/editable; DOCX injection is M8, not yet built
    cover_letter_body TEXT,            -- generated text, reviewable/editable
    resume_path TEXT,                  -- populated once M8 (branded DOCX injection) exists
    cover_letter_path TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
        -- draft | reviewed | approved | filled | submitted
    applied_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (job_id)
);

CREATE TABLE IF NOT EXISTS application_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    question TEXT NOT NULL,
    answer TEXT,
    confidence TEXT,                   -- verified | estimated | needs_review
    evidence_story_ids TEXT,           -- JSON array of candidate_stories.id
    model_run_id INTEGER REFERENCES model_runs(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
