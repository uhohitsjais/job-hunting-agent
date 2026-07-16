from __future__ import annotations


def passes_title_filter(title: str, profile: dict) -> bool:
    """Deterministic, keyword/substring based — no LLM, no semantic
    matching. Excluded titles take precedence over target titles. If no
    target titles are configured, nothing is filtered out by title (a
    blank profile shouldn't silently archive everything)."""
    title_lower = (title or "").lower()

    excluded_titles = [t.lower() for t in (profile.get("excluded_titles") or []) if t.strip()]
    if any(excluded in title_lower for excluded in excluded_titles):
        return False

    target_titles = [t.lower() for t in (profile.get("target_titles") or []) if t.strip()]
    if not target_titles:
        return True

    return any(target in title_lower for target in target_titles)
