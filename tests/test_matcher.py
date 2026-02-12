"""Tests for job preference matching — the core V2.1 business logic.

These tests validate the matcher module (matcher.py) which will be created
in Step 1.3 of WORKFLOW.md. Tests are written first to define expected behavior.

Run: pytest tests/test_matcher.py -v
"""
import pytest


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_preferences():
    """Minimal preferences matching PRD Section 8 config/job_preferences.yaml."""
    return {
        "preferences": {
            "categories": [
                "RAG / Document AI",
                "AI Agent / Multi-Agent System",
                "AI Chatbot / Virtual Assistant",
            ],
            "required_skills": ["Python", "LangChain"],
            "nice_to_have_skills": ["Pinecone", "OpenAI API", "FastAPI"],
            "budget": {
                "fixed_min": 1000,
                "fixed_max": 10000,
                "hourly_min": 40,
            },
            "client_criteria": {
                "payment_verified": True,
                "min_total_spent": 10000,
                "min_rating": 4.5,
            },
            "exclusions": {
                "keywords": ["data entry", "copy paste", "virtual assistant only"],
            },
            "match_threshold": 70,
        }
    }


@pytest.fixture
def perfect_job():
    """Job that matches all preference criteria perfectly."""
    return {
        "uid": "~test001",
        "title": "Build RAG Chatbot with LangChain",
        "description": "We need a RAG-based chatbot using LangChain and Pinecone.",
        "categories": '["RAG / Document AI"]',
        "key_tools": '["LangChain", "Pinecone"]',
        "skills": '["Python", "LangChain", "Pinecone", "OpenAI API"]',
        "job_type": "Fixed",
        "fixed_price": 2500.0,
        "hourly_rate_min": None,
        "hourly_rate_max": None,
        "client_total_spent": "$50K+ spent",
        "client_rating": "4.9 of 5",
        "client_info_raw": "Payment method verified",
        "posted_date_estimated": "2026-02-11",
    }


@pytest.fixture
def exclusion_job():
    """Job that should be auto-rejected due to exclusion keyword."""
    return {
        "uid": "~test002",
        "title": "Data Entry and Copy Paste Assistant",
        "description": "Need someone for data entry tasks.",
        "categories": "[]",
        "key_tools": "[]",
        "skills": '["Excel", "Data Entry"]',
        "job_type": "Hourly",
        "fixed_price": None,
        "hourly_rate_min": 5.0,
        "hourly_rate_max": 10.0,
        "client_total_spent": "",
        "client_rating": "",
        "client_info_raw": "",
        "posted_date_estimated": "2026-02-11",
    }


@pytest.fixture
def null_fields_job():
    """Job with many null/empty fields — should not crash."""
    return {
        "uid": "~test003",
        "title": "AI Project",
        "description": "Build something with AI.",
        "categories": "",
        "key_tools": "",
        "skills": "",
        "job_type": None,
        "fixed_price": None,
        "hourly_rate_min": None,
        "hourly_rate_max": None,
        "client_total_spent": None,
        "client_rating": None,
        "client_info_raw": None,
        "posted_date_estimated": None,
    }


@pytest.fixture
def hourly_job():
    """Hourly-rate job to test budget_fit for non-fixed-price jobs."""
    return {
        "uid": "~test004",
        "title": "Build AI Agent with LangChain",
        "description": "Need ongoing AI development help.",
        "categories": '["AI Agent / Multi-Agent System"]',
        "key_tools": '["LangChain", "Python"]',
        "skills": '["Python", "LangChain"]',
        "job_type": "Hourly",
        "fixed_price": None,
        "hourly_rate_min": 50.0,
        "hourly_rate_max": 80.0,
        "client_total_spent": "$25K+ spent",
        "client_rating": "4.8 of 5",
        "client_info_raw": "Payment method verified",
        "posted_date_estimated": "2026-02-11",
    }


# ── Tests ─────────────────────────────────────────────────────────────

def test_perfect_match_scores_above_threshold(sample_preferences, perfect_job):
    """Job matching all preferences should score >= 90."""
    from matcher import score_job

    score, reasons = score_job(perfect_job, sample_preferences["preferences"])
    assert score >= 90, f"Perfect match scored {score}, expected >= 90"
    assert len(reasons) > 0, "Should have at least one match reason"


def test_exclusion_keywords_reject_job(sample_preferences, exclusion_job):
    """Job containing exclusion keyword in title should score 0."""
    from matcher import score_job

    score, reasons = score_job(exclusion_job, sample_preferences["preferences"])
    assert score == 0, f"Excluded job scored {score}, expected 0"


