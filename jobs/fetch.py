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
            salary_min, salary_max, industry, description, jd_hash, posted_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            posted_at=excluded.posted_at,
            updated_at=excluded.updated_at,
            status=CASE WHEN status = 'delisted' THEN 'sourced' ELSE status END
        """,
        (
            job.source, job.external_id, job.company, job.title, job.url,
            job.location, job.remote_type, job.salary_min, job.salary_max,
            job.industry, job.description, jd_hash, job.posted_at, now,
        ),
    )


def mark_delisted_jobs(conn, source: str, company_name: str, current_external_ids: set) -> int:
    """A job that's no longer in this company's live feed is gone from the
    source ATS — mark it 'delisted' rather than deleting it, so it stays
    visible but clearly labeled as no longer applyable. Skips jobs already
    marked delisted (nothing to update)."""
    rows = conn.execute(
        "SELECT id, external_id FROM jobs WHERE source = ? AND company = ? AND status != 'delisted'",
        (source, company_name),
    ).fetchall()
    now = datetime.now(timezone.utc).isoformat()
    delisted = 0
    for row in rows:
        if row["external_id"] not in current_external_ids:
            conn.execute(
                "UPDATE jobs SET status = 'delisted', updated_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            delisted += 1
    return delisted


def fetch_all() -> dict:
    """Fetch every configured company's postings, upsert into `jobs`, and
    mark anything that's disappeared from a company's feed as 'delisted'.
    Nothing downstream of this function should know or care which ATS a
    given job came from."""
    companies = load_companies()
    conn = get_connection(settings.DATABASE_PATH)
    fetched = 0
    delisted = 0
    try:
        for company in companies:
            fetcher = FETCHERS[company["ats"]]
            normalized_jobs = fetcher(company["slug"])
            current_external_ids = set()
            for job in normalized_jobs:
                job.company = company["name"]
                job.industry = company.get("industry")
                upsert_job(conn, job)
                current_external_ids.add(job.external_id)
                fetched += 1
            delisted += mark_delisted_jobs(conn, company["ats"], company["name"], current_external_ids)
        conn.commit()
    finally:
        conn.close()
    return {"fetched": fetched, "delisted": delisted}
