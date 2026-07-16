from __future__ import annotations

import html
import re
from dataclasses import dataclass


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


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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
