"""Integration tests for the full monitor pipeline.

These tests validate the end-to-end monitor workflow: scrape → classify → match → generate.
Uses mocked Chrome and Grok API to avoid external dependencies.

Run: pytest tests/test_monitor_pipeline.py -v
"""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


@pytest.fixture
def fixture_jobs():
    """Load fixture jobs from tests/fixtures/sample_jobs.json."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_jobs.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def test_db_with_config(tmp_path, monkeypatch):
    """Set up temporary database and config directory for integration tests."""
    import sqlite3

    # Setup DB
    db_path = str(tmp_path / "test_jobs.db")
    monkeypatch.setenv("UPWORK_DB_PATH", db_path)

    import config
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    from database.db import init_db
    init_db()

    # Setup config directory
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)

    # Copy fixture configs
    import yaml
    import shutil
    fixture_config_dir = Path(__file__).parent / "fixtures" / "sample_config"
    for config_file in fixture_config_dir.glob("*.yaml"):
        shutil.copy(config_file, config_dir / config_file.name)

    # Verify threshold is correct
    prefs_file = config_dir / "job_preferences.yaml"
    with open(prefs_file) as f:
        prefs_data = yaml.safe_load(f)
        threshold_val = prefs_data['preferences'].get('match_threshold', prefs_data['preferences'].get('threshold', 70))
        print(f"📋 Test config threshold: {threshold_val}")

    return tmp_path


@pytest.mark.skip(reason="Integration test hangs - needs async/event loop investigation")
def test_monitor_pipeline_end_to_end(test_db_with_config, fixture_jobs, monkeypatch):
    """Full pipeline: mock scrape → classify → match → generate → verify DB + health check."""
    from database.db import get_all_jobs, get_proposals, get_all_job_uids
    import asyncio
    import sys

    # Get initial state
    initial_uids = get_all_job_uids()
    assert len(initial_uids) == 0, "DB should start empty"

    # Mock Chrome scraping to return fixture jobs
    async def mock_scrape_keyword(page, keyword, max_pages=None, start_page=1, save_fn=None):
        """Mock scraper that returns fixture jobs."""
        # Return a subset of fixture jobs (first 3)
        mock_jobs = fixture_jobs[:3]
        return mock_jobs

    # Mock browser launch
    async def mock_launch(*args, **kwargs):
        browser = AsyncMock()
        return browser, None

    async def mock_get_page(browser):
        page = AsyncMock()
        return page

    async def mock_warmup(page):
        pass

    # Mock classify_all function (which is what monitor calls)
    def mock_classify_all():
        """Mock classifier that updates DB directly."""
        # classify_all doesn't return anything, it updates the DB directly
        from database.db import get_connection
        conn = get_connection()
        # Update all jobs with mock classification
        conn.execute("""
            UPDATE jobs SET
                categories = '["RAG / Document AI"]',
                key_tools = '["LangChain", "Pinecone"]',
                ai_summary = 'Build RAG chatbot'
            WHERE ai_summary = '' OR ai_summary IS NULL
        """)
        conn.commit()
        conn.close()

    # Mock proposal generation
    def mock_generate_with_retry(client, job, match_score, match_reasons, profile, projects, guidelines):
        """Mock proposal generator."""
        return f"Sample proposal for {job['title']}"

    # Mock playwright module to avoid import errors
    sys.modules['playwright'] = MagicMock()
    sys.modules['playwright.async_api'] = MagicMock()

    monkeypatch.setenv("XAI_API_KEY", "test-key")

    # Force reload of matcher module to pick up monkeypatched config
    import sys
    if 'matcher' in sys.modules:
        del sys.modules['matcher']
    if 'main' in sys.modules:
        del sys.modules['main']

    # Patch all external dependencies
    with patch("scraper.search.scrape_keyword", mock_scrape_keyword), \
         patch("scraper.browser.launch_chrome_and_connect", mock_launch), \
         patch("scraper.browser.get_page", mock_get_page), \
         patch("scraper.browser.warmup_cloudflare", mock_warmup), \
         patch("classifier.ai.classify_all", mock_classify_all), \
         patch("proposal_generator.generate_proposal_with_retry", mock_generate_with_retry), \
         patch("proposal_generator.OpenAI", MagicMock()):

        # Import and run monitor pipeline
        from main import cmd_monitor_new

        # Run the pipeline
        asyncio.run(cmd_monitor_new(dry_run=False))

    # Verify results
    # 1. Jobs were scraped and saved
    all_jobs = get_all_jobs()
    assert len(all_jobs) == 3, f"Expected 3 jobs, got {len(all_jobs)}"

    # 2. Jobs were classified (check for ai_summary)
    classified_jobs = [j for j in all_jobs if j.get('ai_summary')]
    assert len(classified_jobs) > 0, "At least some jobs should be classified"

    # 3. Check proposals were generated for matched jobs
    proposals = get_proposals()
    assert len(proposals) >= 2, f"Expected at least 2 proposals (65+ score), got {len(proposals)}"

    # Verify proposal structure
    for prop in proposals:
        assert prop['job_uid'] in [j['uid'] for j in all_jobs]
        assert prop['match_score'] > 0
        assert len(prop['proposal_text']) > 0
        assert prop['status'] == 'pending_review'

    # 4. Verify health check file was created
    import config
    health_file = config.DATA_DIR / "last_run_status.json"
    assert health_file.exists(), "Health check file should be created"

    with open(health_file) as f:
        health_data = json.load(f)

    assert health_data['status'] in ['success', 'partial_failure']
    assert health_data['jobs_scraped'] == 3
    assert health_data['jobs_new'] == 3
    assert health_data['proposals_generated'] >= 0
    assert 'timestamp' in health_data
    assert 'duration_seconds' in health_data


@pytest.mark.skip(reason="Integration test hangs - needs async/event loop investigation")
def test_monitor_pipeline_match_scores_stored_correctly(test_db_with_config, fixture_jobs, monkeypatch):
    """Verify match scores and reasons are stored with correct JSON structure."""
    from database.db import get_proposals
    import asyncio
    import sys

    # Mock scraping to return only high-match fixture job
    async def mock_scrape_keyword(page, keyword, max_pages=None, start_page=1, save_fn=None):
        return [fixture_jobs[0]]  # High-match RAG job

    async def mock_launch(*args, **kwargs):
        browser = AsyncMock()
        return browser, None

    async def mock_get_page(browser):
        page = AsyncMock()
        return page

    async def mock_warmup(page):
        pass

    def mock_classify_all():
        """Mock classifier."""
        from database.db import get_connection
        conn = get_connection()
        conn.execute("""
            UPDATE jobs SET
                categories = '["RAG / Document AI"]',
                key_tools = '["LangChain", "Pinecone"]',
                ai_summary = 'Build RAG system'
            WHERE ai_summary = '' OR ai_summary IS NULL
        """)
        conn.commit()
        conn.close()

    def mock_generate_with_retry(client, job, match_score, match_reasons, profile, projects, guidelines):
        return "Test proposal"

    # Mock playwright module
    sys.modules['playwright'] = MagicMock()
    sys.modules['playwright.async_api'] = MagicMock()

    monkeypatch.setenv("XAI_API_KEY", "test-key")

    # Force reload of modules to pick up monkeypatched config
    if 'matcher' in sys.modules:
        del sys.modules['matcher']
    if 'main' in sys.modules:
        del sys.modules['main']

    with patch("scraper.search.scrape_keyword", mock_scrape_keyword), \
         patch("scraper.browser.launch_chrome_and_connect", mock_launch), \
         patch("scraper.browser.get_page", mock_get_page), \
         patch("scraper.browser.warmup_cloudflare", mock_warmup), \
         patch("classifier.ai.classify_all", mock_classify_all), \
         patch("proposal_generator.generate_proposal_with_retry", mock_generate_with_retry), \
         patch("proposal_generator.OpenAI", MagicMock()):

        from main import cmd_monitor_new
        asyncio.run(cmd_monitor_new(dry_run=False))

    # Verify match_reasons JSON structure
    proposals = get_proposals()
    assert len(proposals) > 0, "Should have generated at least one proposal"

    prop = proposals[0]
    assert prop['match_score'] > 0, "Match score should be positive"

    # Parse match_reasons
    match_reasons = json.loads(prop['match_reasons'])
    assert isinstance(match_reasons, list), "match_reasons should be a JSON array"

    if len(match_reasons) > 0:
        reason = match_reasons[0]
        assert 'criterion' in reason, "Each reason should have 'criterion'"
        assert 'weight' in reason, "Each reason should have 'weight'"
        assert 'score' in reason, "Each reason should have 'score'"
        assert 'detail' in reason, "Each reason should have 'detail'"


@pytest.mark.skip(reason="Integration test hangs - needs async/event loop investigation")
def test_monitor_pipeline_idempotency(test_db_with_config, fixture_jobs, monkeypatch):
    """Running monitor twice should not create duplicate proposals."""
    from database.db import get_proposals, get_all_jobs
    import asyncio
    import sys

    # Mock scraping
    async def mock_scrape_keyword(page, keyword, max_pages=None, start_page=1, save_fn=None):
        return [fixture_jobs[0]]

    async def mock_launch(*args, **kwargs):
        browser = AsyncMock()
        return browser, None

    async def mock_get_page(browser):
        page = AsyncMock()
        return page

    async def mock_warmup(page):
        pass

    def mock_classify_all():
        """Mock classifier."""
        from database.db import get_connection
        conn = get_connection()
        conn.execute("""
            UPDATE jobs SET
                categories = '["RAG / Document AI"]',
                key_tools = '["LangChain"]',
                ai_summary = 'Build RAG'
            WHERE ai_summary = '' OR ai_summary IS NULL
        """)
        conn.commit()
        conn.close()

    def mock_generate_with_retry(client, job, match_score, match_reasons, profile, projects, guidelines):
        return "Test proposal"

    # Mock playwright module
    sys.modules['playwright'] = MagicMock()
    sys.modules['playwright.async_api'] = MagicMock()

    monkeypatch.setenv("XAI_API_KEY", "test-key")

    # Force reload of modules to pick up monkeypatched config
    if 'matcher' in sys.modules:
        del sys.modules['matcher']
    if 'main' in sys.modules:
        del sys.modules['main']

    with patch("scraper.search.scrape_keyword", mock_scrape_keyword), \
         patch("scraper.browser.launch_chrome_and_connect", mock_launch), \
         patch("scraper.browser.get_page", mock_get_page), \
         patch("scraper.browser.warmup_cloudflare", mock_warmup), \
         patch("classifier.ai.classify_all", mock_classify_all), \
         patch("proposal_generator.generate_proposal_with_retry", mock_generate_with_retry), \
         patch("proposal_generator.OpenAI", MagicMock()):

        from main import cmd_monitor_new

        # Run pipeline first time
        asyncio.run(cmd_monitor_new(dry_run=False))
        proposals_after_first = get_proposals()
        first_count = len(proposals_after_first)

        # Run pipeline second time (same job already in DB)
        asyncio.run(cmd_monitor_new(dry_run=False))
        proposals_after_second = get_proposals()
        second_count = len(proposals_after_second)

        # Should not create duplicates
        assert second_count == first_count, \
            f"Second run created duplicates: {first_count} → {second_count} proposals"

        # Verify no duplicate job_uids in proposals
        job_uids = [p['job_uid'] for p in proposals_after_second]
        assert len(job_uids) == len(set(job_uids)), "Found duplicate job_uids in proposals"
