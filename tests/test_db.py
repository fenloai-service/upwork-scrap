"""Tests for database/db.py — the core persistence layer."""

import pytest

from database.db import init_db, upsert_jobs, get_all_jobs, get_job_count, get_jobs_since, _to_float


@pytest.fixture
def db_setup(tmp_path, monkeypatch):
    """Point config.DB_PATH to a temp file and init the schema."""
    import config
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    init_db()
    return db_path


def _make_job(uid="~test1", **overrides):
    """Build a minimal job dict with sensible defaults."""
    job = {
        "uid": uid,
        "title": "Build AI Chatbot",
        "url": f"https://www.upwork.com/jobs/{uid}",
        "posted_text": "2 hours ago",
        "posted_date_estimated": "2026-02-11",
        "description": "Need an AI chatbot.",
        "job_type": "Fixed price",
        "hourly_rate_min": None,
        "hourly_rate_max": None,
        "fixed_price": 500.0,
        "experience_level": "Intermediate",
        "est_time": "1-3 months",
        "skills": ["Python", "LangChain"],
        "proposals": "5 to 10",
        "client_country": "United States",
        "client_total_spent": "$10K+",
        "client_rating": "4.9",
        "client_info_raw": "Payment method verified",
        "keyword": "ai chatbot",
        "scraped_at": "2026-02-11T10:00:00",
        "source_page": 1,
    }
    job.update(overrides)
    return job


class TestUpsertJobs:
    def test_insert_new_job(self, db_setup):
        inserted, updated = upsert_jobs([_make_job()])
        assert inserted == 1
        assert updated == 0
        assert get_job_count() == 1

    def test_update_existing_job(self, db_setup):
        upsert_jobs([_make_job()])
        inserted, updated = upsert_jobs([_make_job(title="Updated Title")])
        assert inserted == 0
        assert updated == 1
        assert get_job_count() == 1

        jobs = get_all_jobs()
        assert jobs[0]["title"] == "Updated Title"

    def test_upsert_preserves_first_seen_at(self, db_setup):
        upsert_jobs([_make_job()])
        jobs_before = get_all_jobs()
        first_seen = jobs_before[0]["first_seen_at"]

        upsert_jobs([_make_job(title="Changed")])
        jobs_after = get_all_jobs()
        assert jobs_after[0]["first_seen_at"] == first_seen

    def test_skip_job_without_uid(self, db_setup):
        inserted, updated = upsert_jobs([{"title": "No UID"}])
        assert inserted == 0
        assert updated == 0
        assert get_job_count() == 0

    def test_multiple_jobs(self, db_setup):
        jobs = [_make_job(uid=f"~test{i}") for i in range(5)]
        inserted, updated = upsert_jobs(jobs)
        assert inserted == 5
        assert updated == 0
        assert get_job_count() == 5


class TestGetJobs:
    def test_get_all_jobs_empty(self, db_setup):
        assert get_all_jobs() == []

    def test_get_all_jobs_returns_dicts(self, db_setup):
        upsert_jobs([_make_job()])
        jobs = get_all_jobs()
        assert isinstance(jobs, list)
        assert isinstance(jobs[0], dict)
        assert jobs[0]["uid"] == "~test1"

    def test_get_jobs_since_filters(self, db_setup):
        upsert_jobs([
            _make_job(uid="~old", scraped_at="2026-01-01T00:00:00"),
            _make_job(uid="~new", scraped_at="2026-02-10T00:00:00"),
        ])
        recent = get_jobs_since("2026-02-01")
        assert len(recent) == 1
        assert recent[0]["uid"] == "~new"


class TestToFloat:
    def test_normal_float(self):
        assert _to_float(42.5) == 42.5

    def test_string_number(self):
        assert _to_float("100") == 100.0

    def test_comma_separated(self):
        assert _to_float("1,500") == 1500.0

    def test_none_returns_none(self):
        assert _to_float(None) is None

    def test_empty_string_returns_none(self):
        assert _to_float("") is None

    def test_garbage_returns_none(self):
        assert _to_float("not a number") is None
