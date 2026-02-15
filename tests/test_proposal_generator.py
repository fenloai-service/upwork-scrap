"""Tests for proposal generation with AI providers.

Uses mocked API calls to avoid network dependencies.

Run: pytest tests/test_proposal_generator.py -v
"""
import json
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def sample_job():
    """Sample job for proposal generation testing."""
    return {
        "uid": "~testjob001",
        "title": "Build RAG Chatbot with LangChain",
        "description": "Need an experienced developer to build a RAG system...",
        "categories": '["RAG / Document AI"]',
        "key_tools": '["LangChain", "Pinecone"]',
        "skills": '["Python", "LangChain", "Pinecone"]',
        "job_type": "Fixed",
        "fixed_price": 2500.0,
    }


@pytest.fixture
def sample_match_reasons():
    """Sample match reasons from matcher."""
    return [
        {"criterion": "category_match", "weight": 30, "score": 1.0, "detail": "Perfect category match"},
        {"criterion": "required_skills", "weight": 25, "score": 1.0, "detail": "All required skills present"},
    ]


def test_successful_generation_with_mocked_api(sample_job, sample_match_reasons, tmp_path, monkeypatch):
    """generate_proposal() with mocked API should return proposal text."""
    from proposal_generator import generate_proposal

    # Mock the OpenAI client
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """Hi there,

I'd love to help you build this RAG chatbot using LangChain and Pinecone. I have 5 years of experience building production RAG systems.

In my previous project, I built a similar RAG system that reduced support tickets by 40%.

I propose we start with a discovery call to understand your requirements, then proceed with:
1. Set up the vector database
2. Implement the RAG pipeline
3. Test and deploy

Looking forward to working with you!"""

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    # Set up temp config directory
    import os
    import yaml
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create minimal config files
    configs = {
        "user_profile.yaml": {
            "profile": {
                "name": "Test Dev",
                "bio": "AI developer",
                "years_experience": 5,
                "specializations": ["RAG"],
                "unique_value": "I deliver quality",
                "rate_info": {"hourly": 75, "project_min": 1500},
                "skills": ["Python", "LangChain"]
            }
        },
        "projects.yaml": {
            "projects": [{
                "title": "RAG Chatbot",
                "description": "Built RAG system",
                "technologies": ["Python", "LangChain", "Pinecone"],
                "outcomes": "Reduced support tickets by 40%",
                "url": None
            }]
        },
        "proposal_guidelines.yaml": {
            "guidelines": {
                "tone": "professional",
                "max_length": 300,
                "required_sections": ["greeting", "relevant_experience", "approach", "call_to_action"],
                "avoid_phrases": ["I am very interested"],
                "emphasis": ["Reference specific job requirements"],
                "max_daily_proposals": 20
            }
        }
    }

    for filename, content in configs.items():
        with open(config_dir / filename, "w") as f:
            yaml.dump(content, f)

    # Patch config.CONFIG_DIR
    import config
    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)

    # Patch get_client to return mock client
    with patch("proposal_generator.get_client", return_value=(mock_client, "llama3:8b", "ollama_local")):
        proposal_text = generate_proposal(sample_job, 85.0, sample_match_reasons)

        assert isinstance(proposal_text, str)
        assert len(proposal_text) > 0
        assert "RAG" in proposal_text or "chatbot" in proposal_text.lower()
        mock_client.chat.completions.create.assert_called_once()


def test_api_timeout_handling(sample_job, sample_match_reasons, tmp_path, monkeypatch):
    """generate_proposal() should retry on API timeout."""
    from proposal_generator import generate_proposal
    import time

    # Mock client that times out first 2 times, succeeds on 3rd
    call_count = 0

    def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Request timeout")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test proposal text"
        return mock_response

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = mock_create

    # Setup configs (minimal)
    import yaml
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    for filename in ["user_profile.yaml", "projects.yaml", "proposal_guidelines.yaml"]:
        with open(config_dir / filename, "w") as f:
            yaml.dump({"profile": {}, "projects": [], "guidelines": {}}, f)

    import config
    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)

    with patch("proposal_generator.get_client", return_value=(mock_client, "llama3:8b", "ollama_local")):
        # Should succeed after 3 attempts
        proposal = generate_proposal(sample_job, 80.0, sample_match_reasons)
        assert proposal == "Test proposal text"
        assert call_count == 3, f"Should have retried 3 times, got {call_count}"