def test_job_with_null_fields_scores_without_error(sample_preferences, null_fields_job):
    """Job with None/empty fields should return a numeric score without crashing."""
    from matcher import score_job

    score, reasons = score_job(null_fields_job, sample_preferences["preferences"])
    assert isinstance(score, (int, float)), f"Score should be numeric, got {type(score)}"
    assert 0 <= score <= 100, f"Score {score} out of range 0-100"


def test_get_matching_jobs_filters_below_threshold(sample_preferences, perfect_job, null_fields_job):
    """get_matching_jobs should only return jobs scoring >= threshold."""
    from matcher import get_matching_jobs

    jobs = [perfect_job, null_fields_job]
    prefs = sample_preferences["preferences"]
    matched = get_matching_jobs(jobs, prefs, threshold=prefs["match_threshold"])

    # Perfect job should be included, null_fields_job likely below threshold
    uids = [j["uid"] for j in matched]
    assert "~test001" in uids, "Perfect match job should pass threshold"
    for j in matched:
        assert j["match_score"] >= 70, f"Job {j['uid']} scored {j['match_score']} but threshold is 70"


def test_score_formula_max_is_100(sample_preferences, perfect_job):
    """Verify the max possible score does not exceed 100."""
    from matcher import score_job

    score, _ = score_job(perfect_job, sample_preferences["preferences"])
    assert score <= 100, f"Score {score} exceeds maximum of 100"


def test_hourly_job_scores_correctly(sample_preferences, hourly_job):
    """Hourly-rate job with rate above minimum should get budget_fit credit."""
    from matcher import score_job

    score, reasons = score_job(hourly_job, sample_preferences["preferences"])
    assert score > 0, "Hourly job matching preferences should score > 0"
    assert score >= 70, f"Good hourly match scored {score}, expected >= 70"


def test_client_quality_null_rating_redistributes_weight():
    """Client with no rating should redistribute weight (not crash)."""
    from matcher import score_job

    prefs = {
        "categories": ["AI Chatbot / Virtual Assistant"],
        "required_skills": ["Python"],
        "nice_to_have_skills": [],
        "budget": {"fixed_min": 1000, "fixed_max": 10000, "hourly_min": 40},
        "client_criteria": {"payment_verified": True, "min_total_spent": 5000, "min_rating": 4.5},
        "exclusions": {"keywords": []},
        "match_threshold": 70
    }

    job = {
        "uid": "~test006",
        "title": "Build AI Chatbot",
        "description": "Need a chatbot developer.",
        "categories": '["AI Chatbot / Virtual Assistant"]',
        "key_tools": '["Python", "OpenAI"]',
        "skills": '["Python", "OpenAI API"]',
        "job_type": "Fixed",
        "fixed_price": 2000.0,
        "client_total_spent": "$20K+ spent",
        "client_rating": None,  # No rating yet
        "client_info_raw": "Payment method verified",
    }

    score, reasons = score_job(job, prefs)
    assert isinstance(score, (int, float)), "Should return numeric score"
    assert 0 <= score <= 100, f"Score {score} out of valid range"

    # Find client_quality reason
    client_reason = [r for r in reasons if r['criterion'] == 'client_quality'][0]
    # Should mention either payment verification or spending (without crashing on null rating)
    assert 'verified' in client_reason['detail'].lower() or 'spent' in client_reason['detail'].lower()


def test_client_quality_new_client():
    """New client (no spending + no rating) should still score based on payment verification."""
    from matcher import score_job

    prefs = {
        "categories": ["AI Chatbot / Virtual Assistant"],
        "required_skills": ["Python"],
        "nice_to_have_skills": [],
        "budget": {"fixed_min": 1000, "fixed_max": 10000, "hourly_min": 40},
        "client_criteria": {"payment_verified": True, "min_total_spent": 5000, "min_rating": 4.5},
        "exclusions": {"keywords": []},
        "match_threshold": 70
    }

    job = {
        "uid": "~test007",
        "title": "Build Chatbot (New Client)",
        "description": "First project on Upwork.",
        "categories": '["AI Chatbot / Virtual Assistant"]',
        "key_tools": '["Python"]',
        "skills": '["Python"]',
        "job_type": "Fixed",
        "fixed_price": 1800.0,
        "client_total_spent": "No spending history",
        "client_rating": "No ratings yet",
        "client_info_raw": "Payment method verified",
    }

    score, reasons = score_job(job, prefs)
    assert isinstance(score, (int, float)), "Should return numeric score"
    assert 0 <= score <= 100, f"Score {score} out of valid range"

    # New client with payment verified should get some credit
    client_reason = [r for r in reasons if r['criterion'] == 'client_quality'][0]
    assert client_reason['score'] > 0, "New client with payment verified should get some points"
