"""Tests for scraper/search.py — URL building and date estimation."""

import re
from datetime import datetime, timedelta
from unittest.mock import patch

from scraper.search import build_search_url, estimate_date


class TestBuildSearchUrl:
    def test_basic_keyword(self):
        url = build_search_url("ai", 1)
        assert "q=ai" in url
        assert "page=1" in url
        assert "upwork.com" in url

    def test_keyword_with_spaces(self):
        url = build_search_url("machine learning", 1)
        assert "q=machine+learning" in url

    def test_page_number(self):
        url = build_search_url("ai", 5)
        assert "page=5" in url

    def test_special_characters_encoded(self):
        url = build_search_url("C++ AI", 1)
        assert "C%2B%2B" in url


class TestEstimateDate:
    def test_just_now(self):
        result = estimate_date("just now")
        today = datetime.now().strftime("%Y-%m-%d")
        assert result.startswith(today)

    def test_minutes_ago(self):
        result = estimate_date("Posted 30 minutes ago")
        today = datetime.now().strftime("%Y-%m-%d")
        assert result.startswith(today)

    def test_hours_ago(self):
        result = estimate_date("Posted 2 hours ago")
        today = datetime.now().strftime("%Y-%m-%d")
        assert result.startswith(today)

    def test_days_ago(self):
        result = estimate_date("Posted 3 days ago")
        expected = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        assert result == expected

    def test_weeks_ago(self):
        result = estimate_date("Posted 2 weeks ago")
        expected = (datetime.now() - timedelta(weeks=2)).strftime("%Y-%m-%d")
        assert result == expected

    def test_months_ago(self):
        result = estimate_date("Posted 1 month ago")
        expected = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        assert result == expected

    def test_yesterday(self):
        result = estimate_date("yesterday")
        expected = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected

    def test_unparseable_returns_raw(self):
        result = estimate_date("some weird text")
        assert result == "some weird text"

    def test_empty_string(self):
        result = estimate_date("")
        assert result == ""
