from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RuleResult:
    passed: bool
    disqualifiers: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)  # non-fatal, passed to the LLM as context


def apply_deterministic_rules(job: dict, profile: dict) -> RuleResult:
    """Objective checks only — salary, location/remote fit, excluded
    industries. Anything requiring judgment (is this a worthwhile stretch,
    how to position gaps) is left to the LLM in scoring/evaluate.py."""
    disqualifiers: list[str] = []
    flags: list[str] = []

    min_salary = profile.get("min_salary")
    salary_max = job.get("salary_max")
    salary_min = job.get("salary_min")
    if min_salary:
        if salary_max is not None and salary_max < min_salary:
            disqualifiers.append(
                f"Posted salary max (${salary_max:,}) is below your minimum (${min_salary:,})"
            )
        elif salary_max is None and salary_min is not None and salary_min < min_salary:
            flags.append(
                f"Posted salary min (${salary_min:,}) is below your minimum (${min_salary:,}) — confirm before investing time"
            )

    remote_pref = profile.get("remote_preference")
    remote_type = job.get("remote_type") or "unknown"
    location = job.get("location") or ""
    preferred_locations = profile.get("preferred_locations") or []

    if remote_pref == "remote_only" and remote_type in ("hybrid", "onsite"):
        disqualifiers.append(f"Requires {remote_type} work, but you're remote-only")
    elif remote_pref in ("remote_only", "hybrid_ok") and remote_type == "onsite":
        if preferred_locations and not any(
            loc.lower() in location.lower() for loc in preferred_locations
        ):
            flags.append(
                f"Onsite in {location or 'an unlisted location'}, not one of your preferred locations"
            )

    excluded_industries = [i.lower() for i in (profile.get("excluded_industries") or [])]
    job_industry = (job.get("industry") or "").lower()
    if job_industry and job_industry in excluded_industries:
        disqualifiers.append(f"Industry '{job['industry']}' is on your excluded list")

    return RuleResult(passed=not disqualifiers, disqualifiers=disqualifiers, flags=flags)
