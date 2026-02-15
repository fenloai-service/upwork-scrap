"""Tests for the api_usage_tracker module."""

import pytest
import api_usage_tracker


@pytest.fixture
def tracker_db(tmp_path, monkeypatch):
    """Point api_usage_tracker at a temporary database."""
    db_path = tmp_path / "test_api_usage.db"
    monkeypatch.setattr(api_usage_tracker, "USAGE_DB", db_path)
    api_usage_tracker.init_usage_db()
    return db_path


def test_record_and_retrieve_usage(tracker_db):
    """Record usage entries and verify get_tokens_used_today returns the correct sum."""
    api_usage_tracker.record_usage("groq", "llama-3-70b", 1500)
    api_usage_tracker.record_usage("groq", "llama-3-70b", 2500)
    api_usage_tracker.record_usage("groq", "mixtral-8x7b", 1000)

    total = api_usage_tracker.get_tokens_used_today("groq")
    assert total == 5000


def test_tokens_zero_with_no_usage(tracker_db):
    """On a fresh database, get_tokens_used_today returns 0."""
    total = api_usage_tracker.get_tokens_used_today("groq")
    assert total == 0


def test_check_daily_limit_under_threshold(tracker_db):
    """Record 50000 tokens against a 100000 limit -- well under the 80% warning threshold."""
    api_usage_tracker.record_usage("groq", "llama-3-70b", 50000)

    result = api_usage_tracker.check_daily_limit("groq", limit=100000)

    assert result["can_proceed"] is True
    assert result["warning"] is False
    assert result["exceeded"] is False
    assert result["used"] == 50000
    assert result["remaining"] == 50000
    assert result["percentage"] == pytest.approx(50.0)


def test_check_daily_limit_warning(tracker_db):
    """Record 85000 tokens (>80% of 100000) -- triggers warning but not exceeded."""
    api_usage_tracker.record_usage("groq", "llama-3-70b", 85000)

    result = api_usage_tracker.check_daily_limit("groq", limit=100000)

    assert result["warning"] is True
    assert result["exceeded"] is False
    assert result["can_proceed"] is True
    assert result["used"] == 85000
    assert result["remaining"] == 15000
    assert result["percentage"] == pytest.approx(85.0)


def test_check_daily_limit_exceeded(tracker_db):
    """Record 110000 tokens against a 100000 limit -- exceeded, cannot proceed."""
    api_usage_tracker.record_usage("groq", "llama-3-70b", 110000)

    result = api_usage_tracker.check_daily_limit("groq", limit=100000)

    assert result["exceeded"] is True
    assert result["can_proceed"] is False
    assert result["used"] == 110000
    assert result["remaining"] == 0
    assert result["percentage"] == pytest.approx(110.0)
