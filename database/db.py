"""Database for storing scraped Upwork jobs (SQLite or PostgreSQL).

Backend is selected automatically:
- PostgreSQL when DATABASE_URL environment variable is set
- SQLite (default) when DATABASE_URL is not set
"""

import json
import logging
import sqlite3
from datetime import datetime, date

import config
from database.adapter import get_connection, is_postgres

# Import error classes for both backends (psycopg2 may not be installed)
_INTEGRITY_ERRORS = (sqlite3.IntegrityError,)
_OPERATIONAL_ERRORS = (sqlite3.OperationalError,)

try:
    import psycopg2

    _INTEGRITY_ERRORS = _INTEGRITY_ERRORS + (psycopg2.IntegrityError,)
    _OPERATIONAL_ERRORS = _OPERATIONAL_ERRORS + (psycopg2.OperationalError,)
except ImportError:
    pass

log = logging.getLogger(__name__)


def _rows_to_dicts(rows: list) -> list[dict]:
    """Convert database rows to plain dicts for safe downstream use."""
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# Schema Initialization
# ══════════════════════════════════════════════════════════════════════════════


def init_db():
    """Create the jobs, favorites, and proposals tables if they don't exist."""
    if is_postgres():
        _init_db_postgres()
    else:
        _init_db_sqlite()


def _init_db_sqlite():
    """SQLite schema initialization (with ALTER TABLE for column upgrades)."""
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
                skills TEXT,
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_keyword ON jobs(keyword)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_date_estimated)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_scraped ON jobs(scraped_at)"
        )

        # Add classification columns if they don't exist
        _alter_columns = [
            ("category", "TEXT DEFAULT ''"),
            ("category_confidence", "REAL DEFAULT 0.0"),
            ("summary", "TEXT DEFAULT ''"),
            ("categories", "TEXT DEFAULT ''"),
            ("key_tools", "TEXT DEFAULT ''"),
            ("ai_summary", "TEXT DEFAULT ''"),
        ]
        for col_name, col_def in _alter_columns:
            try:
                conn.execute(
                    f"ALTER TABLE jobs ADD COLUMN {col_name} {col_def}"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Favorites table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                job_uid TEXT PRIMARY KEY,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY(job_uid) REFERENCES jobs(uid)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_favorites_added ON favorites(added_at)"
        )

        # Proposals table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_uid TEXT NOT NULL,
                proposal_text TEXT NOT NULL,
                edited_text TEXT DEFAULT '',
                user_edited INTEGER DEFAULT 0,
                match_score REAL DEFAULT 0.0,
                match_reasons TEXT DEFAULT '',
                status TEXT DEFAULT 'pending_review',
                failure_reason TEXT DEFAULT '',
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT DEFAULT '',
                submitted_at TEXT DEFAULT '',
                email_sent_at TEXT DEFAULT '',
                user_notes TEXT DEFAULT '',
                FOREIGN KEY(job_uid) REFERENCES jobs(uid) ON DELETE CASCADE
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposals_job_uid ON proposals(job_uid)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposals_generated ON proposals(generated_at)"
        )

        # Add user_rating column if it doesn't exist
        try:
            conn.execute(
                "ALTER TABLE proposals ADD COLUMN user_rating INTEGER DEFAULT NULL"
            )
        except sqlite3.OperationalError:
            pass

        conn.commit()
    finally:
        conn.close()


