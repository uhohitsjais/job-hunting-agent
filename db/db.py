from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

PROFILE_ARRAY_FIELDS = [
    "target_titles",
    "excluded_titles",
    "preferred_industries",
    "excluded_industries",
    "preferred_locations",
    "strongest_skills",
    "known_gaps",
    "preferred_company_size",
]

DECISION_GROUPS = ["priority", "apply", "stretch", "archive", "unscored", "filtered_title"]

# Lightweight ALTER TABLE migrations for columns added after a table's first
# CREATE. `CREATE TABLE IF NOT EXISTS` won't add new columns to an existing
# table, so new columns need an explicit ALTER here too. Safe to re-run —
# duplicate-column errors are caught and ignored.
MIGRATIONS = [
    "ALTER TABLE candidate_profile ADD COLUMN excluded_titles TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE applications ADD COLUMN career_brain_docs TEXT",
]


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text())
        for statement in MIGRATIONS:
            try:
                conn.execute(statement)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc):
                    raise
        conn.commit()
    finally:
        conn.close()


def count_rows(db_path: str, table: str) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
        return row["n"]
    finally:
        conn.close()


def fetch_all_jobs(db_path: str) -> list[sqlite3.Row]:
    conn = get_connection(db_path)
    try:
        return conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    finally:
        conn.close()


def fetch_job_by_id(db_path: str, job_id: int) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fetch_jobs_with_latest_evaluation(db_path: str) -> list[dict]:
    """One row per job, joined to its most recent job_evaluations row (if
    any). Scored jobs sort best-first; unscored jobs sort newest-first at
    the bottom."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT jobs.*, je.score, je.decision, je.positioning_strategy,
                   je.reasons_to_apply, je.gaps, je.disqualifiers, je.created_at AS evaluated_at
            FROM jobs
            LEFT JOIN (
                SELECT je1.*
                FROM job_evaluations je1
                JOIN (
                    SELECT job_id, MAX(id) AS max_id FROM job_evaluations GROUP BY job_id
                ) latest ON je1.job_id = latest.job_id AND je1.id = latest.max_id
            ) je ON je.job_id = jobs.id
            ORDER BY (je.score IS NULL) ASC, je.score DESC, jobs.created_at DESC
            """
        ).fetchall()
        jobs = []
        for row in rows:
            job = dict(row)
            for field in ("reasons_to_apply", "gaps", "disqualifiers"):
                job[field] = json.loads(job[field]) if job[field] else []
            jobs.append(job)
        return jobs
    finally:
        conn.close()


def group_jobs_by_decision(jobs: list[dict]) -> dict:
    """Every job stays visible — this just buckets the flat list from
    fetch_jobs_with_latest_evaluation for section display. Nothing is
    dropped: jobs filtered out by the deterministic title pre-filter get
    their own 'filtered_title' group (they were never sent to the LLM, so
    they have no `decision`), separate from 'unscored' (eligible, just
    hasn't been scored yet)."""
    groups: dict[str, list[dict]] = {key: [] for key in DECISION_GROUPS}
    for job in jobs:
        if job.get("status") == "filtered_title":
            key = "filtered_title"
        else:
            key = job.get("decision") or "unscored"
        groups.setdefault(key, []).append(job)
    return groups


def get_pipeline_stats(db_path: str) -> dict:
    conn = get_connection(db_path)
    try:
        def count(where: str = "") -> int:
            return conn.execute(f"SELECT COUNT(*) AS n FROM jobs {where}").fetchone()["n"]

        return {
            "total": count(),
            "filtered": count("WHERE status = 'filtered_title'"),
            "eligible": count("WHERE status = 'sourced'"),
            "scored": count("WHERE status = 'scored'"),
        }
    finally:
        conn.close()


def fetch_job_with_latest_evaluation(db_path: str, job_id: int) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT jobs.*, je.score, je.decision, je.positioning_strategy,
                   je.reasons_to_apply, je.gaps, je.disqualifiers, je.evidence_story_ids,
                   je.created_at AS evaluated_at
            FROM jobs
            LEFT JOIN (
                SELECT je1.*
                FROM job_evaluations je1
                JOIN (
                    SELECT job_id, MAX(id) AS max_id FROM job_evaluations GROUP BY job_id
                ) latest ON je1.job_id = latest.job_id AND je1.id = latest.max_id
            ) je ON je.job_id = jobs.id
            WHERE jobs.id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        job = dict(row)
        for field in ("reasons_to_apply", "gaps", "disqualifiers", "evidence_story_ids"):
            job[field] = json.loads(job[field]) if job[field] else []
        return job
    finally:
        conn.close()


def get_application(db_path: str, job_id: int) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM applications WHERE job_id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_application(db_path: str, job_id: int, **fields) -> None:
    conn = get_connection(db_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        existing = conn.execute(
            "SELECT id FROM applications WHERE job_id = ?", (job_id,)
        ).fetchone()
        payload = dict(fields)
        payload["updated_at"] = now
        if existing:
            set_clause = ", ".join(f"{key} = ?" for key in payload)
            conn.execute(
                f"UPDATE applications SET {set_clause} WHERE job_id = ?",
                [*payload.values(), job_id],
            )
        else:
            payload["job_id"] = job_id
            columns = list(payload.keys())
            placeholders = ", ".join("?" for _ in columns)
            conn.execute(
                f"INSERT INTO applications ({', '.join(columns)}) VALUES ({placeholders})",
                [payload[c] for c in columns],
            )
        conn.commit()
    finally:
        conn.close()


def fetch_jobs_by_status(db_path: str, status: str) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM jobs WHERE status = ?", (status,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def mark_job_status(conn: sqlite3.Connection, job_id: int, status: str) -> None:
    conn.execute(
        "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now(timezone.utc).isoformat(), job_id),
    )


def get_candidate_profile(db_path: str) -> dict:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM candidate_profile WHERE id = 1").fetchone()
        profile = dict(row)
        for field in PROFILE_ARRAY_FIELDS:
            profile[field] = json.loads(profile[field] or "[]")
        return profile
    finally:
        conn.close()


def update_candidate_profile(db_path: str, values: dict) -> None:
    conn = get_connection(db_path)
    try:
        payload = dict(values)
        for field in PROFILE_ARRAY_FIELDS:
            if field in payload:
                payload[field] = json.dumps(payload[field])
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{key} = ?" for key in payload)
        conn.execute(
            f"UPDATE candidate_profile SET {set_clause} WHERE id = 1",
            list(payload.values()),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_approved_candidate_stories(db_path: str) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM candidate_stories WHERE approved = 1"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def insert_model_run(conn: sqlite3.Connection, **fields) -> int:
    columns = list(fields.keys())
    placeholders = ", ".join("?" for _ in columns)
    cursor = conn.execute(
        f"INSERT INTO model_runs ({', '.join(columns)}) VALUES ({placeholders})",
        [fields[c] for c in columns],
    )
    return cursor.lastrowid


def insert_job_evaluation(conn: sqlite3.Connection, **fields) -> int:
    payload = dict(fields)
    for field in ("reasons_to_apply", "gaps", "disqualifiers", "evidence_story_ids"):
        if field in payload and not isinstance(payload[field], str):
            payload[field] = json.dumps(payload[field])
    columns = list(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    cursor = conn.execute(
        f"INSERT INTO job_evaluations ({', '.join(columns)}) VALUES ({placeholders})",
        [payload[c] for c in columns],
    )
    return cursor.lastrowid
