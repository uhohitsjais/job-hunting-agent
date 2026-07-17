from __future__ import annotations

import re

# Presentation-layer only: everything here derives from fields already
# stored in job_evaluations. No new LLM call, no schema change, no change
# to scoring/rules.py or providers/openai_provider.py. This means every
# already-scored job gets the improved view for free, immediately.

TRANSFER_KEYWORDS = [
    "transfer", "maps to", "map well", "translat", "overlap", "leverage",
    "connect", "bridge", "cross-functional", "adjacent", "analogous",
    "comparable", "similar to",
]


def _split_sentences(text: str | None) -> list[str]:
    if not text:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def compute_confidence(evaluation: dict) -> str:
    """Heuristic derived from the *net balance* of evidence already in the
    stored evaluation — NOT a model-reported confidence (the model was
    never asked for one, and this milestone doesn't add that ask). Rule-
    based disqualifications are always 'High' since they're deterministic,
    not a judgment call.

    Deliberately net-based rather than raw-count-based: a thorough,
    honest gap analysis (several gaps noted) alongside strong evidence
    shouldn't read as 'low confidence' just because the gap list is long —
    what matters is whether strengths clearly outweigh gaps, are roughly
    balanced, or are clearly outweighed by them."""
    if evaluation.get("disqualifiers"):
        return "High"
    reasons_count = len(evaluation.get("reasons_to_apply") or [])
    gaps_count = len(evaluation.get("gaps") or [])
    if reasons_count == 0 and gaps_count == 0:
        return "Low"
    net = reasons_count - gaps_count
    if net >= 2:
        return "High"
    if net <= -2:
        return "Low"
    return "Medium"


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


def build_recommendation_view(evaluation: dict) -> dict:
    """Everything the templates need for Recommendation Quality V1 —
    derived entirely from already-stored job_evaluations fields."""
    if not evaluation.get("decision"):
        return {"has_evaluation": False}
    return {
        "has_evaluation": True,
        "decision": evaluation["decision"],
        "score": evaluation.get("score"),
        "confidence": compute_confidence(evaluation),
        "executive_summary": extract_executive_summary(evaluation),
        "top_strengths": (evaluation.get("reasons_to_apply") or [])[:5],
        "top_gaps": (evaluation.get("gaps") or [])[:3],
        "transferable_experience": extract_transferable_experience(evaluation),
        "positioning_strategy": evaluation.get("positioning_strategy"),
        "disqualifiers": evaluation.get("disqualifiers") or [],
    }