def test_malformed_json_response(sample_job, sample_match_reasons, tmp_path, monkeypatch):
    """generate_proposal() should handle malformed responses gracefully."""
    from proposal_generator import generate_proposal

    # Mock API returning markdown fences (common issue)
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """```
Test proposal with markdown fences
```"""

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    # Setup configs
    import yaml
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    for filename in ["user_profile.yaml", "projects.yaml", "proposal_guidelines.yaml"]:
        with open(config_dir / filename, "w") as f:
            yaml.dump({"profile": {}, "projects": [], "guidelines": {}}, f)

    import config
    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)

    with patch("proposal_generator.get_client", return_value=(mock_client, "llama3:8b", "ollama_local")):
        proposal = generate_proposal(sample_job, 80.0, sample_match_reasons)

        # Should strip markdown fences
        assert "```" not in proposal
        assert "Test proposal with markdown fences" in proposal


def test_daily_rate_limit_cap_reached(sample_job, sample_match_reasons, tmp_path, monkeypatch):
    """generate_proposals_batch() should respect daily cap of 20 proposals."""
    from proposal_generator import generate_proposals_batch

    # Mock API rate limit check to pass
    mock_rate_status = {'warning': False, 'exceeded': False, 'used': 0, 'limit': 100000, 'remaining': 100000, 'percentage': 0.0}

    # Mock get_proposals_generated_today to return 20 (at limit)
    with patch("proposal_generator.check_api_rate_limit", return_value=mock_rate_status), \
         patch("proposal_generator.get_proposals_generated_today", return_value=20):
        matched_jobs = [sample_job] * 5  # 5 jobs to process

        results = generate_proposals_batch(matched_jobs, dry_run=False)

        # Should hit internal daily limit (check_daily_limit returns True)
        assert "Daily limit" in str(results['errors'])


def test_prompt_construction(sample_job, sample_match_reasons, tmp_path, monkeypatch):
    """Constructed prompt should contain job title, description, relevant project, and guidelines."""
    from unittest.mock import patch
    from proposal_generator import build_proposal_prompt

    # Setup configs
    import yaml
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    profile = {
        "profile": {
            "name": "Test Dev",
            "bio": "AI developer with RAG experience",
            "years_experience": 5,
            "specializations": ["RAG Systems"],
            "unique_value": "I deliver quality code",
            "rate_info": {"hourly": 75, "project_min": 1500},
            "skills": ["Python"]
        }
    }

    projects = {
        "projects": [{
            "title": "RAG Customer Support Bot",
            "description": "Built production RAG system using LangChain and Pinecone",
            "technologies": ["Python", "LangChain", "Pinecone", "OpenAI"],
            "outcomes": "Reduced support load by 40%, 95% accuracy",
            "url": "https://github.com/test/rag-bot"
        }]
    }

    guidelines = {
        "guidelines": {
            "tone": "professional",
            "max_length": 300,
            "required_sections": ["greeting", "experience", "approach"],
            "avoid_phrases": ["I am very interested", "Please consider me"],
            "emphasis": ["Reference job requirements", "Show understanding"],
            "max_daily_proposals": 20
        }
    }

    with open(config_dir / "user_profile.yaml", "w") as f:
        yaml.dump(profile, f)
    with open(config_dir / "projects.yaml", "w") as f:
        yaml.dump(projects, f)
    with open(config_dir / "proposal_guidelines.yaml", "w") as f:
        yaml.dump(guidelines, f)

    import config
    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)

    # Load configs — bypass DB so test YAML files are used
    from proposal_generator import load_user_profile, load_projects, load_guidelines, select_relevant_projects

    with patch("database.db.load_config_from_db", return_value=None):
        user_profile = load_user_profile()
        all_projects = load_projects()
        guide = load_guidelines()

    # Select relevant projects
    selected_projects = select_relevant_projects(sample_job, all_projects)

    # Build prompt
    prompt = build_proposal_prompt(
        sample_job, 85.0, sample_match_reasons,
        user_profile, selected_projects, guide
    )

    # Verify prompt contains key elements
    assert "Build RAG Chatbot" in prompt or "build rag chatbot" in prompt.lower(), "Should contain job title"
    assert "rag" in prompt.lower(), "Should contain description keywords"
    assert "RAG Customer Support Bot" in prompt or "rag customer support bot" in prompt.lower(), "Should contain relevant project title"
    assert "professional" in prompt.lower(), "Should mention tone"
    assert "avoid" in prompt.lower(), "Should mention phrases to avoid"
    assert len(selected_projects) > 0, "Should have selected at least one relevant project"