def _init_db_postgres():
    """PostgreSQL schema initialization (all columns from the start)."""
    conn = get_connection()
    try:
        # Jobs table — all columns included upfront
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                uid TEXT PRIMARY KEY,
                title TEXT,
                url TEXT,
                posted_text TEXT,
                posted_date_estimated TEXT,
                description TEXT,
                job_type TEXT,
                hourly_rate_min DOUBLE PRECISION,
                hourly_rate_max DOUBLE PRECISION,
                fixed_price DOUBLE PRECISION,
                experience_level TEXT,
                est_time TEXT,
                skills TEXT,
                proposals TEXT,
                client_country TEXT,
                client_total_spent TEXT,
                client_rating TEXT,
                client_info_raw TEXT,
                keyword TEXT,
                scraped_at TEXT,
                source_page INTEGER,
                first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
                category TEXT DEFAULT '',
                category_confidence DOUBLE PRECISION DEFAULT 0.0,
                summary TEXT DEFAULT '',
                categories TEXT DEFAULT '',
                key_tools TEXT DEFAULT '',
                ai_summary TEXT DEFAULT ''
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_keyword ON jobs(keyword)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_date_estimated)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_scraped ON jobs(scraped_at)"
        )

        # Favorites table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                job_uid TEXT PRIMARY KEY REFERENCES jobs(uid),
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_favorites_added ON favorites(added_at)"
        )

        # Proposals table — SERIAL instead of AUTOINCREMENT
        conn.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id SERIAL PRIMARY KEY,
                job_uid TEXT NOT NULL REFERENCES jobs(uid) ON DELETE CASCADE,
                proposal_text TEXT NOT NULL,
                edited_text TEXT DEFAULT '',
                user_edited INTEGER DEFAULT 0,
                match_score DOUBLE PRECISION DEFAULT 0.0,
                match_reasons TEXT DEFAULT '',
                status TEXT DEFAULT 'pending_review',
                failure_reason TEXT DEFAULT '',
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT DEFAULT '',
                submitted_at TEXT DEFAULT '',
                email_sent_at TEXT DEFAULT '',
                user_notes TEXT DEFAULT '',
                user_rating INTEGER DEFAULT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposals_job_uid ON proposals(job_uid)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposals_generated ON proposals(generated_at)"
        )

        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Jobs CRUD
# ══════════════════════════════════════════════════════════════════════════════


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
            existing = conn.execute(
                "SELECT uid FROM jobs WHERE uid = ?", (uid,)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE jobs SET
                        title=?, url=?, posted_text=?, posted_date_estimated=?,
                        description=?, job_type=?, hourly_rate_min=?, hourly_rate_max=?,
                        fixed_price=?, experience_level=?, est_time=?, skills=?,
                        proposals=?, client_country=?, client_total_spent=?,
                        client_rating=?, client_info_raw=?, keyword=?,
                        scraped_at=?, source_page=?
                    WHERE uid=?
                """,
                    (
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
                    ),
                )
                updated += 1
            else:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        uid, title, url, posted_text, posted_date_estimated,
                        description, job_type, hourly_rate_min, hourly_rate_max,
                        fixed_price, experience_level, est_time, skills,
                        proposals, client_country, client_total_spent,
                        client_rating, client_info_raw, keyword,
                        scraped_at, source_page
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
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
                    ),
                )
                inserted += 1

        conn.commit()
    finally:
        conn.close()

    return inserted, updated


def get_all_jobs() -> list[dict]:
    """Get all jobs as a list of dicts."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY posted_date_estimated DESC"
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def get_job_by_uid(uid: str) -> dict | None:
    """Get a single job by its UID. Returns dict or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM jobs WHERE uid = ?", (uid,)
        ).fetchone()
        return dict(row) if row else None
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
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def get_all_job_uids() -> set[str]:
    """Get all job UIDs from the database. Returns a set of UIDs."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT uid FROM jobs").fetchall()
        return {row["uid"] for row in rows}
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
# Classification Helpers (used by classifier/ai.py and classifier/rules.py)
# ══════════════════════════════════════════════════════════════════════════════


def get_unclassified_jobs() -> list[dict]:
    """Get jobs that haven't been AI-classified yet.

    Returns list of dicts with uid, title, description, skills.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT uid, title, description, skills FROM jobs "
            "WHERE ai_summary = '' OR ai_summary IS NULL"
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def get_all_jobs_for_classification() -> list[dict]:
    """Get all jobs for rule-based classification.

    Returns list of dicts with uid, title, description, skills.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT uid, title, description, skills FROM jobs"
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def update_job_classifications(results: list[dict]) -> int:
    """Batch update AI classification fields for jobs.

    Args:
        results: List of dicts with uid, categories (list), key_tools (list), ai_summary (str).

    Returns:
        Number of jobs updated.
    """
    conn = get_connection()
    count = 0
    try:
        for r in results:
            uid = r.get("uid")
            if not uid:
                continue
            categories = json.dumps(r.get("categories", []))
            key_tools = json.dumps(r.get("key_tools", []))
            ai_summary = r.get("ai_summary", "")
            conn.execute(
                "UPDATE jobs SET categories=?, key_tools=?, ai_summary=? WHERE uid=?",
                (categories, key_tools, ai_summary, uid),
            )
            count += 1
        conn.commit()
    finally:
        conn.close()
    return count


