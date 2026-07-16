import hashlib
from datetime import datetime, timezone
from pathlib import Path

import yaml

from config import settings
from db.db import get_connection

from . import ashby, greenhouse, lever
from .normalize import NormalizedJob

COMPANIES_PATH = Path(__file__).resolve().parent.parent / "config" / "companies.yaml"

FETCHERS = {
    "greenhouse": greenhouse.fetch_jobs,
    "lever": lever.fetch_jobs,
    "ashby": ashby.fetch_jobs,
}


def load_companies() -> list[dict]:
    return yaml.safe_load(COMPANIES_PATH.read_text())["companies"]


def upsert_job(conn, job: NormalizedJob) -> None:
    jd_hash = hashlib.sha256(job.description.encode()).hexdigest()[:16]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO jobs (
            source, external_id, company, title, url, location, remote_type,
            salary_min, salary_max, industry, description, jd_hash, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, external_id) DO UPDATE SET
            title=excluded.title,
            url=excluded.url,
            location=excluded.location,
            remote_type=excluded.remote_type,
            salary_min=excluded.salary_min,
            salary_max=excluded.salary_max,
            industry=excluded.industry,
            description=excluded.description,
            jd_hash=excluded.jd_hash,
            updated_at=excluded.updated_at
        """,
        (
            job.source, job.external_id, job.company, job.title, job.url,
            job.location, job.remote_type, job.salary_min, job.salary_max,
            job.industry, job.description, jd_hash, now,
        ),
    )


def fetch_all() -> int:
    """Fetch every configured company's postings and upsert into `jobs`.
    Nothing downstream of this function should know or care which ATS a
    given job came from."""
    companies = load_companies()
    conn = get_connection(settings.DATABASE_PATH)
    total = 0
    try:
        for company in companies:
            fetcher = FETCHERS[company["ats"]]
            normalized_jobs = fetcher(company["slug"])
            for job in normalized_jobs:
                job.company = company["name"]
                job.industry = company.get("industry")
                upsert_job(conn, job)
                total += 1
        conn.commit()
    finally:
        conn.close()
    return total
