from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class NormalizedJob:
    """The shape every ATS connector must return. Everything past this point
    (scoring, materials, fill) operates only on NormalizedJob and never
    branches on `source`."""

    source: str
    external_id: str
    company: str
    title: str
    location: str | None
    remote_type: str | None  # remote | hybrid | onsite | unknown
    description: str
    salary_min: int | None
    salary_max: int | None
    url: str
    industry: str | None = None  # set by fetch.py from config/companies.yaml, not by connectors
    posted_at: str | None = None  # ISO8601 UTC, when the ATS says the job was posted


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_posted_at_iso(value: str | None) -> str | None:
    """ISO8601 string (Greenhouse first_published, Ashby publishedAt) ->
    normalized UTC ISO string. Never raises — a date we can't parse just
    means posted_at stays null, not a fetch failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def parse_posted_at_epoch_ms(value: int | None) -> str | None:
    """Epoch milliseconds (Lever createdAt) -> normalized UTC ISO string."""
    if not value:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def guess_remote_type(location: str | None, explicit: str | None = None) -> str:
    if explicit:
        explicit_lower = explicit.lower()
        if "remote" in explicit_lower:
            return "remote"
        if "hybrid" in explicit_lower:
            return "hybrid"
        if "onsite" in explicit_lower or "on-site" in explicit_lower:
            return "onsite"
    if location and "remote" in location.lower():
        return "remote"
    return "unknown"
