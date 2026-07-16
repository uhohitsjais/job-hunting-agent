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

from .context import build_candidate_context
from .rules import apply_deterministic_rules


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

    candidate_context = build_candidate_context(profile)

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
        input_context=json.dumps(metadata.input_context),
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


def evaluate_all(rescore: bool = False) -> dict:
    from db.db import fetch_all_jobs

    from providers.openai_provider import OpenAIProvider

    provider = OpenAIProvider()
    profile = get_candidate_profile(settings.DATABASE_PATH)
    stories = fetch_approved_candidate_stories(settings.DATABASE_PATH)

    if rescore:
        jobs = [dict(row) for row in fetch_all_jobs(settings.DATABASE_PATH)]
    else:
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