def update_job_category(uid: str, category: str, confidence: float) -> None:
    """Update rule-based classification for a single job."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE jobs SET category = ?, category_confidence = ? WHERE uid = ?",
            (category, confidence, uid),
        )
        conn.commit()
    finally:
        conn.close()


def update_job_categories_batch(updates: list[tuple]) -> None:
    """Batch update rule-based category/confidence for multiple jobs.

    Args:
        updates: List of (category, confidence, uid) tuples.
    """
    conn = get_connection()
    try:
        for category, confidence, uid in updates:
            conn.execute(
                "UPDATE jobs SET category = ?, category_confidence = ? WHERE uid = ?",
                (category, confidence, uid),
            )
        conn.commit()
    finally:
        conn.close()


def get_classification_status() -> tuple[int, int]:
    """Get classification progress.

    Returns:
        (total_jobs, classified_jobs) tuple.
    """
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        classified = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE ai_summary != '' AND ai_summary IS NOT NULL"
        ).fetchone()[0]
        return total, classified
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Proposals Helpers
# ══════════════════════════════════════════════════════════════════════════════


def get_proposals_generated_today() -> int:
    """Count proposals generated today (calendar day)."""
    conn = get_connection()
    try:
        today = date.today().isoformat()
        # Use LIKE for cross-database compatibility (works on both SQLite and PostgreSQL)
        result = conn.execute(
            "SELECT COUNT(*) as count FROM proposals WHERE generated_at LIKE ?",
            (today + "%",),
        ).fetchone()
        return result["count"] if result else 0
    finally:
        conn.close()


def get_pending_proposals_with_jobs() -> list[dict]:
    """Get pending proposals with full job details (for email sending).

    Returns list of dicts with proposal and job fields.
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                p.job_uid,
                p.proposal_text,
                p.match_score,
                p.status,
                j.title,
                j.url,
                j.description,
                j.hourly_rate_min,
                j.hourly_rate_max,
                j.fixed_price,
                j.skills
            FROM proposals p
            JOIN jobs j ON p.job_uid = j.uid
            WHERE p.status = 'pending_review'
            ORDER BY p.match_score DESC
        """).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Favorites Management
# ══════════════════════════════════════════════════════════════════════════════


def add_favorite(job_uid: str, notes: str = "") -> bool:
    """Add a job to favorites. Returns True if added, False if already exists."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT job_uid FROM favorites WHERE job_uid = ?", (job_uid,)
        ).fetchone()

        if existing:
            return False

        conn.execute(
            "INSERT INTO favorites (job_uid, notes) VALUES (?, ?)",
            (job_uid, notes),
        )
        conn.commit()
        log.info(f"Added job {job_uid} to favorites")
        return True
    except _INTEGRITY_ERRORS as e:
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
        return _rows_to_dicts(rows)
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
            "UPDATE favorites SET notes = ? WHERE job_uid = ?", (notes, job_uid)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Proposals Management
# ══════════════════════════════════════════════════════════════════════════════


def insert_proposal(
    job_uid: str,
    proposal_text: str,
    match_score: float = 0.0,
    match_reasons: str = "",
    status: str = "pending_review",
) -> int:
    """Insert a new proposal. Returns the proposal ID."""
    conn = get_connection()
    try:
        if is_postgres():
            cursor = conn.execute(
                """
                INSERT INTO proposals (
                    job_uid, proposal_text, match_score, match_reasons, status
                ) VALUES (?, ?, ?, ?, ?)
                RETURNING id
            """,
                (job_uid, proposal_text, match_score, match_reasons, status),
            )
            row = cursor.fetchone()
            proposal_id = row["id"] if row else None
        else:
            cursor = conn.execute(
                """
                INSERT INTO proposals (
                    job_uid, proposal_text, match_score, match_reasons, status
                ) VALUES (?, ?, ?, ?, ?)
            """,
                (job_uid, proposal_text, match_score, match_reasons, status),
            )
            proposal_id = cursor.lastrowid

        conn.commit()
        log.info(f"Inserted proposal {proposal_id} for job {job_uid}")
        return proposal_id
    finally:
        conn.close()


