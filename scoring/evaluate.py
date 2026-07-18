from __future__ import annotations

import json

from config import settings
from db.db import (
    fetch_approved_candidate_stories,
    fetch_jobs_by_status,
    get_candidate_profile,
    get_connection,
    insert_job_evaluation,
    insert_model_run,
    mark_job_status,
)

from .context import build_full_candidate_context
from .rules import apply_deterministic_rules
from .title_filter import passes_title_filter


def apply_title_filter() -> dict:
    """Deterministic pre-filter, runs before any LLM call — no exceptions.
    Moves currently-'sourced' jobs that fail the title filter to
    'filtered_title'. Idempotent: only touches jobs still in 'sourced', so
    re-running never re-filters an already-scored or already-filtered job.

    This is its own explicit pipeline stage (`python app.py filter`, or the
    dashboard's "Run Title Filter" button) — evaluate_all() no longer calls
    it automatically. The intended workflow is fetch -> filter -> (review) ->
    score, with control over each stage."""
    profile = get_candidate_profile(settings.DATABASE_PATH)
    jobs = fetch_jobs_by_status(settings.DATABASE_PATH, "sourced")

    conn = get_connection(settings.DATABASE_PATH)
    filtered = 0
    eligible = 0
    try:
        for job in jobs:
            if passes_title_filter(job["title"], profile):
                eligible += 1
            else:
                mark_job_status(conn, job["id"], "filtered_title")
                filtered += 1
        conn.commit()
    finally:
        conn.close()
    return {"filtered": filtered, "eligible": eligible}


def evaluate_job(conn, job: dict, profile: dict, stories: list[dict], provider) -> str:
    """Runs one job through rules, then the LLM if it passes. Always writes a
    job_evaluations row and marks the job 'scored' — even a rule-based
    archive is a real evaluation, not a non-event. The job stays visible
    either way; 'archive' is a grouping, not a rejection. Returns the
    decision string."""
    rule_result = apply_deterministic_rules(job, profile)

    if not rule_result.passed:
        insert_job_evaluation(
            conn,
            job_id=job["id"],
            positioning_profile_id=None,
            model_run_id=None,
            score=0,
            decision="archive",
            reasons_to_apply=[],
            gaps=[],
            disqualifiers=rule_result.disqualifiers,
            positioning_strategy="Disqualified by rule-based screening before reaching AI review.",
            evidence_story_ids=[],
        )
        mark_job_status(conn, job["id"], "scored")
        return "archive"

    candidate_context, career_brain_docs, career_brain_hash = build_full_candidate_context(profile)

    try:
        result, metadata = provider.recommend_job(
            job, profile, candidate_context, stories, rule_result.flags
        )
    except Exception as exc:
        insert_model_run(
            conn,
            task_type="recommend_job",
            job_id=job["id"],
            prompt_file="recommendation.md",
            prompt_version="unknown",
            model_name=getattr(provider, "model_name", "unknown"),
            input_context=None,
            raw_output=None,
            parsed_output=None,
            success=0,
            error_message=str(exc),
        )
        # Job stays 'sourced' so it's retried on the next `score` run once
        # whatever failed (e.g. missing API key) is fixed. One bad call
        # shouldn't abort evaluating the rest of the batch.
        return "error"

    model_run_id = insert_model_run(
        conn,
        task_type="recommend_job",
        job_id=job["id"],
        prompt_file=metadata.prompt_file,
        prompt_version=metadata.prompt_version,
        model_name=metadata.model_name,
        input_context=json.dumps(
            {
                **metadata.input_context,
                "career_brain_docs": career_brain_docs,
                "career_brain_hash": career_brain_hash,
            }
        ),
        raw_output=metadata.raw_output,
        parsed_output=json.dumps(
            {
                "score": result.score,
                "decision": result.decision,
                "reasons_to_apply": result.reasons_to_apply,
                "gaps": result.gaps,
                "disqualifiers": result.disqualifiers,
                "positioning_strategy": result.positioning_strategy,
                "evidence_story_ids": result.evidence_story_ids,
            }
        ),
        success=1,
        error_message=None,
    )

    insert_job_evaluation(
        conn,
        job_id=job["id"],
        positioning_profile_id=None,
        model_run_id=model_run_id,
        score=result.score,
        decision=result.decision,
        reasons_to_apply=result.reasons_to_apply,
        gaps=result.gaps,
        disqualifiers=result.disqualifiers,
        positioning_strategy=result.positioning_strategy,
        evidence_story_ids=result.evidence_story_ids,
    )
    mark_job_status(conn, job["id"], "scored")
    return result.decision


def evaluate_all(rescore: bool = False, job_id: int | None = None) -> dict:
    from db.db import fetch_all_jobs, fetch_job_by_id

    from providers.openai_provider import OpenAIProvider

    provider = OpenAIProvider()
    profile = get_candidate_profile(settings.DATABASE_PATH)
    stories = fetch_approved_candidate_stories(settings.DATABASE_PATH)

    if job_id is not None:
        # Targeted single-job (re)score — bypasses the status filter
        # entirely, for verifying a specific change (e.g. new Career Brain
        # content) without touching the rest of the database.
        job = fetch_job_by_id(settings.DATABASE_PATH, job_id)
        jobs = [job] if job else []
    elif rescore:
        # --rescore redoes LLM judgment, not the deterministic title gate —
        # jobs already filtered_title stay excluded. Run `python app.py
        # filter` separately first if you want the gate reconsidered too.
        all_jobs = [dict(row) for row in fetch_all_jobs(settings.DATABASE_PATH)]
        jobs = [job for job in all_jobs if job["status"] != "filtered_title"]
    else:
        # Only jobs already past the title filter (still 'sourced' means
        # eligible here — anything that failed the filter is
        # 'filtered_title' by the time this runs, assuming `filter` was run
        # first). If you skip the filter step, everything 'sourced' gets
        # scored, same as before this feature existed.
        jobs = fetch_jobs_by_status(settings.DATABASE_PATH, "sourced")

    conn = get_connection(settings.DATABASE_PATH)
    counts: dict[str, int] = {}
    try:
        for job in jobs:
            decision = evaluate_job(conn, job, profile, stories, provider)
            counts[decision] = counts.get(decision, 0) + 1
            conn.commit()
    finally:
        conn.close()
    return counts
