"""SQLite database for storing scraped Upwork jobs."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import config

log = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create the jobs and favorites tables if they don't exist."""
    conn = get_connection()
    try:
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

        # Favorites table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                job_uid TEXT PRIMARY KEY,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY(job_uid) REFERENCES jobs(uid)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_favorites_added ON favorites(added_at)
        """)

        conn.commit()
    finally:
        conn.close()


def upsert_jobs(jobs: list[dict]) -> tuple[int, int]:
    """Insert or update jobs. Returns (inserted_count, updated_count)."""
    conn = get_connection()
    inserted = 0
    updated = 0

    try:
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
    finally:
        conn.close()

    return inserted, updated


def get_all_jobs() -> list[dict]:
    """Get all jobs as a list of dicts."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM jobs ORDER BY posted_date_estimated DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_job_count() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    finally:
        conn.close()


def get_jobs_since(since_date: str) -> list[dict]:
    """Get jobs scraped since a given date (ISO format)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE scraped_at >= ? ORDER BY posted_date_estimated DESC",
            (since_date,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _to_float(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Favorites Management
# ══════════════════════════════════════════════════════════════════════════════

def add_favorite(job_uid: str, notes: str = "") -> bool:
    """Add a job to favorites. Returns True if added, False if already exists."""
    conn = get_connection()
    try:
        # Check if already favorited
        existing = conn.execute(
            "SELECT job_uid FROM favorites WHERE job_uid = ?", (job_uid,)
        ).fetchone()

        if existing:
            return False

        conn.execute(
            "INSERT INTO favorites (job_uid, notes) VALUES (?, ?)",
            (job_uid, notes)
        )
        conn.commit()
        log.info(f"Added job {job_uid} to favorites")
        return True
    except sqlite3.IntegrityError as e:
        log.warning(f"Failed to add favorite {job_uid}: {e}")
        return False
    finally:
        conn.close()


def remove_favorite(job_uid: str) -> bool:
    """Remove a job from favorites. Returns True if removed, False if not found."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM favorites WHERE job_uid = ?", (job_uid,)
        )
        conn.commit()
        removed = cursor.rowcount > 0
        if removed:
            log.info(f"Removed job {job_uid} from favorites")
        return removed
    finally:
        conn.close()


def get_favorites() -> list[dict]:
    """Get all favorited jobs with their full details."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                j.*,
                f.added_at as favorited_at,
                f.notes as favorite_notes
            FROM favorites f
            JOIN jobs j ON f.job_uid = j.uid
            ORDER BY f.added_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def is_favorite(job_uid: str) -> bool:
    """Check if a job is favorited."""
    conn = get_connection()
    try:
        result = conn.execute(
            "SELECT 1 FROM favorites WHERE job_uid = ?", (job_uid,)
        ).fetchone()
        return result is not None
    finally:
        conn.close()


def get_favorite_count() -> int:
    """Get total number of favorited jobs."""
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
    finally:
        conn.close()


def update_favorite_notes(job_uid: str, notes: str) -> bool:
    """Update notes for a favorited job."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE favorites SET notes = ? WHERE job_uid = ?",
            (notes, job_uid)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
