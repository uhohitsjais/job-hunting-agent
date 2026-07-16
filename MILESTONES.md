# Job Hunting Agent — 48-Hour MVP Milestone Plan

Goal: smallest working tool that finds PM jobs from Greenhouse/Lever/Ashby, scores fit, drafts tailored materials into your branded templates, opens + fills the application, and lets you review before submit. Human-gated, no auto-submit, no invented qualifications.

Stack: Python + SQLite + Flask + Playwright. OpenAI Responses API for all candidate-facing scoring/writing, behind a provider interface. Rule: **app stays runnable after every checkpoint.**

Two things needed from you before their checkpoints hit: a PM candidate profile/narrative doc (needed by M4) and your branded DOCX resume/cover-letter templates (needed by M8).

| # | Hours | Milestone | Acceptance criteria |
|---|-------|-----------|---------------------|
| M1 | 0–3 | Runnable skeleton + SQLite schema | ✅ Done. `python app.py init` creates `data/jobs.db` idempotently; `providers/base.py` interface + `OpenAIProvider` stub |
| M2 | 3–6 | Fetch real jobs from 3 test companies | ✅ Done. Gusto (Greenhouse), Rover (Lever), Patreon (Ashby) — 114 postings, deduped via upsert on `(source, external_id)`. Connectors live in `jobs/` and return a shared `NormalizedJob` type; nothing downstream branches on ATS |
| M3 | 6–9 | Basic web dashboard | ✅ Done as a byproduct of M1+M2 — `python app.py serve` already shows the real fetched jobs in a plain HTML table. No extra work needed |
| M4 | 9–13 | Hybrid recommendation engine | 🟡 Built and tested except the live LLM call. Structured `/profile` page (no narrative doc) replaces the profile-doc blocker. Deterministic rules (salary/location/excluded industries) run first — confirmed working. LLM call (judgment-only: should you apply, selling points, gaps, positioning, stretch worth it) implemented via OpenAI Responses API with structured JSON output — code path confirmed, failure handling confirmed, **live call still needs your `OPENAI_API_KEY` + `OPENAI_MODEL`** |
| M5 | 13–16 | Expand sourcing to 10–15 companies | Add confirmed Greenhouse/Lever/Ashby companies from your target sheet to `config/companies.yaml`; re-fetch pulls from all of them; dashboard now has real volume |
| M6 | 16–19 | Job detail page | Click into a job → see full JD, score, strongest matches, gaps, recommendation (apply/consider/skip) |
| M7 | 19–23 | Draft resume content + cover letter | For jobs above a fit threshold, OpenAI generates structured resume bullet edits + cover letter text (not full documents yet) — stored per job, viewable on detail page |
| M8 | 23–27 | Inject into branded DOCX templates | Approved content gets inserted into your existing `.docx` templates preserving formatting; output saved to `data/generated/`. **Blocked on:** your branded templates |
| M9 | 27–31 | Review queue | Dashboard view: approve / edit / skip per job; status field moves Sourced → Drafted → Reviewed → Approved; this is the "wake up, spend an hour, done" screen |
| M10 | 31–36 | Playwright fill — Greenhouse | For approved jobs on Greenhouse, opens a real browser, navigates to the apply page, fills standard fields (name, email, resume upload, work history) using known Greenhouse form structure, stops before Submit |
| M11 | 36–40 | Lever/Ashby fill | Same as M10, extended to the other two ATSs — only attempted if Greenhouse fill is solid; if it's shaky, this slot becomes Greenhouse hardening instead |
| M12 | 40–48 | Hardening + operating guide | Error logging on every model/scrape call (`data/logs/`), fix rough edges found in dogfooding, short README on how to run `fetch` → `score` → `serve` → review → `fill` daily |

## Rules that hold across every milestone
- Never auto-click Submit. Ever.
- Never invent candidate experience, metrics, or qualifications not in your source materials.
- Pause on sensitive fields (salary expectations, sponsorship, demographic/legal/attestation questions) for manual input.
- One provider file (`providers/base.py`) is the only thing scoring/materials code talks to.
- SQLite is the single source of truth — no Google Sheets sync in this MVP.
