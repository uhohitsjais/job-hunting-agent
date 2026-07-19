from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from scoring.title_filter import passes_title_filter

# Presentation-layer only: everything here derives from fields already
# stored in job_evaluations/model_runs, plus a read of Career Brain files
# purely to pull a title/tag list for display. No new LLM call, no schema
# change, no change to scoring/rules.py or providers/openai_provider.py.
# This means every already-scored job gets the improved view for free,
# immediately, with zero additional API cost.

REPO_ROOT = Path(__file__).resolve().parent.parent

TRANSFER_KEYWORDS = [
    "transfer", "maps to", "map well", "translat", "overlap", "leverage",
    "connect", "bridge", "cross-functional", "adjacent", "analogous",
    "comparable", "similar to",
]

TAG_SECTION_RE = re.compile(r"(?im)^#+\s*what this (?:proves|demonstrates)\s*$")

PROFILE_LIST_SIGNAL_FIELDS = [
    ("target_titles", "Target Titles"),
    ("strongest_skills", "Strongest Skills"),
    ("preferred_industries", "Preferred Industries"),
    ("known_gaps", "Known Gaps"),
]
PROFILE_SCALAR_SIGNAL_FIELDS = [
    ("years_experience", "Years of Experience"),
    ("remote_preference", "Remote Preference"),
    ("stretch_willingness", "Stretch Willingness"),
]

FILTER_KEYWORDS = {
    "Salary": ["salary"],
    "Location": ["remote", "onsite", "hybrid", "location"],
    "Industry": ["industry"],
}


def humanize_posted_at(posted_at: str | None) -> str:
    """'Today' / '1 day ago' / '3 days ago' / '2 weeks ago' etc, instead of
    a raw date — same underlying posted_at value, just friendlier."""
    if not posted_at:
        return "—"
    try:
        posted = datetime.fromisoformat(posted_at)
    except ValueError:
        return "—"

    days = (datetime.now(timezone.utc) - posted).days
    if days <= 0:
        return "Today"
    if days == 1:
        return "1 day ago"
    if days < 7:
        return f"{days} days ago"
    weeks = days // 7
    if weeks == 1:
        return "1 week ago"
    if days < 30:
        return f"{weeks} weeks ago"
    months = days // 30
    if months == 1:
        return "1 month ago"
    return f"{months} months ago"


def _split_sentences(text: str | None) -> list[str]:
    if not text:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def extract_executive_summary(evaluation: dict) -> str:
    """First sentence of positioning_strategy. In practice the existing
    prompt already tends to lead with a decisive framing statement ("Do
    not spend an application on this role." / "Position herself as...") —
    this just surfaces that sentence rather than asking the model for a
    new field."""
    sentences = _split_sentences(evaluation.get("positioning_strategy"))
    if sentences:
        return sentences[0]
    return "No positioning detail available for this evaluation."


def extract_transferable_experience(evaluation: dict) -> list[str]:
    """Heuristic keyword extraction from positioning_strategy + reasons_to_apply
    — not a distinct model output. A dedicated LLM field would be cleaner,
    but that means re-scoring, which is out of scope for a
    presentation-only milestone."""
    candidates = []
    for sentence in _split_sentences(evaluation.get("positioning_strategy"))[1:]:
        if any(kw in sentence.lower() for kw in TRANSFER_KEYWORDS):
            candidates.append(sentence)
    for reason in evaluation.get("reasons_to_apply") or []:
        if any(kw in reason.lower() for kw in TRANSFER_KEYWORDS) and reason not in candidates:
            candidates.append(reason)
    return candidates[:3]


def _read_career_brain_file(relative_path: str) -> str | None:
    path = REPO_ROOT / relative_path
    if not path.is_file():
        return None
    try:
        return path.read_text()
    except (OSError, UnicodeDecodeError):
        return None


def get_career_brain_doc_title(relative_path: str) -> str:
    """First H1 heading in the file — that's the clean display name Jais
    already wrote for each doc. Falls back to a prettified filename if the
    file has since been renamed/replaced (career_brain/ docs get swapped
    for fuller drafts over time) or is otherwise unreadable."""
    content = _read_career_brain_file(relative_path)
    if content:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
    stem = Path(relative_path).stem
    stem = re.sub(r"^[A-Za-z0-9]+-", "", stem, count=1) if re.match(r"^[A-Z]\d{3}-", stem) else stem
    return stem.replace("-", " ").replace("_", " ").title()


def parse_career_brain_tags(relative_path: str) -> list[str]:
    """Pulls the bullet list under a '# What This Demonstrates' / '# What
    this proves' heading, if present — Jais's own self-authored domain/
    skill tags for that story, not model-generated."""
    content = _read_career_brain_file(relative_path)
    if not content:
        return []
    tags = []
    in_section = False
    for line in content.splitlines():
        if TAG_SECTION_RE.match(line):
            in_section = True
            continue
        if in_section:
            stripped = line.strip()
            if stripped.startswith("#") or stripped == "---":
                break
            if stripped.startswith("- "):
                tags.append(stripped[2:].strip())
    return tags


def build_career_brain_evidence(career_brain_docs: list[str]) -> list[dict]:
    """Friendly doc names for display — never the raw markdown body."""
    return [{"path": doc, "title": get_career_brain_doc_title(doc)} for doc in career_brain_docs]


