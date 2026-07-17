# Job Hunting Agent

Single-user tool that sources PM job postings, scores whether they're worth applying to, drafts tailored materials, and opens/fills the application for review before you submit. See `MILESTONES.md` for the build plan.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: set OPENAI_API_KEY and OPENAI_MODEL before Milestone 4
```

## Run

```bash
python app.py init      # create/update data/jobs.db (safe to re-run)
python app.py fetch     # pull job postings from companies in config/companies.yaml
python app.py filter    # deterministic title pre-filter - no LLM calls, preview savings before scoring
python app.py score     # evaluate eligible jobs against your candidate profile (add --rescore to redo all)
python app.py status    # print row counts for every table
python app.py serve     # start the dashboard at http://localhost:5000
```

Workflow: **fetch → filter → (review) → score**. Each stage is explicit and separate — `score` no longer runs the title filter automatically, so if you skip `filter`, every sourced job gets scored (same as before this stage existed).

`/health` returns `{"status": "ok"}`. Visit `/profile` to fill in your candidate profile before scoring — new profiles get sensible title-filter defaults seeded automatically (see Candidate Profile below), everything else starts empty.

## Adding a company to fetch from

Add an entry to `config/companies.yaml` with `name`, `slug`, and `ats` (`greenhouse` | `lever` | `ashby`). Confirm the slug is correct first:

```bash
curl -s "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs" | head -c 200   # greenhouse
curl -s "https://api.lever.co/v0/postings/{slug}?mode=json" | head -c 200        # lever
curl -s "https://api.ashbyhq.com/posting-api/job-board/{slug}" | head -c 200     # ashby
```

A 200 with job data confirms it; a 404 means wrong slug or that company isn't on that ATS.

## Candidate Profile

`/profile` is the source of truth for evaluation — structured fields only, no narrative text: target/excluded titles (deterministic filter), preferred/excluded industries, preferred locations, remote preference, min/preferred salary, strongest skills, known gaps, preferred company size, years of experience, stretch-role willingness, plus contact info (name/email/phone/LinkedIn URL) used when filling applications. List fields take comma-separated values. `/profile/import` extracts a first draft from pasted LinkedIn/resume text for review before saving. Edit it in the browser, not in a prompt file.

New profiles get seeded with sensible title-filter defaults (`target_titles`: product manager, product operations, chief of staff; `excluded_titles`: engineer, designer, accountant, accounting, finance, security, attorney, counsel, sales, recruiter, hr, people partner, customer support) — this only happens once, on first creation of the profile row; re-running `python app.py init` never overwrites an existing, customized profile.

## Deterministic title filter (`python app.py filter`)

Runs before any LLM call, costs nothing: case-insensitive substring match against `target_titles`/`excluded_titles`. Excluded titles always win. A job passes if its title contains any target-title substring (e.g. target `product manager` matches "Senior Product Manager", "Product Manager, Payments Experience", "VP, Product Manager" — no exact-phrase match required) and doesn't contain any excluded-title substring. Jobs that fail move to `jobs.status = 'filtered_title'` — never deleted, still browsable in the dashboard's "Filtered (Title)" section. This is a separate, explicit pipeline stage — `score` does not run it automatically, so you control when it happens (and can preview the impact via the dashboard's "Run Title Filter" button or the CLI before spending any API budget).

## How scoring works (`python app.py score`)

Only touches jobs still in `sourced` status (i.e. already past the title filter, if you ran it). Hybrid, two-stage, per job:

1. **Deterministic rules** (`scoring/rules.py`, pure Python, no API call): checks salary floor, remote/location fit, and excluded industries. Anything failing here is an instant `archive` with the specific reason recorded — the LLM is never called.
2. **LLM judgment** (only for jobs that pass rules): the OpenAI Responses API answers the subjective questions — should you spend time on this, strongest selling points, biggest gaps, positioning strategy, is it a worthwhile stretch. Decisions are `priority | apply | stretch | archive` — no job is ever hidden or rejected, only grouped.

Every evaluation — rule-based archive or LLM judgment — writes a row to `job_evaluations`. Re-scoring a job adds a new row rather than overwriting the old one, so you can compare results across profile edits, prompt edits, or model changes over time. A job only gets marked `scored` if an evaluation actually completed; failed OpenAI calls (bad/missing key, rate limit) are logged to `model_runs.error_message` and the job stays `sourced` so `python app.py score` retries it next time, without you losing the rest of the batch.

## Career Brain (`career_brain/`)

The long-term source of truth about you as a candidate — markdown files on disk, no database, no embeddings, no vector search. See `career_brain/README.md` for the full explanation. Short version: drop `.md` files into `career_brain/profile/`, `career_brain/stories/`, `career_brain/evidence/`, `career_brain/preferences/` and they're automatically included in every future resume-summary/cover-letter generation — no registration, no restart. `python app.py career-brain` previews exactly which documents would be loaded, without generating anything.

Career Brain content layers **on top of** your existing LinkedIn/resume context for materials generation — it doesn't replace it, so generation quality never regresses even while the folder is empty. It does **not** feed recommendation scoring (`recommend_job`) at all — that stays exactly as it was, reading only your structured profile + LinkedIn/resume text. Every generation records exactly which Career Brain documents it used (`applications.career_brain_docs`), shown on the job detail page, so any past resume/cover letter is reproducible.

## Current state

- Sourcing: `jobs/greenhouse.py`, `jobs/lever.py`, `jobs/ashby.py` return the same `NormalizedJob` shape; `jobs/fetch.py` handles fetch + dedup. Currently configured: Gusto, Rover, Patreon (~115 postings). Expanding to the full target list is a deferred milestone.
- Scoring: verified end-to-end against a live OpenAI call (not just structurally) — the hybrid rules+LLM engine, the title filter, LinkedIn/resume import + extraction, job detail page, resume-summary/cover-letter draft generation, and a Playwright-based Greenhouse partial-fill are all built and tested against real data.
- Materials generation now also pulls from Career Brain (see above) — verified end-to-end with a real generation while the folder was still empty (graceful no-op) and with isolated unit tests proving the non-empty path builds the combined context correctly.
- `positioning_profiles` (renamed from `candidate_profiles`) holds 5 seeded archetype rows (Senior PM, Platform PM, Marketplace PM, Product Operations, Chief of Staff) — a future resume/story routing layer, still not wired into scoring.
- `candidate_stories` (SQLite table) is empty — separate from Career Brain (markdown files); populate whichever one you actually use before scoring/materials cite strong evidence. Until then the AI is told explicitly not to fabricate evidence.
- No automated application submission exists anywhere in this project, and won't until you explicitly ask for it.
