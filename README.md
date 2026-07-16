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
python app.py score     # evaluate sourced jobs against your candidate profile (add --rescore to redo all)
python app.py status    # print row counts for every table
python app.py serve     # start the dashboard at http://localhost:5000
```

`/health` returns `{"status": "ok"}`. Visit `/profile` to fill in your candidate profile before scoring — it's empty by default.

## Adding a company to fetch from

Add an entry to `config/companies.yaml` with `name`, `slug`, and `ats` (`greenhouse` | `lever` | `ashby`). Confirm the slug is correct first:

```bash
curl -s "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs" | head -c 200   # greenhouse
curl -s "https://api.lever.co/v0/postings/{slug}?mode=json" | head -c 200        # lever
curl -s "https://api.ashbyhq.com/posting-api/job-board/{slug}" | head -c 200     # ashby
```

A 200 with job data confirms it; a 404 means wrong slug or that company isn't on that ATS.

## Candidate Profile

`/profile` is the source of truth for evaluation — structured fields only, no narrative text: target titles, preferred/excluded industries, preferred locations, remote preference, min/preferred salary, strongest skills, known gaps, preferred company size, years of experience, stretch-role willingness. List fields take comma-separated values. Edit it in the browser, not in a prompt file.

## How scoring works (`python app.py score`)

Hybrid, two-stage, per job:

1. **Deterministic rules first** (`scoring/rules.py`, pure Python, no API call): checks salary floor, remote/location fit, and excluded industries. Anything failing here is an instant `skip` with the specific reason recorded — the LLM is never called.
2. **LLM judgment second** (only for jobs that pass rules): the OpenAI Responses API answers the subjective questions — should you spend time on this, strongest selling points, biggest gaps, positioning strategy, is it a worthwhile stretch. It also sees any non-fatal rule flags (e.g. "onsite in a non-preferred location") as context.

Every evaluation — rule-based skip or LLM judgment — writes a row to `job_evaluations`. Re-scoring a job adds a new row rather than overwriting the old one, so you can compare results across profile edits, prompt edits, or model changes over time. A job only gets marked `scored` if an evaluation actually completed; failed OpenAI calls (bad/missing key, rate limit) are logged to `model_runs.error_message` and the job stays `sourced` so `python app.py score` retries it next time, without you losing the rest of the batch.

## Current state (Milestone 4)

- Sourcing (M2): `jobs/greenhouse.py`, `jobs/lever.py`, `jobs/ashby.py` return the same `NormalizedJob` shape; `jobs/fetch.py` handles fetch + dedup. Currently configured: Gusto, Rover, Patreon (~115 postings). Expanding to the full target list is Milestone 5.
- Scoring (M4): implemented and tested end-to-end for the rule-only path (confirmed real disqualifications fire correctly) and the failure path (confirmed a missing API key logs cleanly without crashing the batch). **Not yet verified against a live OpenAI call** — needs `OPENAI_API_KEY` + `OPENAI_MODEL` in `.env`.
- `positioning_profiles` (renamed from `candidate_profiles`) holds 5 seeded archetype rows (Senior PM, Platform PM, Marketplace PM, Product Operations, Chief of Staff) — a future resume/story routing layer, still not wired into scoring.
- `candidate_stories` is empty — populate it with real, honest examples of your work before scoring cites strong evidence; until then the AI is told explicitly not to fabricate evidence.
- No automated application submission exists anywhere in this project, and won't until you explicitly ask for it.
