"""Tests for the unified AI client factory.

Run: pytest tests/test_ai_client.py -v
"""

import os
from pathlib import Path

import pytest
import yaml


SAMPLE_CONFIG = Path(__file__).parent / "fixtures" / "sample_config" / "ai_models.yaml"


def test_load_ai_config_parses_yaml():
    """load_ai_config() should parse the sample YAML correctly."""
    from ai_client import load_ai_config

    cfg = load_ai_config(SAMPLE_CONFIG)
    assert "ai_models" in cfg
    assert "classification" in cfg["ai_models"]
    assert "proposal_generation" in cfg["ai_models"]
    assert "providers" in cfg["ai_models"]


def test_load_ai_config_missing_file():
    """load_ai_config() should raise FileNotFoundError for missing file."""
    from ai_client import load_ai_config

    with pytest.raises(FileNotFoundError):
        load_ai_config(Path("/nonexistent/ai_models.yaml"))


def test_get_client_classification():
    """get_client('classification') should return client, model, and provider."""
    from ai_client import get_client

    client, model_name, provider_name = get_client("classification", config_path=SAMPLE_CONFIG, skip_health_check=True)
    assert model_name == "llama3:8b"
    assert provider_name == "ollama_local"
    assert client is not None


def test_get_client_proposal_generation():
    """get_client('proposal_generation') should return client, model, and provider."""
    from ai_client import get_client

    client, model_name, provider_name = get_client("proposal_generation", config_path=SAMPLE_CONFIG, skip_health_check=True)
    assert model_name == "llama3:8b"
    assert provider_name == "ollama_local"


def test_get_client_groq_missing_api_key(tmp_path, monkeypatch):
    """get_client() should raise RuntimeError when Groq API key is missing."""
    from ai_client import get_client

    # Create config that uses groq as provider
    cfg = {
        "ai_models": {
            "classification": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
            "proposal_generation": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
            "providers": {
                "groq": {
                    "name": "Groq Cloud",
                    "base_url": "https://api.groq.com/openai/v1",
                    "api_key": None,
                    "api_key_env": "GROQ_API_KEY",
                    "models": ["llama-3.3-70b-versatile"],
                }
            },
        }
    }
    cfg_path = tmp_path / "ai_models.yaml"
    with open(cfg_path, "w") as f:
        yaml.dump(cfg, f)

    # Ensure env var is not set
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        get_client("classification", config_path=cfg_path)


def test_get_client_groq_with_api_key(tmp_path, monkeypatch):
    """get_client() should work when Groq API key is set in env."""
    from ai_client import get_client

    cfg = {
        "ai_models": {
            "classification": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
            "proposal_generation": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
            "providers": {
                "groq": {
                    "name": "Groq Cloud",
                    "base_url": "https://api.groq.com/openai/v1",
                    "api_key": None,
                    "api_key_env": "GROQ_API_KEY",
                    "models": ["llama-3.3-70b-versatile"],
                }
            },
        }
    }
    cfg_path = tmp_path / "ai_models.yaml"
    with open(cfg_path, "w") as f:
        yaml.dump(cfg, f)

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")

    client, model_name, provider_name = get_client("classification", config_path=cfg_path, skip_health_check=True)
    assert provider_name == "groq"
    assert model_name == "llama-3.3-70b-versatile"


def test_list_available_models():
    """list_available_models() should return model list from config."""
    from ai_client import list_available_models

    models = list_available_models("ollama_local", config_path=SAMPLE_CONFIG)
    assert "llama3:8b" in models
    assert "mistral:7b" in models

    groq_models = list_available_models("groq", config_path=SAMPLE_CONFIG)
    assert "llama-3.3-70b-versatile" in groq_models


def test_list_available_models_default_provider():
    """list_available_models() with no provider should use classification provider."""
    from ai_client import list_available_models

    models = list_available_models(config_path=SAMPLE_CONFIG)
    assert "llama3:8b" in models
