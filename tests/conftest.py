"""Shared test fixtures for the upwork-scrap test suite."""

import sys
from unittest.mock import MagicMock

# Mock playwright before any test imports it
# This allows tests to run without having playwright installed
sys.modules['playwright'] = MagicMock()
sys.modules['playwright.async_api'] = MagicMock()

import sqlite3
import tempfile
import os

import pytest


@pytest.fixture(autouse=True)
def ensure_sqlite_backend(monkeypatch):
    """Ensure tests always use SQLite backend by clearing DATABASE_URL."""
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database with the jobs schema."""
    db_path = tmp_path / "test_jobs.db"
    conn = sqlite3.connect(str(db_path))
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
            first_seen_at TEXT,
            category TEXT DEFAULT '',
            category_confidence REAL DEFAULT 0,
            summary TEXT DEFAULT '',
            categories TEXT DEFAULT '',
            key_tools TEXT DEFAULT '',
            ai_summary TEXT DEFAULT '',
            match_score REAL DEFAULT NULL,
            match_reasons TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def sample_job():
    """Return a sample job dict for testing."""
    return {
        "uid": "test-123",
        "title": "Build AI Chatbot with LangChain",
        "url": "https://www.upwork.com/jobs/~test123",
        "posted_text": "2 hours ago",
        "description": "Need an AI chatbot built with LangChain and OpenAI.",
        "job_type": "Fixed price",
        "fixed_price": 500.0,
        "experience_level": "Intermediate",
        "skills": '["Python", "LangChain", "OpenAI"]',
        "keyword": "ai chatbot",
    }
