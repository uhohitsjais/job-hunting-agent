import requests

from .normalize import NormalizedJob, guess_remote_type, parse_posted_at_iso

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def fetch_jobs(slug: str) -> list[NormalizedJob]:
    resp = requests.get(BASE_URL.format(slug=slug), timeout=15)
    resp.raise_for_status()
    jobs = []
    for item in resp.json().get("jobs", []):
        location = item.get("location")
        jobs.append(
            NormalizedJob(
                source="ashby",
                external_id=str(item["id"]),
                company=slug,
                title=item.get("title", ""),
                location=location,
                remote_type=guess_remote_type(location, item.get("workplaceType")),
                description=item.get("descriptionPlain", "") or "",
                salary_min=None,
                salary_max=None,
                url=item.get("jobUrl", ""),
                posted_at=parse_posted_at_iso(item.get("publishedAt")),
            )
        )
    return jobs
