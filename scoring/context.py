from __future__ import annotations


def build_candidate_context(profile: dict) -> str:
    """Returns the narrative candidate context passed to the LLM alongside
    the structured profile fields. Today this is just LinkedIn + resume text
    pasted into /profile/import. If a richer "Career Brain" source of truth
    is built later, only this function changes — recommend_job and the
    materials-generation methods keep taking an opaque `candidate_context`
    string and don't need to know where it came from."""
    parts = []
    if profile.get("linkedin_text"):
        parts.append("LinkedIn profile:\n" + profile["linkedin_text"])
    if profile.get("resume_text"):
        parts.append("Resume:\n" + profile["resume_text"])
    if not parts:
        return "No LinkedIn profile or resume provided yet — do not fabricate work history."
    return "\n\n".join(parts)
