"""SQLite database for storing scraped Upwork jobs."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import config


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create the jobs table if it doesn't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            uid TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            posted_text TEXT,
            posted_date_estimated TEXT,
            description TEXT,
            job_type TEXT,
            hourly_rate_min REAL,
            hourly_rate_max REAL,
            fixed_price REAL,
            experience_level TEXT,
            est_time TEXT,
            skills TEXT,  -- JSON array
            proposals TEXT,
            client_country TEXT,
            client_total_spent TEXT,
            client_rating TEXT,
            client_info_raw TEXT,
            keyword TEXT,
            scraped_at TEXT,
            source_page INTEGER,
            first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_keyword ON jobs(keyword)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_date_estimated)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_scraped ON jobs(scraped_at)
    """)
    conn.commit()
    conn.close()


def upsert_jobs(jobs: list[dict]) -> tuple[int, int]:
    """Insert or update jobs. Returns (inserted_count, updated_count)."""
    conn = get_connection()
    inserted = 0
    updated = 0

    for job in jobs:
        uid = job.get("uid")
        if not uid:
            continue

        skills_json = json.dumps(job.get("skills", []))

        # Check if exists
        existing = conn.execute("SELECT uid FROM jobs WHERE uid = ?", (uid,)).fetchone()

        if existing:
            # Update — keep first_seen_at, update everything else
            conn.execute("""
                UPDATE jobs SET
                    title=?, url=?, posted_text=?, posted_date_estimated=?,
                    description=?, job_type=?, hourly_rate_min=?, hourly_rate_max=?,
                    fixed_price=?, experience_level=?, est_time=?, skills=?,
                    proposals=?, client_country=?, client_total_spent=?,
                    client_rating=?, client_info_raw=?, keyword=?,
                    scraped_at=?, source_page=?
                WHERE uid=?
            """, (
                job.get("title", ""),
                job.get("url", ""),
                job.get("posted_text", ""),
                job.get("posted_date_estimated", ""),
                job.get("description", ""),
                job.get("job_type", ""),
                _to_float(job.get("hourly_rate_min")),
                _to_float(job.get("hourly_rate_max")),
                _to_float(job.get("fixed_price")),
                job.get("experience_level", ""),
                job.get("est_time", ""),
                skills_json,
                job.get("proposals", ""),
                job.get("client_country", ""),
                job.get("client_total_spent", ""),
                job.get("client_rating", ""),
                job.get("client_info_raw", ""),
                job.get("keyword", ""),
                job.get("scraped_at", ""),
                job.get("source_page", 0),
                uid,
            ))
            updated += 1
        else:
            conn.execute("""
                INSERT INTO jobs (
                    uid, title, url, posted_text, posted_date_estimated,
                    description, job_type, hourly_rate_min, hourly_rate_max,
                    fixed_price, experience_level, est_time, skills,
                    proposals, client_country, client_total_spent,
                    client_rating, client_info_raw, keyword,
                    scraped_at, source_page
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uid,
                job.get("title", ""),
                job.get("url", ""),
                job.get("posted_text", ""),
                job.get("posted_date_estimated", ""),
                job.get("description", ""),
                job.get("job_type", ""),
                _to_float(job.get("hourly_rate_min")),
                _to_float(job.get("hourly_rate_max")),
                _to_float(job.get("fixed_price")),
                job.get("experience_level", ""),
                job.get("est_time", ""),
                skills_json,
                job.get("proposals", ""),
                job.get("client_country", ""),
                job.get("client_total_spent", ""),
                job.get("client_rating", ""),
                job.get("client_info_raw", ""),
                job.get("keyword", ""),
                job.get("scraped_at", ""),
                job.get("source_page", 0),
            ))
            inserted += 1

    conn.commit()
    conn.close()
    return inserted, updated


def get_all_jobs() -> list[dict]:
    """Get all jobs as a list of dicts."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM jobs ORDER BY posted_date_estimated DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_job_count() -> int:
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()
    return count


def get_jobs_since(since_date: str) -> list[dict]:
    """Get jobs scraped since a given date (ISO format)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE scraped_at >= ? ORDER BY posted_date_estimated DESC",
        (since_date,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _to_float(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None
