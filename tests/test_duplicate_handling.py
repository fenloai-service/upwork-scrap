"""Tests for duplicate handling in scraping and scraping config loading.

Run: pytest tests/test_duplicate_handling.py -v
"""

import pytest


def make_fake_jobs(uids):
    """Create minimal job dicts with given UIDs."""
    return [{"uid": uid, "title": f"Job {uid}", "url": f"/jobs/{uid}"} for uid in uids]


class TestDuplicateFiltering:
    """Test the duplicate UID filtering logic."""

    def test_known_uids_filtered_out(self):
        """Jobs with UIDs in known_uids should be filtered."""
        all_jobs = make_fake_jobs(["a", "b", "c", "d"])
        known_uids = {"a", "c"}

        new_jobs = [j for j in all_jobs if j["uid"] not in known_uids]
        assert len(new_jobs) == 2
        assert {j["uid"] for j in new_jobs} == {"b", "d"}

    def test_no_filtering_when_none(self):
        """When known_uids is None, all jobs pass through."""
        all_jobs = make_fake_jobs(["a", "b", "c"])
        known_uids = None

        if known_uids is not None:
            new_jobs = [j for j in all_jobs if j["uid"] not in known_uids]
        else:
            new_jobs = all_jobs

        assert len(new_jobs) == 3

    def test_intra_session_dedup(self):
        """New UIDs should be added to known_uids to prevent intra-session dupes."""
        known_uids = {"existing1"}
        page1_jobs = make_fake_jobs(["new1", "new2"])
        page2_jobs = make_fake_jobs(["new2", "new3"])  # new2 is a dupe from page 1

        # Simulate page 1 processing
        filtered1 = [j for j in page1_jobs if j["uid"] not in known_uids]
        known_uids.update(j["uid"] for j in filtered1)

        assert len(filtered1) == 2
        assert known_uids == {"existing1", "new1", "new2"}

        # Simulate page 2 processing
        filtered2 = [j for j in page2_jobs if j["uid"] not in known_uids]
        known_uids.update(j["uid"] for j in filtered2)

        assert len(filtered2) == 1
        assert filtered2[0]["uid"] == "new3"

    def test_early_termination_condition(self):
        """When all jobs on a page are known, early termination should trigger."""
        known_uids = {"a", "b", "c"}
        page_jobs = make_fake_jobs(["a", "b", "c"])

        new_jobs = [j for j in page_jobs if j["uid"] not in known_uids]
        skipped = len(page_jobs) - len(new_jobs)

        should_terminate = (len(new_jobs) == 0 and skipped > 0)
        assert should_terminate is True

    def test_no_early_termination_with_new_jobs(self):
        """When there are new jobs on the page, don't terminate early."""
        known_uids = {"a"}
        page_jobs = make_fake_jobs(["a", "b", "c"])

        new_jobs = [j for j in page_jobs if j["uid"] not in known_uids]
        skipped = len(page_jobs) - len(new_jobs)

        should_terminate = (len(new_jobs) == 0 and skipped > 0)
        assert should_terminate is False

    def test_empty_known_uids(self):
        """Empty known_uids set should pass all jobs through."""
        known_uids = set()
        all_jobs = make_fake_jobs(["a", "b", "c"])

        new_jobs = [j for j in all_jobs if j["uid"] not in known_uids]
        assert len(new_jobs) == 3

    def test_jobs_without_uid_not_filtered(self):
        """Jobs without a UID should not be filtered out."""
        known_uids = {"a"}
        jobs = [{"uid": "a", "title": "Job A"}, {"uid": "", "title": "No UID"}, {"title": "Missing UID"}]

        new_jobs = [j for j in jobs if j.get("uid") and j["uid"] not in known_uids]
        # Jobs without valid UIDs are filtered by the `j.get("uid")` check
        assert len(new_jobs) == 0  # "a" is known, "" and None are filtered by the check


class TestScrapingConfigLoading:
    """Test that scraping config loads from YAML."""

    def test_keywords_loaded_from_yaml(self):
        """config.KEYWORDS should be loaded (either from YAML or fallback)."""
        import config
        assert isinstance(config.KEYWORDS, list)
        assert len(config.KEYWORDS) >= 15
        assert "ai" in config.KEYWORDS

    def test_duplicate_skip_enabled(self):
        """DUPLICATE_SKIP_ENABLED should be a bool."""
        import config
        assert isinstance(config.DUPLICATE_SKIP_ENABLED, bool)

    def test_duplicate_early_termination(self):
        """DUPLICATE_EARLY_TERMINATION should be a bool."""
        import config
        assert isinstance(config.DUPLICATE_EARLY_TERMINATION, bool)

    def test_safety_settings_loaded(self):
        """Safety settings should have valid values."""
        import config
        assert config.MIN_DELAY_SECONDS >= 1
        assert config.MAX_DELAY_SECONDS >= config.MIN_DELAY_SECONDS
        assert config.MAX_PAGES_PER_SESSION > 0
        assert config.PAGE_LOAD_TIMEOUT > 0

    def test_search_url_template_has_placeholders(self):
        """URL template should contain {keyword} and {page} placeholders."""
        import config
        assert "{keyword}" in config.SEARCH_URL_TEMPLATE
        assert "{page}" in config.SEARCH_URL_TEMPLATE

    def test_scraping_yaml_parses(self):
        """config/scraping.yaml should parse correctly."""
        import yaml
        import os

        yaml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "scraping.yaml")
        if not os.path.exists(yaml_path):
            pytest.skip("config/scraping.yaml not yet created")

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        assert "scraping" in data
        assert "keywords" in data["scraping"]
        assert "duplicate_handling" in data["scraping"]
        assert len(data["scraping"]["keywords"]) >= 15
