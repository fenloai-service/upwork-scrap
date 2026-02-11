"""Tests for YAML config loading and validation.

These tests validate that config files parse correctly and that
missing required fields produce clear errors.

Run: pytest tests/test_config.py -v
"""
import os

import pytest


REQUIRED_CONFIGS = {
    "job_preferences.yaml": "preferences",
    "user_profile.yaml": "profile",
    "projects.yaml": "projects",
    "proposal_guidelines.yaml": "guidelines",
    "email_config.yaml": "email",
}


def test_all_yaml_configs_parse():
    """Each config/*.yaml file should parse with yaml.safe_load() without error."""
    import yaml

    config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")

    if not os.path.isdir(config_dir):
        pytest.skip("config/ directory not yet created (Step 1.1)")

    for filename, expected_key in REQUIRED_CONFIGS.items():
        filepath = os.path.join(config_dir, filename)
        if not os.path.exists(filepath):
            pytest.skip(f"{filename} not yet created (Step 1.1)")

        with open(filepath) as f:
            data = yaml.safe_load(f)

        assert data is not None, f"{filename} parsed as None"
        assert expected_key in data, (
            f"{filename} missing required top-level key '{expected_key}'. "
            f"Found keys: {list(data.keys())}"
        )


def test_missing_required_config_field_raises(tmp_path):
    """Preferences without 'match_threshold' should raise ValueError with helpful message."""
    import yaml

    # Write a preferences file missing match_threshold
    bad_prefs = {
        "preferences": {
            "categories": ["RAG / Document AI"],
            "required_skills": ["Python"],
            # match_threshold intentionally missing
        }
    }
    prefs_path = tmp_path / "job_preferences.yaml"
    with open(prefs_path, "w") as f:
        yaml.dump(bad_prefs, f)

    # This test will be fully functional once matcher.py is created (Step 1.3).
    # For now, we validate the concept: load_preferences should validate required keys.
    try:
        from matcher import load_preferences

        with pytest.raises((ValueError, KeyError)):
            load_preferences(str(prefs_path))
    except ImportError:
        pytest.skip("matcher.py not yet created (Step 1.3)")
