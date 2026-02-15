"""Integration tests for the end-to-end pipeline.

Tests the flow: database upsert -> matcher -> proposal generator -> database insert proposal.

Uses a real temporary SQLite database for DB operations; mocks only the AI client
(no real API calls) and the scraper (no real Chrome needed).

Run: pytest tests/test_pipeline_integration.py -v
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

import config
import database.db as db_mod
from database.db import (
    init_db,
    upsert_jobs,
    get_all_jobs,
    insert_proposal,
    get_proposals,
    proposal_exists,
    get_all_job_uids,
)
from matcher import score_job, get_matching_jobs


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def integration_db(tmp_path, monkeypatch):
    """Set up a temporary SQLite database for integration tests.

    Patches config.DB_PATH so that database.adapter._get_sqlite_connection()
    uses the temp path, then initialises the full schema via init_db().
    """
    db_path = tmp_path / "test_integration.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    init_db()
    return db_path


@pytest.fixture
def sample_jobs():
    """Sample jobs covering different types and budget ranges."""
    return [
        {
            "uid": "~integ001",
            "title": "Build AI Pipeline with Python",
            "url": "https://upwork.com/jobs/~integ001",
            "posted_text": "1 hour ago",
            "description": "Need Python AI developer for data pipeline",
            "job_type": "Fixed",
            "fixed_price": 3000.0,
            "experience_level": "Intermediate",
            "skills": '["Python", "TensorFlow", "Docker"]',
            "keyword": "python ai",
            "scraped_at": "2025-01-15 12:00:00",
            "source_page": 1,
            "category": "AI/ML",
            "category_confidence": 0.95,
            "key_tools": '["Python", "TensorFlow"]',
        },
        {
            "uid": "~integ002",
            "title": "LangChain RAG Chatbot Development",
            "url": "https://upwork.com/jobs/~integ002",
            "posted_text": "3 hours ago",
            "description": "Build a RAG chatbot using LangChain and Pinecone for customer support",
            "job_type": "Hourly",
            "hourly_rate_min": 50.0,
            "hourly_rate_max": 80.0,
            "experience_level": "Expert",
            "skills": '["Python", "LangChain", "Pinecone", "OpenAI"]',
            "keyword": "langchain",
            "scraped_at": "2025-01-15 12:30:00",
            "source_page": 1,
            "category": "RAG / Document AI",
            "category_confidence": 0.98,
            "key_tools": '["LangChain", "Pinecone"]',
            "client_total_spent": "$50K+ spent",
            "client_rating": "4.9 of 5",
            "client_info_raw": "Payment method verified",
        },
        {
            "uid": "~integ003",
            "title": "WordPress Blog Setup",
            "url": "https://upwork.com/jobs/~integ003",
            "posted_text": "5 hours ago",
            "description": "Simple WordPress blog setup with basic customisation",
            "job_type": "Fixed",
            "fixed_price": 200.0,
            "experience_level": "Entry Level",
            "skills": '["WordPress", "HTML", "CSS"]',
            "keyword": "wordpress",
            "scraped_at": "2025-01-15 13:00:00",
            "source_page": 2,
            "category": "Web Development",
            "category_confidence": 0.90,
            "key_tools": '["WordPress"]',
        },
    ]


@pytest.fixture
def integration_preferences():
    """Preferences suitable for the integration sample jobs."""
    return {
        "categories": [
            "RAG / Document AI",
            "AI/ML",
            "AI Agent / Multi-Agent System",
        ],
        "required_skills": ["python", "langchain"],
        "nice_to_have_skills": ["pinecone", "openai", "fastapi"],
        "budget": {
            "fixed_min": 500,
            "fixed_max": 10000,
            "hourly_min": 40,
        },
        "client_criteria": {
            "payment_verified": True,
            "min_total_spent": 1000,
            "min_rating": 4.0,
        },
        "exclusion_keywords": ["wordpress", "data entry"],
        "threshold": 30,
    }


@pytest.fixture
def config_dir_with_files(tmp_path):
    """Create a temporary config directory with all required config YAML files."""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()

    configs = {
        "user_profile.yaml": {
            "profile": {
                "name": "Test Developer",
                "bio": "AI/ML developer specialising in RAG systems and LangChain.",
                "years_experience": 5,
                "specializations": ["RAG Systems", "AI Chatbots"],
                "unique_value": "Production-ready AI solutions with clean code.",
                "rate_info": {"hourly": 50, "project_min": 1000},
                "skills": ["Python", "LangChain", "OpenAI"],
            }
        },
        "projects.yaml": {
            "projects": [
                {
                    "title": "RAG Customer Support Bot",
                    "description": "Built production RAG system using LangChain and Pinecone.",
                    "technologies": ["Python", "LangChain", "Pinecone", "OpenAI"],
                    "outcomes": "Reduced support tickets by 40%.",
                    "url": None,
                }
            ]
        },
        "proposal_guidelines.yaml": {
            "guidelines": {
                "tone": "professional",
                "max_length": 300,
                "required_sections": [
                    "greeting",
                    "relevant_experience",
                    "approach",
                    "call_to_action",
                ],
                "avoid_phrases": ["I am very interested"],
                "emphasis": ["Reference specific job requirements"],
                "max_daily_proposals": 20,
            }
        },
        "job_preferences.yaml": {
            "preferences": {
                "categories": ["RAG / Document AI", "AI/ML"],
                "required_skills": ["Python", "LangChain"],
                "nice_to_have_skills": ["Pinecone"],
                "budget": {"fixed_min": 500, "fixed_max": 10000, "hourly_min": 40},
                "client_criteria": {
                    "payment_verified": True,
                    "min_total_spent": 1000,
                    "min_rating": 4.0,
                },
                "exclusion_keywords": ["wordpress"],
                "threshold": 30,
            }
        },
    }

    for filename, content in configs.items():
        with open(cfg_dir / filename, "w") as f:
            yaml.dump(content, f)

    return cfg_dir


# ── Test 1: DB upsert -> load -> score ────────────────────────────────


def test_upsert_then_score_jobs(integration_db, sample_jobs, integration_preferences):
    """Upsert jobs to real DB, load them back, score each with matcher.

    Validates the database-to-matcher flow:
    - Jobs survive an upsert round-trip through SQLite
    - score_job() returns valid 0-100 scores for every job
    - Jobs matching preferences score higher than non-matching ones
    """
    # 1. Upsert sample jobs into the real temp DB
    inserted, updated = upsert_jobs(sample_jobs)
    assert inserted == 3, f"Expected 3 inserts, got {inserted}"
    assert updated == 0, f"Expected 0 updates, got {updated}"

    # 2. Load all jobs back from DB
    all_jobs = get_all_jobs()
    assert len(all_jobs) == 3, f"Expected 3 jobs in DB, got {len(all_jobs)}"

    # 3. Verify UIDs round-tripped correctly
    uids_in_db = get_all_job_uids()
    assert uids_in_db == {"~integ001", "~integ002", "~integ003"}

    # 4. Score every job; all scores must be 0-100 floats
    scores = {}
    for job in all_jobs:
        score, reasons = score_job(job, integration_preferences)
        assert isinstance(score, (int, float)), (
            f"Score for {job['uid']} should be numeric, got {type(score)}"
        )
        assert 0 <= score <= 100, (
            f"Score {score} for {job['uid']} outside valid range 0-100"
        )
        assert isinstance(reasons, list), "Reasons should be a list"
        scores[job["uid"]] = score

    # 5. The WordPress job should be excluded (score == 0) or very low
    # because "wordpress" is in the exclusion_keywords list
    assert scores["~integ003"] == 0, (
        f"WordPress job should be excluded (score 0), got {scores['~integ003']}"
    )

    # 6. The RAG/LangChain job should score higher than the generic AI job
    assert scores["~integ002"] > scores["~integ001"], (
        f"RAG job ({scores['~integ002']}) should outscore generic AI job ({scores['~integ001']})"
    )


# ── Test 2: upsert job -> insert proposal -> proposal_exists ─────────


def test_upsert_and_check_proposal_exists(integration_db, sample_jobs):
    """Upsert a job, insert a proposal for it, then verify proposal_exists().

    Validates the database proposal flow:
    - A proposal can be inserted for an existing job
    - proposal_exists() returns True for that job
    - proposal_exists() returns False for a non-existent job
    - The proposal data round-trips correctly (text, score, reasons)
    """
    # 1. Upsert just the first job
    upsert_jobs([sample_jobs[0]])
    assert get_all_job_uids() == {"~integ001"}

    # 2. Before inserting a proposal, proposal_exists should be False
    assert proposal_exists("~integ001") is False, (
        "No proposal should exist yet for ~integ001"
    )

    # 3. Insert a proposal for that job
    match_reasons = json.dumps([
        {"criterion": "category", "weight": 30, "score": 1.0, "detail": "AI/ML match"},
        {"criterion": "budget_fit", "weight": 20, "score": 1.0, "detail": "$3000 fixed"},
    ])
    proposal_id = insert_proposal(
        job_uid="~integ001",
        proposal_text="I would love to help build this AI pipeline...",
        match_score=75.5,
        match_reasons=match_reasons,
        status="pending_review",
    )
    assert isinstance(proposal_id, int), f"Expected int proposal ID, got {type(proposal_id)}"
    assert proposal_id > 0, "Proposal ID should be a positive integer"

    # 4. proposal_exists should now return True
    assert proposal_exists("~integ001") is True, (
        "proposal_exists() should return True after inserting a proposal"
    )

    # 5. proposal_exists for a non-existent job should return False
    assert proposal_exists("~nonexistent999") is False, (
        "proposal_exists() should return False for a job with no proposal"
    )

    # 6. Verify proposal data via get_proposals()
    proposals = get_proposals(status="pending_review")
    assert len(proposals) == 1, f"Expected 1 proposal, got {len(proposals)}"
    p = proposals[0]
    assert p["job_uid"] == "~integ001"
    assert "AI pipeline" in p["proposal_text"]
    assert p["match_score"] == pytest.approx(75.5)
    assert p["status"] == "pending_review"

    # Verify match_reasons round-tripped as valid JSON
    stored_reasons = json.loads(p["match_reasons"])
    assert len(stored_reasons) == 2
    assert stored_reasons[0]["criterion"] == "category"


# ── Test 3: batch generation dry-run ──────────────────────────────────


def test_batch_generation_dry_run(
    integration_db, sample_jobs, config_dir_with_files, monkeypatch
):
    """Upsert jobs, build matched_jobs list, run generate_proposals_batch(dry_run=True).

    Validates the proposal batch pipeline in dry-run mode:
    - Config files are loaded from the temp directory
    - dry_run=True skips actual AI calls and DB writes
    - Returns results dict with generated > 0 and no errors
    """
    # 1. Point config.CONFIG_DIR at the temp config directory
    monkeypatch.setattr(config, "CONFIG_DIR", config_dir_with_files)

    # 2. Upsert sample jobs to DB (needed so UIDs exist)
    upsert_jobs(sample_jobs)

    # 3. Build matched_jobs list as the matcher would produce
    matched_jobs = [
        {
            **sample_jobs[0],
            "match_score": 72.5,
            "match_reasons": json.dumps([
                {"criterion": "category", "weight": 30, "score": 1.0, "detail": "AI/ML match"},
                {"criterion": "required_skills", "weight": 25, "score": 0.5, "detail": "1/2 found: python"},
            ]),
        },
        {
            **sample_jobs[1],
            "match_score": 91.0,
            "match_reasons": json.dumps([
                {"criterion": "category", "weight": 30, "score": 1.0, "detail": "RAG / Document AI match"},
                {"criterion": "required_skills", "weight": 25, "score": 1.0, "detail": "2/2 found"},
                {"criterion": "budget_fit", "weight": 20, "score": 1.0, "detail": "$50/hr meets min"},
            ]),
        },
    ]

    # 4. Mock the daily limit check so it does not block us,
    #    and the API rate limit check so it does not try to access the real tracker DB
    mock_rate_status = {
        "warning": False,
        "exceeded": False,
        "used": 0,
        "limit": 100000,
        "remaining": 100000,
        "percentage": 0.0,
    }

    with patch("proposal_generator.get_proposals_generated_today", return_value=0), \
         patch("proposal_generator.check_api_rate_limit", return_value=mock_rate_status):

        from proposal_generator import generate_proposals_batch

        results = generate_proposals_batch(matched_jobs, dry_run=True)

    # 5. Verify results
    assert isinstance(results, dict), "Results should be a dict"
    assert results["generated"] == 2, (
        f"Expected 2 dry-run generations, got {results['generated']}"
    )
    assert results["failed"] == 0, (
        f"Expected 0 failures, got {results['failed']}"
    )
    assert len(results["errors"]) == 0, (
        f"Expected no errors, got {results['errors']}"
    )

    # 6. In dry-run mode, no proposals should have been written to the DB
    assert proposal_exists("~integ001") is False, (
        "dry_run should not insert proposals into the database"
    )
    assert proposal_exists("~integ002") is False, (
        "dry_run should not insert proposals into the database"
    )