def get_proposals(status: str = None, limit: int = None) -> list[dict]:
    """Get proposals, optionally filtered by status."""
    conn = get_connection()
    try:
        query = """
            SELECT
                p.*,
                j.title as job_title,
                j.url as job_url,
                j.job_type,
                j.hourly_rate_min,
                j.hourly_rate_max,
                j.fixed_price,
                j.client_rating,
                j.client_country,
                j.description as job_description,
                j.skills as job_skills,
                j.posted_date_estimated
            FROM proposals p
            JOIN jobs j ON p.job_uid = j.uid
        """

        params = []
        if status:
            query += " WHERE p.status = ?"
            params.append(status)

        query += " ORDER BY p.generated_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def update_proposal_status(
    proposal_id: int, status: str, failure_reason: str = ""
) -> bool:
    """Update proposal status. Returns True if updated."""
    conn = get_connection()
    try:
        timestamp_col = ""
        timestamp_val = datetime.now().isoformat()

        if status == "approved":
            timestamp_col = ", reviewed_at = ?"
        elif status == "submitted":
            timestamp_col = ", submitted_at = ?"

        query = f"UPDATE proposals SET status = ?, failure_reason = ?{timestamp_col} WHERE id = ?"
        params = [status, failure_reason]
        if timestamp_col:
            params.append(timestamp_val)
        params.append(proposal_id)

        cursor = conn.execute(query, params)
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            log.info(f"Updated proposal {proposal_id} status to {status}")
        return updated
    finally:
        conn.close()


def update_proposal_text(proposal_id: int, edited_text: str) -> bool:
    """Update proposal text. Marks user_edited=1. Returns True if updated."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE proposals
            SET edited_text = ?, user_edited = 1
            WHERE id = ?
        """,
            (edited_text, proposal_id),
        )
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            log.info(f"Updated proposal {proposal_id} text (user edited)")
        return updated
    finally:
        conn.close()


def get_proposal_stats() -> dict:
    """Get proposal statistics. Returns dict with counts by status."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM proposals
            GROUP BY status
        """).fetchall()

        stats = {row["status"]: row["count"] for row in rows}

        total = conn.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]
        stats["total"] = total

        return stats
    finally:
        conn.close()


def update_proposal_rating(job_uid: str, rating: int) -> bool:
    """Update user rating for a proposal (1-5 stars)."""
    if rating is not None and (rating < 1 or rating > 5):
        raise ValueError("Rating must be between 1 and 5")

    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE proposals SET user_rating = ? WHERE job_uid = ?",
            (rating, job_uid),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_proposal_analytics() -> dict:
    """Get proposal quality analytics including acceptance rate and ratings."""
    conn = get_connection()
    try:
        # Get counts by status
        status_rows = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM proposals
            GROUP BY status
        """).fetchall()

        status_counts = {row["status"]: row["count"] for row in status_rows}
        total = sum(status_counts.values())

        approved = status_counts.get("approved", 0)
        submitted = status_counts.get("submitted", 0)
        acceptance_rate = (
            ((approved + submitted) / total * 100) if total > 0 else 0
        )

        # Get average match score
        avg_match_result = conn.execute(
            "SELECT AVG(match_score) as avg FROM proposals"
        ).fetchone()
        avg_match_score = (
            avg_match_result["avg"] if avg_match_result["avg"] else 0
        )

        # Get average rating
        avg_rating_result = conn.execute(
            "SELECT AVG(user_rating) as avg FROM proposals WHERE user_rating IS NOT NULL"
        ).fetchone()
        avg_rating = (
            avg_rating_result["avg"] if avg_rating_result["avg"] else None
        )

        # Get rating distribution
        rating_rows = conn.execute("""
            SELECT user_rating, COUNT(*) as count
            FROM proposals
            WHERE user_rating IS NOT NULL
            GROUP BY user_rating
            ORDER BY user_rating
        """).fetchall()
        rating_distribution = {
            row["user_rating"]: row["count"] for row in rating_rows
        }

        return {
            "total_proposals": total,
            "pending_review": status_counts.get("pending_review", 0),
            "approved": approved,
            "submitted": submitted,
            "rejected": status_counts.get("rejected", 0),
            "failed": status_counts.get("failed", 0),
            "acceptance_rate": round(acceptance_rate, 1),
            "avg_match_score": round(avg_match_score, 1),
            "avg_rating": round(avg_rating, 2) if avg_rating else None,
            "rating_distribution": rating_distribution,
            "proposals_by_status": [
                {"status": row["status"], "count": row["count"]}
                for row in status_rows
            ],
        }
    finally:
        conn.close()


def proposal_exists(job_uid: str) -> bool:
    """Check if a proposal already exists for a job."""
    conn = get_connection()
    try:
        result = conn.execute(
            "SELECT 1 FROM proposals WHERE job_uid = ? LIMIT 1", (job_uid,)
        ).fetchone()
        return result is not None
    finally:
        conn.close()