def build_strongest_matching_experience(career_brain_docs: list[str], limit: int = 10) -> list[str]:
    """'What This Demonstrates' tags from every Career Brain doc actually
    used in this evaluation — Jais's own self-authored domain/skill labels,
    not fabricated here. Ranked by how many of the used docs each tag
    appears in (a tag repeating across several of her stories is more
    corroborated than one that shows up once), capped so this stays a
    short, useful signal instead of dumping every tag from every doc."""
    counts: dict[str, int] = {}
    first_seen_order: list[str] = []
    for doc in career_brain_docs:
        for tag in set(parse_career_brain_tags(doc)):
            if tag not in counts:
                first_seen_order.append(tag)
            counts[tag] = counts.get(tag, 0) + 1
    ranked = sorted(first_seen_order, key=lambda t: -counts[t])
    return ranked[:limit]


def build_profile_signals(profile: dict, evaluation: dict) -> list[str]:
    """Deterministic keyword-echo check: which structured profile fields'
    content shows up (as a substring) in the evaluation's own text. Every
    non-empty profile field is always sent to the model in full (see
    prompts/recommendation.md), so this can't tell you what was included
    in the input — every field always is. It's a proxy for which fields'
    content is reflected in the model's actual output, based on the
    CURRENT profile (no historical profile snapshot is stored per
    evaluation, so older evaluations are compared against today's
    profile, not the one live when they ran)."""
    haystack = " ".join(
        (evaluation.get("reasons_to_apply") or [])
        + (evaluation.get("gaps") or [])
        + (evaluation.get("disqualifiers") or [])
        + [evaluation.get("positioning_strategy") or ""]
    ).lower()

    signals = []
    for field, label in PROFILE_LIST_SIGNAL_FIELDS:
        values = profile.get(field) or []
        if any(v.strip() and v.lower() in haystack for v in values):
            signals.append(label)
    for field, label in PROFILE_SCALAR_SIGNAL_FIELDS:
        value = profile.get(field)
        if value and str(value).lower() in haystack:
            signals.append(label)
    return signals


def build_deterministic_filter_summary(
    evaluation: dict, profile: dict, deterministic_flags: list[str]
) -> dict:
    """What the deterministic layer (title filter + rules) actually did
    for this job. Title match is recomputed live (cheap, no LLM, no
    side effects) since a job's scored state doesn't guarantee `filter`
    was run first — score no longer runs it automatically. Salary/
    Location/Industry status comes from reading the already-stored
    disqualifiers (rule-based archive) or deterministic_flags (non-fatal,
    passed to the LLM) for the relevant keyword."""
    rule_archived = (evaluation.get("positioning_strategy") or "").startswith(
        "Disqualified by rule-based screening"
    )
    notes = " ".join(
        (evaluation.get("disqualifiers") or []) + (deterministic_flags or [])
    ).lower()

    title_ok = passes_title_filter(evaluation.get("title", ""), profile)
    results = {"Title Match": "passed" if title_ok else "would fail with your current profile"}

    configured = {
        "Salary": bool(profile.get("min_salary")),
        "Location": bool(profile.get("remote_preference")),
        "Industry": bool(profile.get("excluded_industries")),
    }
    for name, keywords in FILTER_KEYWORDS.items():
        if not configured[name]:
            results[name] = "not configured"
        elif any(kw in notes for kw in keywords):
            results[name] = "failed" if rule_archived else "flagged (non-fatal)"
        else:
            results[name] = "passed"

    any_triggered = any(v in ("failed", "flagged (non-fatal)") for v in results.values())
    return {"results": results, "any_triggered": any_triggered}


def build_recommendation_view(
    evaluation: dict, profile: dict | None = None, model_run: dict | None = None
) -> dict:
    """Everything the job detail template needs — derived entirely from
    already-stored job_evaluations/model_runs fields plus a read of
    Career Brain file headers/tags for display names. No confidence
    field, deliberately: an earlier version inferred High/Medium/Low from
    evidence counts, but that's an engineering heuristic, not something
    the model actually said — it produced unintuitive results and user
    testing rejected it immediately. Fit score is the primary
    quantitative signal."""
    if not evaluation.get("decision"):
        return {"has_evaluation": False}

    profile = profile or {}
    input_context: dict = {}
    if model_run and model_run.get("input_context"):
        try:
            input_context = json.loads(model_run["input_context"])
        except (json.JSONDecodeError, TypeError):
            input_context = {}
    career_brain_docs = input_context.get("career_brain_docs") or []
    deterministic_flags = input_context.get("deterministic_flags") or []

    return {
        "has_evaluation": True,
        "decision": evaluation["decision"],
        "score": evaluation.get("score"),
        "executive_summary": extract_executive_summary(evaluation),
        "top_strengths": (evaluation.get("reasons_to_apply") or [])[:5],
        "top_gaps": (evaluation.get("gaps") or [])[:3],
        "transferable_experience": extract_transferable_experience(evaluation),
        "positioning_strategy": evaluation.get("positioning_strategy"),
        "disqualifiers": evaluation.get("disqualifiers") or [],
        "strongest_matching_experience": build_strongest_matching_experience(career_brain_docs),
        "career_brain_evidence": build_career_brain_evidence(career_brain_docs),
        "profile_signals": build_profile_signals(profile, evaluation),
        "deterministic_filters": build_deterministic_filter_summary(
            evaluation, profile, deterministic_flags
        ),
    }
