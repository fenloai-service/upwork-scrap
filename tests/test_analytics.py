"""Tests for dashboard.analytics module."""

import json
from datetime import date

import pandas as pd
import pytest

from dashboard.analytics import (
    daily_volume,
    hourly_rate_stats,
    jobs_to_dataframe,
    skill_frequency,
)


def _make_job(
    uid="~job1",
    title="Job 1",
    job_type="Hourly",
    hourly_rate_min=30.0,
    hourly_rate_max=50.0,
    fixed_price=None,
    experience_level="Intermediate",
    skills='["Python", "AI"]',
    keyword="python ai",
    posted_date_estimated="2025-01-15 10:00:00",
    scraped_at="2025-01-15 12:00:00",
    **overrides,
):
    """Helper to build a job dict with sensible defaults."""
    job = {
        "uid": uid,
        "title": title,
        "url": f"https://example.com/{uid}",
        "posted_text": "2 hours ago",
        "posted_date_estimated": posted_date_estimated,
        "description": "description placeholder",
        "job_type": job_type,
        "hourly_rate_min": hourly_rate_min,
        "hourly_rate_max": hourly_rate_max,
        "fixed_price": fixed_price,
        "experience_level": experience_level,
        "est_time": "1-3 months",
        "skills": skills,
        "proposals": "5-10",
        "client_country": "US",
        "client_total_spent": "$10k+",
        "client_rating": "4.9",
        "client_info_raw": "",
        "keyword": keyword,
        "scraped_at": scraped_at,
        "source_page": 1,
        "first_seen_at": scraped_at,
        "category": "AI",
        "category_confidence": 0.9,
        "summary": "",
        "categories": "",
        "key_tools": "",
        "ai_summary": "",
    }
    job.update(overrides)
    return job


class TestJobsToDataframe:
    def test_jobs_to_dataframe_parses_skills(self):
        """skills JSON string should be parsed into a Python list in skills_list column."""
        jobs = [
            _make_job(uid="~a", skills='["Python", "LangChain"]'),
            _make_job(uid="~b", skills='["React", "TypeScript", "Node.js"]'),
        ]

        df = jobs_to_dataframe(jobs)

        assert "skills_list" in df.columns
        assert df.loc[df["uid"] == "~a", "skills_list"].iloc[0] == [
            "Python",
            "LangChain",
        ]
        assert df.loc[df["uid"] == "~b", "skills_list"].iloc[0] == [
            "React",
            "TypeScript",
            "Node.js",
        ]

    def test_jobs_to_dataframe_empty_input(self):
        """An empty list should produce an empty DataFrame."""
        df = jobs_to_dataframe([])

        assert isinstance(df, pd.DataFrame)
        assert df.empty


class TestSkillFrequency:
    def test_skill_frequency_counts_correctly(self):
        """Skill counts should be accurate and ordered most-common first."""
        jobs = [
            _make_job(uid="~1", skills='["Python", "AI"]'),
            _make_job(uid="~2", skills='["Python", "LangChain"]'),
            _make_job(uid="~3", skills='["Python", "AI", "LangChain"]'),
        ]
        df = jobs_to_dataframe(jobs)

        result = skill_frequency(df)

        assert list(result.columns) == ["skill", "count"]

        # Python appears in all 3 jobs
        python_row = result[result["skill"] == "Python"]
        assert python_row["count"].iloc[0] == 3

        # AI appears in 2 jobs
        ai_row = result[result["skill"] == "AI"]
        assert ai_row["count"].iloc[0] == 2

        # LangChain appears in 2 jobs
        lc_row = result[result["skill"] == "LangChain"]
        assert lc_row["count"].iloc[0] == 2

        # Most common skill is first
        assert result.iloc[0]["skill"] == "Python"
        assert result.iloc[0]["count"] == 3


class TestHourlyRateStats:
    def test_hourly_rate_stats_with_data(self):
        """Stats should be computed correctly from hourly job rates."""
        jobs = [
            _make_job(uid="~h1", job_type="Hourly", hourly_rate_min=20.0, hourly_rate_max=40.0),
            _make_job(uid="~h2", job_type="Hourly", hourly_rate_min=30.0, hourly_rate_max=60.0),
            _make_job(uid="~h3", job_type="Hourly", hourly_rate_min=40.0, hourly_rate_max=80.0),
        ]
        df = jobs_to_dataframe(jobs)

        stats = hourly_rate_stats(df)

        assert stats["count"] == 3
        assert stats["min_rate_avg"] == pytest.approx(30.0)   # (20+30+40)/3
        assert stats["max_rate_avg"] == pytest.approx(60.0)   # (40+60+80)/3
        assert stats["min_rate_median"] == pytest.approx(30.0)
        assert stats["max_rate_median"] == pytest.approx(60.0)
        assert stats["min_rate_min"] == pytest.approx(20.0)
        assert stats["max_rate_max"] == pytest.approx(80.0)

    def test_hourly_rate_stats_no_hourly_jobs(self):
        """When all jobs are Fixed, hourly stats should return count 0."""
        jobs = [
            _make_job(
                uid="~f1",
                job_type="Fixed",
                hourly_rate_min=None,
                hourly_rate_max=None,
                fixed_price=500.0,
            ),
            _make_job(
                uid="~f2",
                job_type="Fixed",
                hourly_rate_min=None,
                hourly_rate_max=None,
                fixed_price=1000.0,
            ),
        ]
        df = jobs_to_dataframe(jobs)

        stats = hourly_rate_stats(df)

        assert stats == {"count": 0}


class TestDailyVolume:
    def test_daily_volume_groups_by_date(self):
        """Jobs should be grouped and counted by their posted date."""
        jobs = [
            _make_job(uid="~d1", posted_date_estimated="2025-01-15 08:00:00"),
            _make_job(uid="~d2", posted_date_estimated="2025-01-15 14:00:00"),
            _make_job(uid="~d3", posted_date_estimated="2025-01-16 10:00:00"),
            _make_job(uid="~d4", posted_date_estimated="2025-01-17 09:00:00"),
            _make_job(uid="~d5", posted_date_estimated="2025-01-17 18:00:00"),
            _make_job(uid="~d6", posted_date_estimated="2025-01-17 23:00:00"),
        ]
        df = jobs_to_dataframe(jobs)

        result = daily_volume(df)

        assert list(result.columns) == ["date", "count"]
        assert len(result) == 3

        # Rows are sorted by date
        counts = dict(zip(result["date"].astype(str), result["count"]))
        assert counts["2025-01-15"] == 2
        assert counts["2025-01-16"] == 1
        assert counts["2025-01-17"] == 3
