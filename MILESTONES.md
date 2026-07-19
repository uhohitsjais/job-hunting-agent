# Job Hunting Agent — 48-Hour MVP Milestone Plan

Goal: smallest working tool that finds PM jobs from Greenhouse/Lever/Ashby, scores fit, drafts tailored materials into your branded templates, opens + fills the application, and lets you review before submit. Human-gated, no auto-submit, no invented qualifications.

Stack: Python + SQLite + Flask + Playwright. OpenAI Responses API for all candidate-facing scoring/writing, behind a provider interface. Rule: **app stays runnable after every checkpoint.**

One thing still needed from you: your branded DOCX resume/cover-letter templates (needed for M8 — DOCX injection). Everything else that was originally blocked has been resolved: the candidate profile is now a structured `/profile` page (no narrative doc needed), and Career Brain (`career_brain/`) has replaced the assumption that LinkedIn/resume text alone would be enough context.

| # | Milestone | Status |
|---|-----------|--------|
| M1 | Runnable skeleton + SQLite schema | ✅ Done |
| M2 | Fetch real jobs from 3 test companies | ✅ Done (Gusto/Greenhouse, Rover/Lever, Patreon/Ashby) |
| M3 | Basic web dashboard | ✅ Done, byproduct of M1+M2 |
| M4 | Hybrid recommendation engine | ✅ Done, verified against live OpenAI calls. Structured `/profile` (no narrative doc needed) is the source of truth; deterministic rules run first, LLM judgment second; decisions are `priority/apply/stretch/archive` — nothing is ever hidden, only grouped |
| M5 | Expand sourcing to 10–15 companies | ✅ Done — 17 companies configured, 562 jobs sourced, 92 scored so far |
| M6 | Job detail page | ✅ Done (`/jobs/<id>` — score, reasons, gaps, positioning strategy, executive summary) |
| M7 | Draft resume content + cover letter | ✅ Done — plain-text resume summary + cover letter generation, reviewable/editable on the job detail page |
| M8 | Inject into branded DOCX templates | ⏸️ Not started. **Blocked on:** your branded DOCX templates. Materials generation (M7) currently outputs plain text, no branded formatting yet |
| M9 | Review queue | ⏸️ Not built as a dedicated dashboard view. In practice, review happens directly on the job detail page (edit resume summary/cover letter inline, regenerate) — revisit only if that stops being enough |
| M10 | Playwright fill — Greenhouse | ✅ Done — `python app.py fill <job_id>` opens a real browser, fills contact info + LinkedIn + cover letter, always leaves résumé upload and work-authorization/demographic questions for manual completion, never submits |
| M11 | Lever/Ashby fill | ✅ Done — `python app.py fill <job_id>` now dispatches by ATS automatically. Same rules as Greenhouse (never touches résumé/work-auth/demographic questions, never submits). Ashby has no cover-letter text option (file upload only); Lever's standard form has no cover-letter field at all |
| M12 | Hardening + operating guide | ⏸️ Not started |

## Milestones added beyond the original plan

| Milestone | Status |
|-----------|--------|
| Deterministic title pre-filter | ✅ Done — case-insensitive substring match on target/excluded titles, runs before any LLM call, its own explicit pipeline stage (`fetch → filter → score`) |
| Recommendation Quality V1 (presentation) | ✅ Done — top strengths, gaps, transferable experience, positioning strategy, executive summary, all derived from existing evaluation data, no new LLM calls. Confidence heuristic added then removed after user testing showed it was untrustworthy |
| Career Brain V0.1 | ✅ Done — `career_brain/{profile,stories,evidence,preferences}/` markdown folders, read fresh at generation time, no database/embeddings/vector search. Feeds both materials generation and recommendation scoring, layered on top of (not replacing) LinkedIn/resume context. 10 real documents added so far (gitignored — contains real names, recommendation quotes, internal business data) |

## Rules that hold across every milestone
- Never auto-click Submit. Ever.
- Never invent candidate experience, metrics, or qualifications not in your source materials.
- Pause on sensitive fields (salary expectations, sponsorship, demographic/legal/attestation questions) for manual input.
- One provider file (`providers/base.py`) is the only thing scoring/materials code talks to.
- SQLite is the single source of truth — no Google Sheets sync in this MVP.
