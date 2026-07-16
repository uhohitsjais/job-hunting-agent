import requests

from .normalize import NormalizedJob, guess_remote_type, strip_html

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def fetch_jobs(slug: str) -> list[NormalizedJob]:
    resp = requests.get(BASE_URL.format(slug=slug), params={"content": "true"}, timeout=15)
    resp.raise_for_status()
    jobs = []
    for item in resp.json().get("jobs", []):
        location = (item.get("location") or {}).get("name")
        jobs.append(
            NormalizedJob(
                source="greenhouse",
                external_id=str(item["id"]),
                company=slug,
                title=item.get("title", ""),
                location=location,
                remote_type=guess_remote_type(location),
                description=strip_html(item.get("content")),
                salary_min=None,
                salary_max=None,
                url=item.get("absolute_url", ""),
            )
        )
    return jobs
