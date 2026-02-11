"""Tests for proposals table CRUD operations in database/db.py.

These tests validate the proposals DB functions that will be created
in Step 1.2 of WORKFLOW.md. Uses a temporary in-memory or temp-file DB.

Run: pytest tests/test_db_proposals.py -v
"""
import os
import sqlite3
import tempfile

import pytest


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Set up a temporary database with jobs + proposals tables."""
    db_path = str(tmp_path / "test_jobs.db")
    monkeypatch.setenv("UPWORK_DB_PATH", db_path)

    # Patch the DB_PATH in config so db.py uses our temp DB
    import config
    monkeypatch.setattr(config, "DB_PATH", db_path)

    from database.db import init_db
    init_db()

    # Insert a test job to reference from proposals
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT INTO jobs (uid, title, url, keyword, scraped_at)
        VALUES ('~testjob001', 'Test AI Job', 'https://upwork.com/jobs/~testjob001', 'ai', '2026-02-11')
    """)
    conn.execute("""
        INSERT INTO jobs (uid, title, url, keyword, scraped_at)
        VALUES ('~testjob002', 'Test ML Job', 'https://upwork.com/jobs/~testjob002', 'ml', '2026-02-11')
    """)
    conn.commit()
    conn.close()

    yield db_path


def test_insert_and_get_proposal(test_db):
    """insert_proposal() stores data, get_proposals() retrieves it."""
    from database.db import insert_proposal, get_proposals

    insert_proposal(
        job_uid="~testjob001",
        proposal_text="Hi, I'd love to help with your AI project...",
        match_score=85.0,
        match_reasons='["Category: RAG (100%)", "Skills: Python, LangChain (90%)"]',
    )

    proposals = get_proposals()
    assert len(proposals) >= 1, "Should have at least one proposal"

    p = [p for p in proposals if p["job_uid"] == "~testjob001"][0]
    assert p["proposal_text"] == "Hi, I'd love to help with your AI project..."
    assert p["match_score"] == 85.0
    assert p["status"] == "pending_review"


def test_duplicate_proposal_rejected(test_db):
    """Second proposal for same job_uid should not create a duplicate row."""
    from database.db import insert_proposal, get_proposals

    insert_proposal(
        job_uid="~testjob002",
        proposal_text="First proposal text",
        match_score=75.0,
        match_reasons="[]",
    )

    # Second insert: should either raise or silently ignore
    try:
        insert_proposal(
            job_uid="~testjob002",
            proposal_text="Duplicate",
            match_score=80.0,
            match_reasons="[]",
        )
    except Exception:
        pass  # Raising is acceptable behavior

    # Either way, only one proposal should exist for this job
    proposals = get_proposals()
    job002_proposals = [p for p in proposals if p["job_uid"] == "~testjob002"]
    assert len(job002_proposals) == 1, f"Expected 1 proposal, got {len(job002_proposals)}"
    assert job002_proposals[0]["proposal_text"] == "First proposal text"


def test_proposal_status_transitions(test_db):
    """pending_review -> approved -> submitted should update correctly."""
    from database.db import insert_proposal, get_proposals, update_proposal_status

    insert_proposal(
        job_uid="~testjob001",
        proposal_text="Test proposal",
        match_score=90.0,
        match_reasons="[]",
    )

    proposals = get_proposals()
    prop = [p for p in proposals if p["job_uid"] == "~testjob001"][0]
    assert prop["status"] == "pending_review"

    update_proposal_status(prop["id"], "approved")
    proposals = get_proposals()
    prop = [p for p in proposals if p["job_uid"] == "~testjob001"][0]
    assert prop["status"] == "approved"

    update_proposal_status(prop["id"], "submitted")
    proposals = get_proposals()
    prop = [p for p in proposals if p["job_uid"] == "~testjob001"][0]
    assert prop["status"] == "submitted"
