import requests

from .normalize import NormalizedJob, guess_remote_type, parse_posted_at_epoch_ms

BASE_URL = "https://api.lever.co/v0/postings/{slug}"


def fetch_jobs(slug: str) -> list[NormalizedJob]:
    resp = requests.get(BASE_URL.format(slug=slug), params={"mode": "json"}, timeout=15)
    resp.raise_for_status()
    jobs = []
    for item in resp.json():
        categories = item.get("categories") or {}
        location = categories.get("location")
        jobs.append(
            NormalizedJob(
                source="lever",
                external_id=str(item["id"]),
                company=slug,
                title=item.get("text", ""),
                location=location,
                remote_type=guess_remote_type(location, item.get("workplaceType")),
                description=item.get("descriptionPlain", "") or "",
                salary_min=None,
                salary_max=None,
                url=item.get("hostedUrl", ""),
                posted_at=parse_posted_at_epoch_ms(item.get("createdAt")),
            )
        )
    return jobs
