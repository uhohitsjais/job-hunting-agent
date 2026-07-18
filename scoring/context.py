from __future__ import annotations

from materials.career_brain import hash_career_brain_context, load_career_brain_context


def build_candidate_context(profile: dict) -> str:
    """Returns the LinkedIn/resume narrative context. Unchanged since Career
    Brain was added — kept as its own function so callers that intentionally
    want only this (none currently do) still can."""
    parts = []
    if profile.get("linkedin_text"):
        parts.append("LinkedIn profile:\n" + profile["linkedin_text"])
    if profile.get("resume_text"):
        parts.append("Resume:\n" + profile["resume_text"])
    if not parts:
        return "No LinkedIn profile or resume provided yet — do not fabricate work history."
    return "\n\n".join(parts)


def build_full_candidate_context(profile: dict) -> tuple[str, list[str], str]:
    """The one candidate_context builder used by both recommend_job
    (scoring/evaluate.py) and materials generation (web/server.py) — LinkedIn
    /resume (build_candidate_context, unchanged) with Career Brain
    (materials.career_brain.load_career_brain_context, unchanged loader)
    layered on top, never replacing it. Returns (combined_text,
    career_brain_doc_paths, career_brain_hash) — the paths/hash aren't part
    of what's sent to the model, they're for model_runs logging so any past
    evaluation or generation is reproducible."""
    base_context = build_candidate_context(profile)
    career_brain_text, career_brain_docs = load_career_brain_context()
    if not career_brain_text:
        return base_context, [], ""
    combined = (
        base_context
        + "\n\n---\n\nCareer Brain (long-term source of truth):\n\n"
        + career_brain_text
    )
    return combined, career_brain_docs, hash_career_brain_context(career_brain_text)
